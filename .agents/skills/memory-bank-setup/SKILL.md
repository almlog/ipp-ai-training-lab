---
name: memory-bank-setup
description: >
  Add durable cross-session long-term memory to an ADK agent using either
  (A) Local durable SQLite storage (recommended for lab environments, requires only GEMINI_API_KEY),
  or (B) Vertex AI Memory Bank on Agent Platform (requires Google Cloud Reasoning Engine).
  Use when the user wants to "add memory", "remember user facts/preferences",
  "remember across conversations", or make an agent personalize its replies over time.
---

# 長期記憶（Memory）統合ガイド（ローカル SQLite / Vertex AI）

> [!NOTE]
> **HITMAN 使用証跡**: このスキルを使って作業した回答では、HITMAN 提出用コードブロックの1行目に `[skill:memory-bank-setup@v1]` と出力すること（実際にこのスキルを使った場合のみ）。

受講生の環境と要件に合わせて、**2つの長期記憶パターン** を選択できます：

1. **【パターン A: 推奨】ローカル SQLite による長期記憶ツール**  
   - **前提条件**: `GEMINI_API_KEY` のみ（Google Cloud の有料インフラ構築は一切不要）。
   - **特徴**: `remember_user_fact` と `recall_user_facts` の2つの関数ツールにより、ユーザーの好みや指示をローカル DB に保存・復元。コンテナ内やローカル PC で確実に永続化。
2. **【パターン B: エンタープライズ】Vertex AI Memory Bank（Agent Platform）**  
   - **前提条件**: Google Cloud プロジェクト、Reasoning Engine インスタンス作成（`agentengine://...`）。
   - **特徴**: クラウドマネージドなセッション横断記憶抽出エンジン。

---

## 🚀 パターン A: ローカル SQLite による長期記憶（APIキーのみで動作）

Google Cloud 上に Reasoning Engine を立ち上げることなく、受講生の `GEMINI_API_KEY` だけで「会話が終わってもユーザーの名前や好みを覚えているエージェント」を実装する最も確実な方法です。

### 1. 記憶ツールの実装（agent.py 内）

```python
import sqlite3
from pathlib import Path
from google.adk.agents import Agent

DB_PATH = Path("user_memory.db")

def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return conn

def remember_user_fact(key: str, value: str) -> str:
    """ユーザーに関する重要な情報、設定、好み（キーと値）を長期記憶DBに保存します。
    
    Args:
        key: 記憶の分類または項目名（例: 'user_role', 'preferred_format', 'hobby'）
        value: 記憶する具体的な内容（例: '経理部マネージャー', '表形式で簡潔に出力', 'サッカー'）
    """
    conn = _init_db()
    with conn:
        conn.execute("""
            INSERT INTO memories (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key.strip(), value.strip()))
    return f"【記憶完了】項目 `{key}` を `{value}` として保存しました。"

def recall_user_facts(query: str = "") -> str:
    """これまでに保存されたユーザーの長期記憶（設定・好み・属性）を検索・取得します。
    
    Args:
        query: 検索キーワード（省略時はすべての記憶を一覧表示）
    """
    conn = _init_db()
    cursor = conn.cursor()
    if query:
        cursor.execute("SELECT key, value FROM memories WHERE key LIKE ? OR value LIKE ?", (f"%{query}%", f"%{query}%"))
    else:
        cursor.execute("SELECT key, value FROM memories ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    if not rows:
        return "保存された長期記憶はありません。"
    
    items = [f"- {k}: {v}" for k, v in rows]
    return "【保存されている長期記憶】\n" + "\n".join(items)

# ADK エージェントに関数ツールとして登録
root_agent = Agent(
    model="gemini-2.5-flash",
    name="memory_agent",
    instruction=(
        "あなたはパーソナルAIアシスタントです。"
        "ユーザーが名前、所属、好み、指示を伝えた場合は、必ず remember_user_fact ツールを使って保存してください。"
        "また、ユーザーへの回答時には必要に応じて recall_user_facts を呼び出し、過去に保存された好みに沿って回答してください。"
    ),
    tools=[remember_user_fact, recall_user_facts],
)
```

### 2. 即時動作確認スクリプト

同梱のスクリプトで、記憶の保存と呼び出しをターミナルからテストできます：

```bash
python .agents/skills/memory-bank-setup/scripts/local_memory_tool.py --remember "user_name" "山田太郎"
python .agents/skills/memory-bank-setup/scripts/local_memory_tool.py --recall
```

---

## 🏛️ パターン B: Vertex AI Memory Bank（Reasoning Engine）

Google Cloud Agent Platform のフルマネージド長期記憶エンジンです。

```
Write (per turn):  session events ─▶ after_agent_callback ─▶ add_session_to_memory()
                                    ─▶ Memory Bank extracts + stores durable facts

Read  (per turn):  PreloadMemoryTool ─▶ search_memory(user_id) at turn start
                                      ─▶ relevant memories injected into the system instruction
```

Two moving parts:
1. **The agent code** — a memory *tool* (reads) + a *callback* (writes). Same for
   every runtime.
2. **A memory service** pointed at a **Memory Bank instance**. This is the part
   that changes between local and deployed, and the part `agents-cli` does **not**
   set up for you.

## The one thing that trips people up

**A "Memory Bank instance" is just an Agent Engine (Reasoning Engine)
instance.** You create one with `client.agent_engines.create()`; its resource
name is `projects/<p>/locations/<loc>/reasoningEngines/<ID>` and `<ID>` is the
Memory Bank ID you pass everywhere as `agentengine://<ID>`.

Consequences:
- Memory Bank is a **managed cloud resource** — you cannot see real, persisted
  memories with a purely in-memory local run. ADK defaults to
  `InMemoryMemoryService` unless you explicitly point it at a Memory Bank
  instance.
- **`agents-cli deploy` does not wire a memory service.** It configures a
  *session* service on Agent Runtime, but leaves the memory service at ADK's
  default. Adding the tool + callback is necessary but **not sufficient** — you
  must also point a memory service at a Memory Bank instance (steps below).
- Because it's a cloud resource, do memory work **after** (or alongside) a first
  deploy, or create a standalone instance for local testing — not before any
  Agent Engine exists.

## Prerequisites (one-time)

```bash
PROJECT=your-project-id
LOCATION=us-central1          # use a Memory-Bank-supported region
gcloud config set project "$PROJECT"
gcloud services enable aiplatform.googleapis.com --project="$PROJECT"
gcloud auth application-default login   # already done if you logged in via `agy`
```

Memory Bank runs in specific regions — see
https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/agent-locations.
Keep `GOOGLE_CLOUD_LOCATION` consistent with the region you create the instance in.

## Step 1 — wire the agent (tool + callback)

Edit the agent definition (in an `agents-cli` project this is `app/agent.py`).
Add a **memory-generation callback** and a **memory tool**:

```python
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
# Alternative tool: from google.adk.tools.load_memory_tool import LoadMemoryTool


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    instruction=(
        "You are a helpful assistant. You remember the user's stated "
        "preferences and facts from previous conversations and use them to "
        "personalize your responses."
    ),
    # READ: PreloadMemoryTool retrieves memories at the start of every turn and
    # injects them into the system instruction (no explicit tool call needed).
    # Use LoadMemoryTool() instead if you want the model to fetch on demand.
    tools=[PreloadMemoryTool()],
    after_agent_callback=generate_memories_callback,
)
```

That's the whole agent-side change. It is runtime-agnostic — the same code works
locally and deployed. **`add_session_to_memory()` and the tools are no-ops
against an in-memory service**, so they only produce durable memories once a real
Memory Bank instance is wired in (next steps).

> Only send salient turns to memory. `add_session_to_memory()` at the end of a
> turn is the simplest; for finer control use
> `callback_context.add_events_to_memory(events=...)` with a subset of events.

## Step 2 — create a Memory Bank instance

If you have **already deployed** with `agents-cli`, you already have an Agent
Engine — you can reuse its ID as the Memory Bank ID (skip to Step 3). Otherwise
create a standalone instance (`scripts/create_memory_bank.py`):

```python
import vertexai

PROJECT_ID = "your-project-id"
LOCATION   = "us-central1"

client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

# A Memory Bank instance IS an Agent Engine instance. Default config is fine
# for the lab; it extracts general user facts/preferences automatically.
memory_bank = client.agent_engines.create()

resource_name = memory_bank.api_resource.name       # projects/.../reasoningEngines/NNN
memory_bank_id = resource_name.split("/")[-1]        # NNN  ← use this everywhere
print("MEMORY_BANK_ID:", memory_bank_id)
print("resource name :", resource_name)
```

Save the printed `MEMORY_BANK_ID`. (To customize *which* topics are extracted —
`USER_PERSONAL_INFO`, `USER_PREFERENCES`, `EXPLICIT_INSTRUCTIONS`,
`KEY_CONVERSATION_DETAILS` — see the "Configure your Memory Bank instance"
section of the Set up docs; the default config needs no customization.)

## Step 3 — point a memory service at the instance

The memory service must be given the `agentengine://<MEMORY_BANK_ID>` URI. Pick
the row that matches how the agent runs:

| Runtime | How to wire the memory service |
|---|---|
| **Local ADK Web** (fastest to test) | `adk web --memory_service_uri=agentengine://MEMORY_BANK_ID` |
| **Deployed on Agent Runtime** | Set the memory service in the app (below) so the deployed container uses Memory Bank, not the in-memory default |
| **Local `Runner` / script** | `VertexAiMemoryBankService(project=..., location=..., agent_engine_id=MEMORY_BANK_ID)` passed to `Runner(memory_service=...)` |

### Local test (recommended first)

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
# Run from the folder that contains the agent package (e.g. the project root
# with app/ inside). This overrides ADK's in-memory default.
adk web --memory_service_uri=agentengine://MEMORY_BANK_ID
```

`agents-cli playground` runs `adk web` but does not forward
`--memory_service_uri`, so for a *real* Memory Bank locally run `adk web`
directly with the flag.

### Deployed on Agent Runtime (agents-cli project)

`agents-cli deploy` will not attach a memory service, so set one explicitly in
the app so the deployed container uses Memory Bank. In the ADK app definition
(the `AdkApp` / `get_fast_api_app` wiring — see the `google-agents-cli-deploy`
and `google-agents-cli-adk-code` skills for the exact file in this project
version), provide a memory-service builder:

```python
from google.adk.memory import VertexAiMemoryBankService

def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project="your-project-id",
        location="us-central1",
        agent_engine_id="MEMORY_BANK_ID",   # reuse the deployed engine's ID, or a standalone one
    )
# Pass memory_service_builder=memory_bank_service_builder to AdkApp,
# or --memory_service_uri=agentengine://MEMORY_BANK_ID to the ADK deploy command.
```

Then redeploy. Confirm the deployed agent actually persists memories (Step 4) —
don't assume the default did it.

## Step 4 — verify

1. **Talk to the agent** (local ADK Web or the deployed playground): state a
   durable fact, e.g. *"Remember that I'm allergic to penicillin."*
2. **Start a NEW session** and ask something that needs it — the agent should
   recall it without being reminded.
3. **See the stored memory in the Console:**
   https://console.cloud.google.com/agent-platform/memory-bank
   (Vertex AI → Agent Engines → your instance → Memory Bank.) Allow a few
   seconds — extraction runs in the background after the turn.

## Troubleshooting

- **Memories never persist / nothing in the Console** → you're on the default
  `InMemoryMemoryService`. The tool + callback alone don't create a bank; you
  must pass `--memory_service_uri=agentengine://<ID>` (local) or set
  `VertexAiMemoryBankService` in the deployed app. This is the #1 cause.
- **Works locally, not when deployed** → `agents-cli deploy` didn't wire a
  memory service; add the `memory_service_builder` / `memory_service_uri` and
  redeploy (Step 3, deployed row).
- **Recalls in the same session but not across sessions** → you're seeing
  *session state*, not memory. Confirm `PreloadMemoryTool` is in `tools` and the
  `after_agent_callback` is set, and that both sessions use the **same
  `user_id`** (memories are scoped by `user_id` + `app_name`).
- **`NOT_FOUND` / permission errors on the memory service** → the
  `MEMORY_BANK_ID` region must match `GOOGLE_CLOUD_LOCATION`, and it must be a
  Memory-Bank-supported region; the caller/service account needs
  `roles/aiplatform.user`.
- **`'await' outside function`** in a standalone script → wrap async calls in
  `asyncio.run(...)`; ADK is async-first.
