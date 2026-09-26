# HITMAN 設計ルール（このフォルダを変更するときは必ず守ること）

この節のルールは、過去に実際に起きた不具合（ループ、勝手な進行、受講生間の状態混在、会話履歴の消失、ダミー実装の合格）を防ぐためのものです。
ルールに反する変更が必要だと判断した場合は、実装せずに理由を説明して人間に確認してください。

## 1. 研修の状態はセッションにだけ置く
- 研修の状態（モード、コース、現在ステップ、合否、企画アイデア、T-2 の上書き）は ADK の session.state にだけ保存する。読み書きは `app/agent.py` の `HitmanState` を使う（ツールは `tool_context` 経由）。
- モジュールのグローバル変数（`CURRENT_STEP`、`ACTIVE_TRAINING_COURSE`、`TRAINING_PARAMETERS` 等）や `TRAINING_SOP_ORIGINAL` / `TRAINING_SOP_HITMAN_CLONE` を実行時に書き換えない。全受講生で共有されてしまう。
- 受講生ごとの表示の違い（企画名、エージェント名など）は、`get_training_sop` がセッションの値から都度計算する。

## 2. ステップの進行は判定結果だけで決める
- 研修ステップが進むのは `apply_training_verdict`（`verify_step_output` の VERIFIED_APPROVED）だけ。コースの変更は `select_training_course` だけ。
- フロント（`frontend/static/index.html`）は `/chat` などが返す `state` をそのまま表示する。LLM の応答文を正規表現やキーワードで解析して、ステップ・合否・コースを決めない。
- localStorage の内容を読み込み時に書き換える「自己治癒」処理を追加しない。サーバの state が正で、`/api/session/sync` で同期する。

## 3. 合格条件は客観的な証跡で判定する
- T-1: 新しい会話で `/ipp-skill-check` を実行した出力（`[skill:ipp-skill-check@v1]`）。
- T-3: `ipp-agent-smoke-test` の出力。`SMOKE_JSON` の生データから再判定し、`SMOKE_DIGEST` で改変を検知する。
- 合格させるためにキーワードを追加して判定を緩めない。受講生が通れない場合は、手順・案内・スキルの側を直す。

## 4. スキル（リポジトリ直下の `.agents/skills/`）
- Antigravity が読み込むのは「開いているワークスペース直下の `.agents/skills/`」だけで、新しい会話から有効になる（実機で確認済み）。
- `SKILL.md` の frontmatter は YAML として正しく書き、`name` はフォルダ名と一致させる。各スキルは使用証跡 `[skill:<name>@v1]` の出力ルールを持つ。
- HITMAN・画面・マニュアルから参照するスキルは、リポジトリに実在するものだけにする。

## 5. テストとサンプル
- 変更後は `uv run pytest tests/unit` を実行し、全件合格を確認する。テストを削除・緩和して通す変更は禁止。
- 「ログ注入」用のサンプルログ（`index.html` の `TEST_EVIDENCES`、`knowledge/training_test_evidences.md`）は、実際のコマンド出力から作る。作り物のログを手で書かない（`test_skill_references.py` が現行の判定で T-1〜T-6 を通るか検査する）。

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
