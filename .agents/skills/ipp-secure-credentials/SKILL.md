---
name: ipp-secure-credentials
description: IPP AI研修で、受講生自身の Gemini API キーを安全に使うための準備と検査。エージェントやアプリのフォルダに .env / .env.example を用意し、.gitignore・.dockerignore・.gcloudignore で .env を除外し、キーが平文でコード・ログ・Git に混入していないかを検査する。「APIキーを設定したい」「.env を作って」「キーが漏れていないか確認して」と頼まれたとき、または T-3 の実装開始時・T-5 のデプロイ前・T-6 の公開前に必ず使う。
---

# 認証情報を安全に扱う（IPP 研修の必須ルール）

> [!NOTE]
> **HITMAN 使用証跡**: このスキルを使って作業した回答では、HITMAN 提出用コードブロックの1行目に `[skill:ipp-secure-credentials@v1]` と出力すること（実際にこのスキルを使った場合のみ）。

受講生は各自の Gemini API キーを持って参加します。作るツールは **必ず受講生自身のキー** を使い、キーは **`.env` ファイルにだけ** 置きます。

## 絶対に守ること（例外なし）

1. **キーの値を見ない・書かない・表示しない。** あなた（AI）は `.env` を開いて読んだり、`cat .env` / `type .env` / `Get-Content .env` / `echo $GEMINI_API_KEY` を実行したりしてはいけません。キーの有無の確認は `env_setup.py --check` だけで行います（値は表示されません）。
2. **キーは受講生がエディタで `.env` に直接書き込む。** チャット欄に貼ってもらわない。受講生がチャットにキーを貼った場合は、使わずに「漏えいしたキーとして無効化・再発行してください」と案内する。
3. **コマンドラインにキーを埋め込まない。** `$env:GEMINI_API_KEY="..."`、`export GEMINI_API_KEY=...`、`gcloud run deploy --set-env-vars GEMINI_API_KEY=...` はすべて禁止（実行履歴・デプロイログ・Cloud Run の設定画面に平文で残る）。
4. **コードにキーを書かない。** プログラムは `.env`（ローカル）または環境変数（Cloud Run では Secret Manager から注入）から読む。
5. **`.env` は Git・コンテナに入れない。** `.gitignore`・`.dockerignore`・`.gcloudignore` に `.env` を入れる（`env_setup.py` が自動で行う）。
6. **HITMAN に提出するログにキーを含めない。** HITMAN はキーを含むログを必ず不合格にします。

## 手順

### 1. `.env` の準備（T-3 の実装開始時）

ワークスペースのルートで実行します：

```bash
python .agents/skills/ipp-secure-credentials/scripts/env_setup.py --agent-dir ipp-agent-workspace/<エージェント名>
```

- `<エージェント名>/.env.example`（値は空）と `<エージェント名>/.env`（無ければ値が空のものを作成）を用意します。
- `.gitignore`・`.dockerignore`・`.gcloudignore` に `.env` を追記します。
- 最後に `GEMINI_API_KEY: 未設定` または `GEMINI_API_KEY: 設定済み` を表示します（値は表示しません）。

`未設定` と表示されたら、受講生に次のとおり案内して待機します：

> エディタで `ipp-agent-workspace/<エージェント名>/.env` を開き、`GEMINI_API_KEY=` の後ろにご自身の Gemini API キーを貼り付けて保存してください。キーはチャットには貼らないでください。保存したら「設定しました」と教えてください。

「設定しました」と言われたら、`env_setup.py --agent-dir ... --check` を実行して `設定済み` になったことを確認してから次へ進みます。

### 2. プログラムからの読み込み方

エージェント・アプリは次の順でキーを探します（`ipp-build-app-from-brief` スキルの `credentials.py` がこの処理を行う）：

1. 環境変数 `GEMINI_API_KEY` または `GOOGLE_API_KEY`（Cloud Run では Secret Manager から注入される）
2. アプリのフォルダの `.env`

`AQ.` で始まるキー（Vertex AI Express）は自動で Vertex AI 接続に切り替えます。

### 3. 漏えい検査（T-5 のデプロイ前・T-6 の公開前）

```bash
python .agents/skills/ipp-secure-credentials/scripts/secret_scan.py ipp-agent-workspace/<エージェント名>
```

- `.env` 以外のファイル（コード・設定・README・Dockerfile 等）にキーが書かれていないか、`.env` が除外設定されているかを検査します。
- `SECRET_SCAN: PASS` 以外なら、該当ファイル（パスと種類だけが表示され、値は表示されない）を直してから再実行します。キーをコードに書いてしまっていた場合は、そのキーを無効化・再発行してください。

## 漏えいしたときの対応

キーがチャット・ログ・Git・コマンド履歴に出てしまったら、**消すだけでは不十分**です。Google AI Studio の API キー画面で該当キーを削除し、新しいキーを作って `.env` に入れ直してください。
