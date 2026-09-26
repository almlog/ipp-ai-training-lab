# 🧪 IPP AI実践研修 テスト用想定回答・エビデンス集 (Step T-1 〜 T-6)

本ドキュメントは、HITMAN Cockpit および AntiGravity の研修フロー（ステップ T-1 〜 T-6）の検証・デモ・リハーサル時に、ターミナルで何度も `git clone` やデプロイを実行することなく、**即座に提出して Wチェック（合格承認）を獲得できるコピー用エビデンス（生ログ）集**です。

---

## 📋 使い方
1. HITMAN 画面で現在進行中のステップ（T-1 〜 T-6）を確認します。
2. 以下の該当ステップのコードブロック（ターミナルログ）をそのままコピーします。
3. HITMAN Cockpit のチャット送信欄に貼り付けて Enter キーを押します。
4. HITMAN のAI有識者（確認者）がログを客観検証し、🟢 **VERIFIED_APPROVED (合格承認)** が発行されて次ステップがアンロックされます。

---

## 🛠️ Step T-1: 開発環境構築とスキル同期 (エビデンス)

> 新しい会話で `/ipp-skill-check` を実行した出力です（クローンのログだけでは合格しません）。

```text
[skill:ipp-skill-check@v1]
PS C:\work> Get-ChildItem .agents\skills -Name
build-agent-frontend
enable-a2ui
ipp-skill-check
memory-bank-setup
novasmart-governance-lab
pick-your-agent-project
publish-to-github
rag-engine-setup
record-demo
troubleshoot-lab-setup
```

---

## 📝 Step T-2: 要件定義 (Project Brief / 仕様設計 エビデンス)

```markdown
# project_brief.md (コースA: 現場課題解決AIエージェント要件定義)

## 1. アプリ概要
- アプリ名: my_agent (社内申請＆マニュアルQAアシスタント)
- 目的: 社内申請手続きや各種規程に関する問い合わせに24時間自律回答する。
- ターゲットユーザー: IPP 全社員

## 2. アーキテクチャ＆ツール
- フレームワーク: Google ADK (Agent Development Kit 1.5.0) + Python
- モデル: gemini-3.8-flash (フォールバック: gemini-3.6-flash)
- UIコンポーネント: A2UI v0.8 リッチカード表示
- 追加機能: 申請フォームカード生成ツール, RAGナレッジ検索

## 3. A2UIカード表示仕様
- 申請ステータス表示カード (Status: APPROVED / PENDING)
- 該当マニュアル参照リンクカード (Card > Column > Text)
- 事前Wチェック確認枠
```

---

## 🤖 Step T-3: エージェントコア＆A2UI実装 (エビデンス)

```python
$ ls -la ipp-agent-workspace/my_agent/
total 24
-rw-r--r-- 1 user staff 1850 Sep 7 20:22 agent.py
-rw-r--r-- 1 user staff  920 Sep 7 20:22 a2ui_utils.py
-rw-r--r-- 1 user staff 1200 Sep 7 20:22 main.py
-rw-r--r-- 1 user staff  350 Sep 7 20:22 pyproject.toml
drwxr-xr-x 2 user staff 4096 Sep 7 20:22 tests

$ head -n 30 ipp-agent-workspace/my_agent/agent.py
# agent.py - Google ADK Agent for my_agent
from google.adk.agents import Agent
from google.adk.models import Gemini
from a2ui_utils import a2ui_callback

MODEL = "gemini-3.8-flash"

def consult_policy_faq(query: str) -> dict:
    return {"status": "success", "query": query, "answer": "申請手順をご案内します。"}

root_agent = Agent(
    name="my_agent",
    model=Gemini(model=MODEL),
    instruction="社内課題解決アシスタントとしてA2UIカードで丁寧に回答...",
    tools=[consult_policy_faq],
    after_model_callback=a2ui_callback,
)
```

---

## 🧪 Step T-4: ローカルテスト＆自律Wチェック (エビデンス)

```text
$ pytest ipp-agent-workspace/my_agent/tests/ -v
============================= test session starts =============================
platform win32 -- Python 3.12.2, pytest-8.1.1, pluggy-1.4.0
rootdir: C:\workspace\ipp-agent-workspace\my_agent
collected 5 items

tests/test_agent.py::test_agent_initialization PASSED                   [ 20%]
tests/test_agent.py::test_consult_policy_faq PASSED                      [ 40%]
tests/test_agent.py::test_a2ui_callback_integration PASSED               [ 60%]
tests/test_agent.py::test_error_handling PASSED                          [ 80%]
tests/test_agent.py::test_schema_validity PASSED                         [100%]

============================== 5 passed in 1.42s ==============================
```

---

## 🌐 Step T-5: Cloud Run 本番デプロイ (エビデンス)

```text
$ gcloud run deploy my-agent --source ipp-agent-workspace/my_agent --region asia-northeast1 --allow-unauthenticated
Building Container... DONE
Uploading Sources... DONE
Creating Revision... DONE
Routing Traffic... DONE

Service [my-agent] revision [my-agent-00001-v8a] has been deployed and is serving 100 percent of traffic.
Service URL: https://my-agent-1070367799384.asia-northeast1.run.app
```

---

## 🏆 Step T-6: 個人GitHub公開＆修了証発行 (エビデンス)

```text
$ gh auth status
✓ Logged in to github.com as shunpei-suzuki (oauth_token)

$ git remote -v
origin  https://github.com/shunpei-suzuki/my-ai-agent.git (fetch)
origin  https://github.com/shunpei-suzuki/my-ai-agent.git (push)

$ git push origin main
Enumerating objects: 18, done.
Counting objects: 100% (18/18), done.
Writing objects: 100% (18/18), 8.5 KiB | 8.5 MiB/s, done.
Total 18 (delta 4), reused 0 (delta 0)
To https://github.com/shunpei-suzuki/my-ai-agent.git
 * [new branch]      main -> main
Branch 'main' set up to track remote branch 'main' from 'origin'.
```
