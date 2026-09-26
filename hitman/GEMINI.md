# HITMAN 設計ルール（このフォルダを変更するときは必ず守ること）

この節のルールは、過去に実際に起きた不具合（ループ、勝手な進行、受講生間の状態混在、会話履歴の消失、ダミー実装の合格）を防ぐためのものです。
ルールに反する変更が必要だと判断した場合は、実装せずに理由を説明して人間に確認してください。
各ルールの背景（実際に起きた不具合）とロードマップは `docs/hitman-fix-history-and-roadmap.md` にまとめてあります。変更前に「4. Antigravity への注意事項」を読んでください。

## 1. 研修の状態はセッションにだけ置く
- 研修の状態（モード、コース、現在ステップ、合否、企画アイデア、T-2 の上書き）は ADK の session.state にだけ保存する。読み書きは `app/agent.py` の `HitmanState` を使う（ツールは `tool_context` 経由）。
- モジュールのグローバル変数（`CURRENT_STEP`、`ACTIVE_TRAINING_COURSE`、`TRAINING_PARAMETERS` 等）や `TRAINING_SOP_ORIGINAL` / `TRAINING_SOP_HITMAN_CLONE` を実行時に書き換えない。全受講生で共有されてしまう。
- 受講生ごとの表示の違い（企画名、エージェント名など）は、`get_training_sop` がセッションの値から都度計算する。

## 2. ステップの進行は判定結果だけで決める
- 研修ステップが進むのは `apply_training_verdict`（`verify_step_output` の VERIFIED_APPROVED）だけ。コースの変更は `select_training_course` だけ。
- フロント（`frontend/static/index.html`）は `/chat` などが返す `state` をそのまま表示する。LLM の応答文を正規表現やキーワードで解析して、ステップ・合否・コースを決めない。
- localStorage の内容を読み込み時に書き換える「自己治癒」処理を追加しない。サーバの state が正で、`/api/session/sync` で同期する。

## 3. 会話の理解は LLM、ツールは記録と事実の提供
- T-2 の企画相談では、受講生の発言をツールに生のまま渡してキーワードで「確定・相談中・コース」を判定する実装にしない。LLM が要約と判断（`update_project_plan(idea_summary, status, course)`）を明示的に渡す。
- ツールは定型の会話文を返さない（LLM がそれを読み上げるだけになり、会話が固定化する）。返すのは記録内容・推奨スキル・次にやることなどの事実。
- 返答候補のボタンは LLM が `offer_choices` で毎ターン作る。フロントに固定のチップを追加しない。

## 4. 合格条件は客観的な証跡で判定する
- T-1: 新しい会話で `/ipp-skill-check` を実行した出力（`[skill:ipp-skill-check@v1]`）。
- T-2: コースAは企画の確定（`update_project_plan(status="confirmed", agent_name=...)`）が必須で、企画書に確定したエージェント名が含まれること。別企画のサンプルで合格させない。
- T-3: `ipp-agent-smoke-test` の出力。`SMOKE_JSON` の生データから再判定し、`SMOKE_DIGEST` で改変を検知する。T-2 合格時に発行した確認コード（`--nonce`）と企画どおりのフォルダ（`agent_dir`）が一致すること。
- コマンドの失敗（`fatal: could not read`、`[rejected]`、`No such file or directory` など）を含むログは、URL やファイル名があっても合格させない。
- 合格させるためにキーワードを追加して判定を緩めない。受講生が通れない場合は、手順・案内・スキルの側を直す。判定を変えたら「異常パターンが不合格になる」テストも追加する。

## 5. スキル（リポジトリ直下の `.agents/skills/`）
- Antigravity が読み込むのは「開いているワークスペース直下の `.agents/skills/`」だけで、新しい会話から有効になる（実機で確認済み）。
- `SKILL.md` の frontmatter は YAML として正しく書き、`name` はフォルダ名と一致させる。各スキルは使用証跡 `[skill:<name>@v1]` の出力ルールを持つ。
- HITMAN・画面・マニュアルから参照するスキルは、リポジトリに実在するものだけにする。

## 6. テストとサンプル
- 変更後は `uv run pytest tests/unit` を実行し、全件合格を確認する。テストを削除・緩和して通す変更は禁止。
- 「🧪ログ注入」のサンプル（`index.html` の `TEST_EVIDENCES`＝正常、`TEST_EVIDENCES_NG`＝異常）は実際のコマンド出力をもとに作る。正常は合格、異常は不合格になることを `test_skill_references.py` が検査する。
- T-2（コースA）/T-3 の注入ログは受講生の企画・確認コードに紐づくため、`build_demo_evidence`（`/api/training/demo-evidence`）で生成する。Cloud Run では既定で無効（`HITMAN_DEMO_EVIDENCE=1` で有効）。受講生が合格ログを作れる経路を増やさない。
- ツールやサンプルの成果物をダミー実装（引数を無視した固定値、LLM を通さない `/chat`、固定値だけを確認するテスト）で作らない。

## 7. 環境と秘密情報
- 自分の環境で動いたことを、受講生の環境で動く根拠にしない。受講生の手順（クローン先・開くフォルダ・新しい会話）どおりに再現して確認する。仕様が不明なことは推測で断定せず、実機で確かめる。
- API キーは `hitman/.env` にだけ置く。コマンド・ログ・チャット・コミットにキーの値を書かない。スクリプトは `.env` から読み込み、キーを表示しない。
- 例外を握りつぶして「動いているように見える」フォールバックにしない。必ずログに出す。

---

# Coding Agent Guide

## Prerequisites

Install the CLI (one-time):
```bash
uv tool install google-agents-cli
```

---

## Development Phases

### Phase 1: Understand Requirements
Before writing any code, understand the project's requirements, constraints, and success criteria.

### Phase 2: Build and Implement
Implement agent logic in `app/`. Use `agents-cli playground` for interactive testing. Iterate based on user feedback.

### Phase 3: The Evaluation Loop (Main Iteration Phase)
Start with 1-2 eval cases, run `agents-cli eval run`, iterate by making changes and rerunning it until satisfied. Expect 5-10+ iterations. Once you have a baseline, reach for `agents-cli eval compare` (regression diffs), `agents-cli eval analyze` (cluster failure modes), and `agents-cli eval optimize` (auto-tune prompts). See the **Evaluation Guide** for metrics, dataset schema, LLM-as-judge config, and common gotchas.

### Phase 4: Pre-Deployment Tests
Run `uv run pytest tests/unit tests/integration`. Fix issues until all tests pass.

### Phase 5: Deploy to Dev
**Requires explicit human approval.** Run `agents-cli deploy` only after user confirms. See the **Deployment Guide** for details.

### Phase 6: Production Deployment
Ask the user: Option A (simple single-project) or Option B (full CI/CD pipeline with `agents-cli infra cicd`).

## Development Commands

| Command | Purpose |
|---------|---------|
| `agents-cli playground` | Interactive local testing |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests |
| `agents-cli eval dataset synthesize` | Synthesize multi-turn eval scenarios for your agent |
| `agents-cli eval run` | Run the agent over the eval dataset and grade the traces |
| `agents-cli eval generate` / `agents-cli eval grade` | Decoupled form: produce traces, then grade them |
| `agents-cli eval compare` | Compare two grade-results files (regression check) |
| `agents-cli eval analyze` | Cluster failure modes from grade results |
| `agents-cli eval metric list` | List built-in metrics available in the SDK |
| `agents-cli eval optimize` | Auto-tune agent prompts using eval data |
| `agents-cli lint` | Check code quality |
| `agents-cli infra single-project` | Set up project infrastructure (Terraform) |
| `agents-cli deploy` | Deploy to dev |
| `agents-cli scaffold enhance` | Add deployment target or CI/CD to project |
| `agents-cli scaffold upgrade` | Upgrade project to latest version |

---

## Operational Guidelines for Coding Agents

- **Code preservation**: Only modify code directly targeted by the user's request. Preserve all surrounding code, config values (e.g., `model`), comments, and formatting.
- **NEVER change the model** unless explicitly asked.
- **Model 404 errors**: Fix `GOOGLE_CLOUD_LOCATION` (e.g., `global` instead of `us-east1`), not the model name.
- **ADK tool imports**: Import the tool instance, not the module: `from google.adk.tools.load_web_page import load_web_page`
- **Run Python with `uv`**: `uv run python script.py`. Run `agents-cli install` first.
- **Stop on repeated errors**: If the same error appears 3+ times, fix the root cause instead of retrying.
- **Terraform conflicts** (Error 409): Use `terraform import` instead of retrying creation.
