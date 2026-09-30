---
name: ipp-cloud-run-deploy
description: IPP AI研修のステップ T-5 で、受講生が作ったアプリを Cloud Run へデプロイする。Gemini API キーは .env から Secret Manager へ安全に登録して参照だけを渡し（平文を残さない）、デプロイ後に /health と /chat を実際に呼んで AI が応答することを確かめ、HITMAN 提出用ログを出力する。また、演習終了後に Cloud Run サービスと Secret Manager のキーを安全に破棄するクリーンアップを行う。「デプロイして」「Cloud Run に出して」「T-5 をやって」「環境を片付けて」「Cloud Run を削除して」「課金を止めて」「クリーンアップして」と頼まれたとき、または HITMAN のプロンプトを貼られたときに使う。
---

# Cloud Run への安全なデプロイと動作確認・安全停止

> [!NOTE]
> **HITMAN 使用証跡**: このスキルのスクリプトが出力するコードブロックの1行目には `[skill:ipp-cloud-run-deploy@v1]` が自動で入る。手で書き足したり書き換えたりしないこと。

URL が出ただけでは「動くアプリ」の証明になりません。このスキルは、デプロイしたアプリに実際にアクセスし、**AI が応答するところまで**を確かめます。また、演習終了後には**作成したリソースとAPIキーを確実に削除**して、課金発生と機密流出を防止します。

## 絶対に守ること

- `gcloud run deploy` を手で実行しない。特に **`--set-env-vars GEMINI_API_KEY=...` は禁止**（キーがデプロイログ・Cloud Run の設定画面に平文で残る）。必ず下のスクリプトを使う。
- `.env` の中身を表示しない（`ipp-secure-credentials` スキルのルール）。
- スクリプトの出力を書き換えない（HITMAN は `DEPLOY_JSON` の生データと `DEPLOY_DIGEST` で改変を検知し、さらに URL へ自分でアクセスして確かめる）。
- 演習終了後は必ずクリーンアップスクリプトを実行し、Cloud Run サービスと Secret Manager のシークレットを破棄すること。

## 事前準備（初回だけ）

1. `gcloud auth login` と `gcloud config set project <プロジェクトID>` が済んでいること（受講生に実行してもらう）。
2. `ipp-agent-workspace/<エージェント名>/.env` に `GEMINI_API_KEY` が設定済みであること（`env_setup.py --check` で確認）。
3. アプリが `GET /health` と `POST /chat`（入力 `{"message": ...}`、出力 `{"reply": ...}` または `{"parts": [...]}`）を持ち、`PORT` 環境変数で待ち受ける Dockerfile があること。

## 手順（デプロイ）

HITMAN の T-5 カードに表示されたコマンドを、ワークスペースのルートでそのまま実行します：

```bash
python .agents/skills/ipp-cloud-run-deploy/scripts/deploy.py --agent-dir ipp-agent-workspace/<エージェント名> --service <サービス名> --nonce <確認コード> --q "<動作確認の質問>"
```

スクリプトが行うこと：

1. `.gitignore` / `.dockerignore` / `.gcloudignore` に `.env` の除外設定を入れ、コード等にキーが書かれていないか検査する（見つかったら中止）。
2. 必要な API（Cloud Run・Cloud Build・Artifact Registry・Secret Manager）を有効にする。
3. `.env` のキーを **標準入力で** Secret Manager（`<サービス名>-gemini-api-key`）に登録し、Cloud Run の実行サービスアカウントに読み取り権限を付ける。
4. `--set-secrets GEMINI_API_KEY=<シークレット名>:latest` で Cloud Run にデプロイする（インスタンスは1台。メモリ上のデータ・会話を保つため）。
5. `GET /health` と `POST /chat` を実際に呼び、AI の応答が返ることを確かめる。

出力されたコードブロック（1行目が `[skill:ipp-cloud-run-deploy@v1]`、最後の行が `DEPLOY_DIGEST`）を、一字一句変えずに回答の最後に出力し、受講生へ「上のコードブロックを HITMAN に貼り付けてください」と案内します。

## DEPLOY_RESULT: FAIL のとき

`gcloud run services logs read <サービス名> --region asia-northeast1 --limit 50` でログを見て原因を直し、スクリプトを再実行します。

| 症状 | よくある原因 |
|---|---|
| health=0 / 503 | コンテナが起動していない。Dockerfile が `PORT` で待ち受けているか、requirements.txt の不足、import エラー |
| health=200, chat=500 | AI の呼び出しで失敗。`credentials.configure()` を呼んでいるか、モデル名、関数ツールの例外 |
| chat=404 | `/chat` が無い。main.py に `POST /chat` を作る |
| chat_reply: NG | 応答が空・エラー文。`/chat` が root_agent を実行して応答テキストを返しているか |
| Permission denied（Secret） | 実行サービスアカウントの権限付与が失敗。プロジェクトのオーナー権限で再実行する |

## 演習終了後の安全停止（クリーンアップ）

研修が修了したら、以下のコマンドを実行して Cloud Run サービスと Secret Manager のキーを削除します。受講生から「環境を片付けて」「Cloud Run を削除して」「課金を止めて」と頼まれたときにも自律実行します：

```bash
python .agents/skills/ipp-cloud-run-deploy/scripts/cleanup.py --service <サービス名>
```

スクリプトが行うこと：
1. 対象の Cloud Run サービスを削除し、外部アクセスとインスタンス起動を停止する。
2. Secret Manager に登録された `<サービス名>-gemini-api-key` を完全に削除する。
3. クリーンアップ結果（`CLEANUP_RESULT: SUCCESS`）を出力する。
