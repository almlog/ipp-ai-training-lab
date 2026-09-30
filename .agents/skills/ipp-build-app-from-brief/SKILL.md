---
name: ipp-build-app-from-brief
description: IPP AI研修のステップ T-3（コースA）で、受講生が T-2 で合意した要件定義書 ipp-agent-workspace/project_brief.md のとおりに、AI エージェント（Google ADK）と Web アプリ（FastAPI＋自作の画面）を実装する。企画書の機能 F・画面 S・関数ツールをすべて作り、受講生自身の Gemini API キーを .env から安全に読み込む。「T-3 を実装して」「企画書どおりに作って」と頼まれたとき、HITMAN の T-3 プロンプトを貼られたときに使う。
---

# 企画書どおりにアプリを作る（コースA）

> [!NOTE]
> **HITMAN 使用証跡**: このスキルを使って作業した回答では、HITMAN 提出用コードブロックの1行目に `[skill:ipp-build-app-from-brief@v1]` と出力すること（実際にこのスキルを使った場合のみ）。T-3 の提出物はスモークテストの出力なので、証跡行はスモークテストのコードブロックの前に別のコードブロックで示してよい。

## 大原則

- **設計図は `ipp-agent-workspace/project_brief.md` だけ。** 企画書にある機能（F）・画面（S）・関数ツールをすべて作る。企画書にない機能を勝手に足したり、別の種類のアプリ（汎用チャット画面、WBS 管理、ログ解析など）に置き換えたりしない。
- **テンプレートの画面をコピーしない。** `build-agent-frontend` のチャット画面テンプレートや、`ipp-agent-workspace` にあるサンプル（`log_analyzer_bot`、`my_hitman`）を流用しない。画面は企画書の『3. 画面』から作る。
- **作れない・時間内に終わらない機能があったら、黙って省略しない。** 受講生に説明し、企画書の『7. 今回は作らないもの』へ移すことに合意をもらってから進める（企画書を更新する）。
- **認証情報は `ipp-secure-credentials` スキルのルールに従う。** キーの値を読まない・書かない・表示しない。

## フォルダ構成

```
ipp-agent-workspace/<エージェント名>/
  credentials.py      このスキルの scripts/credentials.py をそのままコピー（編集しない）
  agent.py            root_agent（Google ADK）と関数ツール
  store.py            データの保存・読み出し（画面の API と関数ツールの両方がここを使う）
  main.py             FastAPI：画面・データAPI・AIチャット
  static/index.html   企画書の画面（S1, S2 …）。必要なら static/*.js, *.css に分ける
  requirements.txt    fastapi, uvicorn, google-adk, google-genai など
  Dockerfile          Cloud Run 用（PORT 環境変数で待ち受け）
  .env / .env.example / .gitignore / .dockerignore / .gcloudignore   ← env_setup.py が作る
```

## 手順

1. **企画書を読む。** `ipp-agent-workspace/project_brief.md` の機能・画面・関数ツール・データ・動作確認をすべて確認する。
2. **認証情報の準備。** `ipp-secure-credentials` スキルの手順1（`env_setup.py`）を実行し、受講生に `.env` へキーを入れてもらう。`--check` で「設定済み」になるまで先へ進まない。
3. **credentials.py をコピー。** `.agents/skills/ipp-build-app-from-brief/scripts/credentials.py` を `<エージェント名>/credentials.py` にコピーする。`agent.py` と `main.py` の先頭（ほかの import より前）で次を書く：
   ```python
   import credentials
   credentials.configure()
   ```
4. **store.py（データ）。** 企画書の『5. データと保存先』どおりに保存・読み出しを実装する。画面の API と関数ツールは同じ store を使う（AI に頼んで登録したデータが画面に出る、画面で入力したデータを AI が参照できる）。
5. **agent.py（AI）。** 企画書の『4. 関数ツール』を、書かれたとおりの名前・引数で実装する。
   - ツールは引数に応じて実際に処理する（store の読み書き・計算・集計など）。固定値を返すダミーは不可。
   - `root_agent` の instruction に、どの場面でどのツールを使うかを書く。ツールの docstring に「いつ使うか」を書く。
   - モデルは `gemini-3.8-flash`（利用できない場合は `gemini-3.6-flash`）。
   - A2UI カードを使う場合は `enable-a2ui` スキルに従う（カードは表示専用）。
6. **main.py（サーバ）。** 次を必ず用意する：
   - `GET /health` → `{"status": "ok"}`（AI を呼ばない）
   - `POST /chat` → 入力 `{"message": "...", "user_id": "..."}`、出力 `{"reply": "<AIの応答テキスト>"}`。必ず root_agent を実行して応答する（LLM を通さない固定文は不可）。利用者ごとにセッションを使い回す。
   - 画面が使うデータ API（例: `GET /api/events`, `POST /api/events`）。
   - `static/` を配信する（`/` で画面が開く）。
7. **static/index.html（画面）。** 企画書の『3. 画面』の S1, S2 … をすべて作る。
   - **Google標準リッチUIの必須要件**:
     - 素のダサい・使えない HTML（ブラウザ標準スタイルのみ）は禁止。
     - Google Fonts（Noto Sans JP 等）と Material Symbols (`material-symbols-outlined`) を導入する。
     - Tailwind CSS（`<script src="https://cdn.tailwindcss.com"></script>`）を導入し、カード型レイアウト（`bg-white rounded-xl shadow-md p-6 border`）で美しく整理する。
     - レスポンシブ用メタタグ `<meta name="viewport" content="width=device-width, initial-scale=1.0">` を必ず設定する。
     - 外部 CDN ライブラリ（FullCalendar、Chart.js 等）を自由に活用してよい。
8. **UI 品質監査（ui_audit.py）。** 画面を作成後、以下のコマンドで Google 標準リッチ UI の基準（80点以上）をクリアしているか検査する：
   ```bash
   python .agents/skills/ipp-build-app-from-brief/scripts/ui_audit.py --agent-dir ipp-agent-workspace/<エージェント名>
   ```
   FAIL の場合は出力されたアドバイスに従って HTML/CSS を修正し、`UI_AUDIT_RESULT: PASS` になるまで直す。
9. **動かして確かめる。** `uvicorn main:app --port 8080`（`<エージェント名>` フォルダで）でローカル起動し、企画書の各機能の受け入れ条件を1つずつ確認して、結果を受講生に報告する。
10. **スモークテスト。** HITMAN の T-3 カードのコマンド（企画書の Q1・Q2 と確認コード入り）をそのまま実行する。FAIL なら出力を書き換えずに原因を直して再実行する。

## Dockerfile の例

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

`.env` は `.dockerignore` で除外されるため、コンテナには入りません。Cloud Run ではキーを Secret Manager から渡します（T-5 の `ipp-cloud-run-deploy` スキルが行う）。
