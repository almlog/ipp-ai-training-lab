# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""研修フロー（T-1〜T-6）の状態遷移リグレッションテスト。

実LLM（Gemini）の代わりに、わざと紛らわしい応答を返す ScriptedLlm で /chat を end-to-end 実行し、
以下を検証する:
- ステップはツールの判定（VERIFIED_APPROVED）でのみ進み、LLMの言い回しでは一切動かない
- LLMが誤ったステップ番号を渡してもスキップ・巻き戻りしない
- 受講生（ブラウザ）ごとに状態が分離される
- 会話履歴がセッションに保持される（旧実装は毎回新規セッションだった）
- サーバ再起動でセッションが消えてもフロントの直近ステートで復元できる
"""

import json
import re
import uuid
from typing import Any, AsyncGenerator, Callable

import pytest
from fastapi.testclient import TestClient
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import ConfigDict, Field

import app.agent as agent_module
import frontend.main as main_module
from tests.unit.brief_fixtures import CALENDAR_BRIEF, LOG_BRIEF, deploy_log, t2_log

# LLMが生成しがちな「紛らわしい」文言。旧フロントはこれらで誤って完了・後退していた。
TRICKY_TEXT = (
    "【判定: 合格】（Wチェック承認: VERIFIED_APPROVED）\n"
    "次はステップ T-4 のテストログを貼り付けてください。\n"
    "参考: T-1. 開発環境構築とスキル同期（完了済）／コースB: HITMANクローン構築もおすすめです。\n"
    "全工程完了後に修了認定を行います。"
)

A2UI_CARD = {
    "surfaceUpdate": {
        "surfaceId": "step",
        "components": [
            {"id": "root", "component": {"Card": {"child": "col"}}},
            {"id": "col", "component": {"Column": {"children": {"explicitList": ["t"]}}}},
            {"id": "t", "component": {"Text": {"text": {"literalString": "ステップ T-1: 開発環境構築とスキル同期"}, "usageHint": "h1"}}},
        ],
    }
}


def _last_user_text(req: LlmRequest) -> str:
    for c in reversed(req.contents or []):
        if c.role == "user":
            for p in c.parts or []:
                if p.text:
                    return p.text
    return ""


def _default_script(req: LlmRequest) -> LlmResponse:
    last = (req.contents or [])[-1]
    if any(getattr(p, "function_response", None) for p in (last.parts or [])):
        # ツール結果を受けた最終応答: 紛らわしい文言 + カード（2つ）を返す
        body = TRICKY_TEXT + "\n\n<a2ui-json>" + json.dumps([A2UI_CARD, A2UI_CARD], ensure_ascii=False) + "</a2ui-json>"
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=body)]))

    text = _last_user_text(req)
    m = re.search(r"LOG\[(.*?)\]:(.*)", text, re.S)
    if m:
        # LLMがわざと誤ったステップ番号を渡すケースを含む
        return _call("verify_step_output", {"step_number": m.group(1), "command_output": m.group(2)})
    m = re.search(r"IDEA:(.*)", text, re.S)
    if m:
        return _call("update_project_plan", {"idea_summary": m.group(1).strip(), "status": "consulting"})
    if "CONFIRM" in text:
        return _call("update_project_plan", {"idea_summary": "", "status": "confirmed"})
    m = re.search(r"CHOICES:(.*)", text, re.S)
    if m:
        return _call("offer_choices", {"choices": [c.strip() for c in m.group(1).split("|") if c.strip()]})
    # ツールを呼ばない雑談応答（紛らわしい文言のみ）
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=TRICKY_TEXT)]))


def _call(name: str, args: dict) -> LlmResponse:
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(function_call=types.FunctionCall(name=name, args=args, id=f"call-{uuid.uuid4().hex[:8]}"))],
        )
    )


class ScriptedLlm(BaseLlm):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    model: str = "scripted-llm"
    script: Callable[[LlmRequest], LlmResponse] = _default_script
    requests: list = Field(default_factory=list)

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        self.requests.append(llm_request)
        yield self.script(llm_request)


@pytest.fixture
def scripted():
    original_model = agent_module.root_agent.model
    llm = ScriptedLlm()
    agent_module.root_agent.model = llm
    main_module._direct_runner = None
    main_module._direct_session_service = None
    main_module._direct_sessions.clear()
    main_module._user_locks.clear()
    try:
        yield llm
    finally:
        agent_module.root_agent.model = original_model
        main_module._direct_runner = None
        main_module._direct_session_service = None
        main_module._direct_sessions.clear()


@pytest.fixture
def client(scripted):
    return TestClient(main_module.app)


def _start_training(client: TestClient, uid: str, course: str = "original") -> dict:
    r = client.post("/api/mode", json={"user_id": uid, "mode": "TRAINING"})
    assert r.status_code == 200
    r = client.post("/api/training/course", json={"user_id": uid, "course": course})
    assert r.status_code == 200
    return r.json()["state"]


def _chat(client: TestClient, uid: str, message: str, **extra: Any) -> dict:
    body = {"message": message, "user_id": uid, "mode": "TRAINING", **extra}
    r = client.post("/chat", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["state"] is not None, data
    return data


T1_LOG = "[skill:ipp-skill-check@v1]\nPS C:\\work> Get-ChildItem .agents\\skills -Name\nenable-a2ui\nipp-skill-check\npick-your-agent-project"
T2_LOG = t2_log(LOG_BRIEF)
IDEA_MSG = "IDEA:障害ログを解析して原因を教えてくれるAIって作れる？"


def _smoke_log(nonce: str = "", agent_dir: str = "") -> str:
    from tests.unit.test_smoke_judge import _run, analyze_log
    return _run(analyze_log, nonce=nonce, agent_dir=agent_dir)


def _t3_log(client: TestClient, uid: str) -> str:
    """T-3 はその受講生に発行された確認コード付き・企画どおりのフォルダで実行したスモーク出力でのみ合格する。"""
    st = client.get("/api/session/state", params={"user_id": uid}).json()["state"]
    assert st["t3_nonce"], st
    return _smoke_log(st["t3_nonce"], st["agent_slug"])


def _pass_until_t3(client: TestClient, uid: str) -> None:
    _chat(client, uid, f"LOG[T-1]:{T1_LOG}")
    _chat(client, uid, f"LOG[T-1]:{T2_LOG}")


def _t5_log(client: TestClient, uid: str) -> str:
    st = client.get("/api/session/state", params={"user_id": uid}).json()["state"]
    return deploy_log(st["t3_nonce"], st["agent_slug"].replace("_", "-"))

T4_LOG = "============ test session starts ============\ncollected 5 items\n============ 5 passed in 0.21s ============"
T6_LOG = "To https://github.com/student/my-agent.git\n * [new branch] main -> main"


def test_tricky_llm_text_never_moves_step(client):
    """『Wチェック承認』『T-1（完了済）』『修了認定』を含む応答でもステップは動かない。"""
    uid = "u-tricky"
    st = _start_training(client, uid)
    assert st["current_step"] == "T-1"
    data = _chat(client, uid, "こんにちは、何をすればいい？")
    assert data["state"]["current_step"] == "T-1"
    assert data["state"]["results"] == {}
    assert data["state"]["verdict_this_turn"] is None


def test_happy_path_advances_exactly_one_step_per_approved_log(client):
    uid = "u-happy"
    _start_training(client, uid)
    expected = ["T-2", "T-3", "T-4", "T-5", "T-6", "T-6"]
    logs = [T1_LOG, T2_LOG, None, T4_LOG, None, T6_LOG]
    for i, (log, nxt) in enumerate(zip(logs, expected, strict=True), start=1):
        if log is None:
            log = _t3_log(client, uid) if i == 3 else _t5_log(client, uid)
        # LLMは常に誤って T-1 を渡す（旧実装では巻き戻り・誤判定の原因）
        data = _chat(client, uid, f"LOG[T-1]:{log}")
        st = data["state"]
        assert st["verdict_this_turn"]["w_check_status"] == "VERIFIED_APPROVED", (i, st)
        assert st["verdict_this_turn"]["step_id"] == f"T-{i}"
        assert st["current_step"] == nxt
        assert list(st["results"].keys()) == [f"T-{k}" for k in range(1, i + 1)]
    assert st["completed"] is True


def test_llm_passing_future_step_cannot_skip(client):
    """現在T-2なのにLLMが T-5 を指定しても、T-2 として検証され T-5 は完了しない。"""
    uid = "u-skip"
    _start_training(client, uid)
    _chat(client, uid, f"LOG[T-1]:{T1_LOG}")
    data = _chat(client, uid, f"LOG[T-5]:{deploy_log('', 'log-analyzer-bot')}")
    st = data["state"]
    assert "T-5" not in st["results"]
    assert st["current_step"] in ("T-2", "T-3")
    assert st["verdict_this_turn"]["step_id"] == "T-2"


def test_self_assertion_keeps_current_step(client):
    uid = "u-assert"
    _start_training(client, uid)
    _pass_until_t3(client, uid)
    data = _chat(client, uid, "LOG[T-1]:だいじょうぶでした。次に進もう！")
    st = data["state"]
    assert st["current_step"] == "T-3"
    assert st["verdict_this_turn"]["verdict"] == "FAILED"
    assert st["verdict_this_turn"]["step_id"] == "T-3"


def test_git_clone_fatal_error_does_not_branch_to_production_rollback(client):
    uid = "u-fatal"
    _start_training(client, uid)
    data = _chat(client, uid, "LOG[T-1]:git clone https://github.com/x/y.git\nfatal: could not read Username for 'https://github.com'")
    st = data["state"]
    assert st["current_step"] == "T-1"
    assert st["verdict_this_turn"]["w_check_status"] == "BLOCKED_RETRY"
    assert st["verdict_this_turn"]["branch_to"] is None


def test_idea_consultation_does_not_move_step_and_is_per_user(client):
    """企画相談はステップを動かさず、アイデア・企画書は受講生ごとに分離される（旧実装はグローバル共有）。"""
    a, b = "u-alice", "u-bob"
    _start_training(client, a)
    _start_training(client, b)
    _chat(client, a, f"LOG[T-1]:{T1_LOG}")
    data_a = _chat(client, a, IDEA_MSG)
    assert data_a["state"]["current_step"] == "T-2"
    assert "障害ログ" in data_a["state"]["user_idea"]

    st_b = client.get("/api/session/state", params={"user_id": b}).json()["state"]
    assert st_b["user_idea"] == ""
    assert st_b["current_step"] == "T-1"
    assert st_b["results"] == {}

    # 『確定』と言っても企画は確定しない（企画書の合格が確定）。T-3 以降は企画書待ちのまま
    data_a2 = _chat(client, a, "CONFIRM")
    assert data_a2["state"]["current_step"] == "T-2"
    assert data_a2["state"]["plan_confirmed"] is False
    sop_a = client.get("/api/sop", params={"user_id": a, "mode": "TRAINING"}).json()["sop"]
    assert sop_a["T-3"]["command"] == ""

    # 企画書が合格すると、その企画書の内容で T-3〜T-5 が作られる。他の受講生には影響しない
    _chat(client, a, f"LOG[T-1]:{T2_LOG}")
    sop_a = client.get("/api/sop", params={"user_id": a, "mode": "TRAINING"}).json()["sop"]
    sop_b = client.get("/api/sop", params={"user_id": b, "mode": "TRAINING"}).json()["sop"]
    assert "--agent-dir ipp-agent-workspace/log_analyzer_bot" in sop_a["T-3"]["command"]
    assert "--service log-analyzer-bot" in sop_a["T-5"]["command"]
    assert "社内障害ログ解析アシスタント" in sop_a["T-4"]["title"]
    assert sop_b["T-3"]["command"] == ""


def test_conversation_history_is_kept_in_session(client, scripted):
    """旧実装は get_session_sync の引数不足で毎回新規セッションになり、LLMが履歴を見られなかった。"""
    uid = "u-history"
    _start_training(client, uid)
    _chat(client, uid, "最初のメッセージ-XYZ")
    _chat(client, uid, "二通目のメッセージ")
    last_req = scripted.requests[-1]
    all_user_text = " ".join(p.text or "" for c in last_req.contents if c.role == "user" for p in (c.parts or []))
    assert "最初のメッセージ-XYZ" in all_user_text


def test_reselecting_same_course_keeps_progress(client):
    """『選択中（折りたたむ）』ボタン相当の同一コース再選択で進捗が消えない。"""
    uid = "u-reselect"
    _start_training(client, uid)
    _pass_until_t3(client, uid)
    _chat(client, uid, f"LOG[T-1]:{_t3_log(client, uid)}")
    st = client.post("/api/training/course", json={"user_id": uid, "course": "original"}).json()["state"]
    assert st["current_step"] == "T-4"
    assert set(st["results"]) == {"T-1", "T-2", "T-3"}

    # コース変更時は T-1 合格のみ引き継いで T-2 から
    st = client.post("/api/training/course", json={"user_id": uid, "course": "hitman_clone"}).json()["state"]
    assert st["course"] == "hitman_clone"
    assert st["current_step"] == "T-2"
    assert st["results"] == {"T-1": "SUCCESS"}


def test_lost_session_is_seeded_from_client_state(client):
    """Cloud Run のコールドスタート等でサーバのセッションが消えても、フロントの直近ステートで復元する。
    ただし連続していない合格（穴あき）は採用しない。"""
    uid = "u-restore"
    client_state = {
        "mode": "TRAINING",
        "course": "original",
        "course_selected": True,
        "results": {"T-1": "SUCCESS", "T-2": "SUCCESS", "T-4": "SUCCESS"},
        "user_idea": "日報要約AI",
        "brief": agent_module._brief_public(agent_module_parse(LOG_BRIEF)),
    }
    data = _chat(client, uid, "こんにちは", client_state=client_state)
    st = data["state"]
    assert st["session_restored"] is True
    assert st["current_step"] == "T-3"
    assert st["results"] == {"T-1": "SUCCESS", "T-2": "SUCCESS"}
    assert st["user_idea"] == "日報要約AI"

    assert st["agent_slug"] == "log_analyzer_bot"
    assert "log_analyzer_bot" in client.get("/api/sop", params={"user_id": uid, "mode": "TRAINING"}).json()["sop"]["T-3"]["command"]

    # 既存セッションがある場合、client_state は無視される（サーバが唯一の正）
    data2 = _chat(client, uid, "もう一度", client_state={"mode": "TRAINING", "results": {}})
    assert data2["state"]["current_step"] == "T-3"
    assert data2["state"]["session_restored"] is False


def test_lost_session_without_brief_restarts_at_t2(client):
    """コースAで企画書（設計図）を復元できない場合は、T-3 以降へ進ませず T-2 からやり直す。"""
    cs = {"mode": "TRAINING", "course": "original", "course_selected": True,
          "results": {"T-1": "SUCCESS", "T-2": "SUCCESS", "T-3": "SUCCESS"}}
    st = _chat(client, "u-restore-nobrief", "こんにちは", client_state=cs)["state"]
    assert st["current_step"] == "T-2"
    assert st["results"] == {"T-1": "SUCCESS"}
    forged = dict(cs, brief={"agent_name": "x", "tools": []})
    st = _chat(client, "u-restore-forged", "こんにちは", client_state=forged)["state"]
    assert st["current_step"] == "T-2"


def agent_module_parse(text: str) -> dict:
    from app.project_brief import parse_brief
    return parse_brief(text)


def test_session_reset_clears_state(client):
    uid = "u-reset"
    _start_training(client, uid)
    _chat(client, uid, f"LOG[T-1]:{T1_LOG}")
    st = client.post("/api/session/reset", json={"user_id": uid}).json()["state"]
    assert st["results"] == {}
    assert st["mode"] == "NORMAL"


def test_reply_contains_only_last_card(client):
    """同一応答内で複数カードが返っても、最後のモデル応答のカードのみ描画対象になる。"""
    uid = "u-cards"
    _start_training(client, uid)
    data = _chat(client, uid, f"LOG[T-1]:{T1_LOG}")
    a2ui = [p for p in data["parts"] if p["kind"] == "a2ui"]
    texts = [p for p in data["parts"] if p["kind"] == "text"]
    assert len(texts) >= 1
    # 最終応答の <a2ui-json> 1ブロック分（beginRendering 等の自動付与を含む）のみ
    assert len(a2ui) <= 4


def test_normalize_course_no_longer_matches_letter_b():
    assert agent_module._normalize_course("web app") == "original"
    assert agent_module._normalize_course("b") == "hitman_clone"
    assert agent_module._normalize_course("コースB") == "hitman_clone"
    assert agent_module._normalize_course("hitman_clone") == "hitman_clone"
    assert agent_module._normalize_course("original") == "original"


def test_session_sync_restores_on_page_load(client):
    uid = "u-sync"
    cs = {"mode": "TRAINING", "course": "hitman_clone", "course_selected": True, "results": {"T-1": "SUCCESS"}}
    st = client.post("/api/session/sync", json={"user_id": uid, "client_state": cs}).json()["state"]
    assert st["session_restored"] is True
    assert st["course"] == "hitman_clone"
    assert st["current_step"] == "T-2"


def test_toggling_mode_resumes_at_first_incomplete_step(client):
    uid = "u-toggle"
    _start_training(client, uid)
    _pass_until_t3(client, uid)
    client.post("/api/mode", json={"user_id": uid, "mode": "NORMAL"})
    st = client.post("/api/mode", json={"user_id": uid, "mode": "TRAINING"}).json()["state"]
    assert st["current_step"] == "T-3"


def test_offer_choices_are_returned_for_the_turn_and_reset_next_turn(client):
    """LLM が offer_choices で出した返答候補がそのターンの state に載り、次のターンには持ち越されない。"""
    uid = "u-choices"
    _start_training(client, uid)
    data = _chat(client, uid, "CHOICES:ログ解析Botで進めたい|もう少し詳しく聞きたい|別のアイデアも見たい")
    assert data["state"]["suggestions"] == ["ログ解析Botで進めたい", "もう少し詳しく聞きたい", "別のアイデアも見たい"]
    data2 = _chat(client, uid, "ありがとう")
    assert data2["state"]["suggestions"] == []


def test_t2_requires_complete_brief_and_uses_it_as_the_blueprint(client):
    """T-2 は書式どおりの企画書でのみ合格し、その企画書が T-3 以降の設計図になる。
    2026-09-30 の実機では『カレンダー＋ガント＋日記』の企画が、キーワード表で WBS 管理Bot にすり替えられていた。"""
    uid = "u-t2-brief"
    _start_training(client, uid)
    _chat(client, uid, f"LOG[T-1]:{T1_LOG}")
    old_style = "[skill:pick-your-agent-project@v1]\n# Project Brief\n## エージェント名: log_analyzer_bot\n## ツール: analyze_log"
    data = _chat(client, uid, f"LOG[T-1]:{old_style}")
    assert data["state"]["current_step"] == "T-2"
    assert data["state"]["verdict_this_turn"]["w_check_status"] == "BLOCKED_RETRY"

    data = _chat(client, uid, f"LOG[T-1]:{t2_log(CALENDAR_BRIEF)}")
    st = data["state"]
    assert st["current_step"] == "T-3"
    assert st["agent_slug"] == "calendar_journal_agent"
    assert st["t3_nonce"].startswith("T3-")
    sop = client.get("/api/sop", params={"user_id": uid, "mode": "TRAINING"}).json()["sop"]
    t3 = sop["T-3"]
    assert f"--nonce {st['t3_nonce']}" in t3["command"]
    assert "--agent-dir ipp-agent-workspace/calendar_journal_agent" in t3["command"]
    assert '--q1 "10月3日に歯医者の予定を入れて"' in t3["command"]
    for word in ("add_event", "upsert_task", "summarize_week", "月カレンダー", "ガント", "日記"):
        assert word in t3["agy_prompt"], word
    everything = json.dumps(sop, ensure_ascii=False)
    for template in ("schedule_wbs_agent", "WBS＆スケジュール管理Bot", "get_schedule_and_wbs", "プロジェクトX"):
        assert template not in everything, template


def test_course_a_steps_follow_the_brief_and_keep_keys_out_of_commands(client):
    """企画書から T-3〜T-6 が作られ、どのステップも API キーを平文で渡す手順を含まない。"""
    uid = "u-brief-steps"
    _start_training(client, uid)
    _chat(client, uid, f"LOG[T-1]:{T1_LOG}")
    _chat(client, uid, f"LOG[T-1]:{t2_log(CALENDAR_BRIEF)}")
    sop = client.get("/api/sop", params={"user_id": uid, "mode": "TRAINING"}).json()["sop"]
    assert sop["T-4"]["command"] == "pytest ipp-agent-workspace/calendar_journal_agent/tests/ -v"
    t5 = sop["T-5"]
    assert t5["command"].startswith("python .agents/skills/ipp-cloud-run-deploy/scripts/deploy.py")
    assert "--service calendar-journal-agent" in t5["command"]
    assert "secret_scan.py ipp-agent-workspace/calendar_journal_agent" in sop["T-6"]["command"]
    for sid in ("T-3", "T-4", "T-5", "T-6"):
        step = sop[sid]
        assert "--set-env-vars GEMINI_API_KEY" not in step["command"]
        assert ".env" in step["agy_prompt"], sid
        assert "build-agent-frontend" not in step["command"]
    assert "env_setup.py --agent-dir ipp-agent-workspace/calendar_journal_agent" in sop["T-3"]["agy_prompt"]
    assert "ipp-build-app-from-brief" in sop["T-3"]["agy_prompt"]


def test_t5_requires_working_deployment(client):
    """URL が出ただけ・/chat が 500 のデプロイでは T-5 に合格しない（実機で S+ 合格してしまった状態）。"""
    uid = "u-t5"
    _start_training(client, uid)
    _pass_until_t3(client, uid)
    _chat(client, uid, f"LOG[T-1]:{_t3_log(client, uid)}")
    _chat(client, uid, f"LOG[T-1]:{T4_LOG}")
    st = client.get("/api/session/state", params={"user_id": uid}).json()["state"]
    assert st["current_step"] == "T-5"
    url_only = "Service [log-analyzer-bot] has been deployed\nService URL: https://log-analyzer-bot-1.asia-northeast1.run.app"
    for bad in (
        url_only,
        deploy_log(st["t3_nonce"], "log-analyzer-bot", chat_status=500),  # API キー未注入で /chat が 500
        deploy_log("T3-000000", "log-analyzer-bot"),  # 他人の確認コード
        deploy_log(st["t3_nonce"], "my-agent"),  # 企画と別のサービス
        deploy_log(st["t3_nonce"], "log-analyzer-bot").replace("chat=200", "chat=200").replace('"status_chat":200', '"status_chat":201'),  # 改変
    ):
        data = _chat(client, uid, f"LOG[T-1]:{bad}")
        assert data["state"]["current_step"] == "T-5", data["state"]["verdict_this_turn"]
        assert data["state"]["verdict_this_turn"]["verdict"] == "FAILED"
    data = _chat(client, uid, f"LOG[T-1]:{deploy_log(st['t3_nonce'], 'log-analyzer-bot')}")
    assert data["state"]["current_step"] == "T-6"


def test_live_deploy_check_blocks_dead_service(client, monkeypatch):
    """HITMAN 自身が公開URLへアクセスし、応答しなければ出力が正しくても合格させない。"""
    uid = "u-t5-live"
    _start_training(client, uid)
    _pass_until_t3(client, uid)
    _chat(client, uid, f"LOG[T-1]:{_t3_log(client, uid)}")
    _chat(client, uid, f"LOG[T-1]:{T4_LOG}")
    monkeypatch.setenv("HITMAN_LIVE_DEPLOY_CHECK", "1")
    calls = []

    def fake_live(url, question, timeout=60):
        calls.append((url, question))
        return {"ok": False, "status_health": 200, "status_chat": 500, "has_reply": False}

    monkeypatch.setattr(agent_module, "live_deploy_check", fake_live)
    data = _chat(client, uid, f"LOG[T-1]:{_t5_log(client, uid)}")
    assert data["state"]["current_step"] == "T-5"
    assert calls and calls[0][1] == "No space left on device のエラーが出ました"  # 企画書の Q1 で確認する
    monkeypatch.setattr(agent_module, "live_deploy_check", lambda url, question, timeout=60: {"ok": True, "status_health": 200, "status_chat": 200, "has_reply": True})
    data = _chat(client, uid, f"LOG[T-1]:{_t5_log(client, uid)}")
    assert data["state"]["current_step"] == "T-6"


def test_chat_message_with_api_key_is_never_sent_to_llm(client, scripted):
    """受講生がチャットに API キーを貼っても、Gemini に送らず・履歴に残さず・判定もしない。"""
    uid = "u-secret"
    _start_training(client, uid)
    n_before = len(scripted.requests)
    fake_key = "AIza" + "Sy" + "A" * 33
    data = _chat(client, uid, f"キーはこれです GEMINI_API_KEY={fake_key} 設定して")
    assert len(scripted.requests) == n_before
    assert data["state"]["secret_blocked"] is True
    assert fake_key not in json.dumps(data, ensure_ascii=False)
    assert "無効化" in data["parts"][0]["text"]
    _chat(client, uid, "こんにちは")
    history = " ".join(p.text or "" for c in scripted.requests[-1].contents for p in (c.parts or []))
    assert fake_key not in history
