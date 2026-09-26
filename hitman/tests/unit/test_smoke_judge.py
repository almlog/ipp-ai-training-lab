# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""T-3 スモークテスト（ipp-agent-smoke-test スキル）と HITMAN 判定の結合テスト。

実際に smoke_test.py でエージェントを動かし（LLM はダミー）、その出力を HITMAN の判定に通す:
- 入力に応じて処理する本物のツール → 合格
- 引数を無視して固定値を返すハリボテのツール → 不合格（ダミー実装の疑い）
- ツールを呼ばず固定文を返すエージェント → 不合格
- 出力の書き換え（FAIL → PASS 等）→ 改変として検知
"""

import asyncio
import importlib.util
import json
import re
import uuid
from pathlib import Path

import pytest
from google.adk.agents import Agent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

import app.agent as agent_module

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".agents" / "skills" / "ipp-agent-smoke-test" / "scripts" / "smoke_test.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("ipp_smoke_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


smoke = _load_script()


class ToolCallingLlm(BaseLlm):
    """ユーザー文から数字を拾ってツールを呼び、ツール結果をそのまま返事にするダミーLLM。"""

    model: str = "tool-calling-llm"
    call_tools: bool = True

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False):
        last = llm_request.contents[-1]
        fr = next((p.function_response for p in last.parts or [] if p.function_response), None)
        if fr is not None:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=f"解析結果: {json.dumps(fr.response, ensure_ascii=False)}")]))
            return
        text = next((p.text for p in last.parts or [] if p.text), "")
        if not self.call_tools:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="ご質問ありがとうございます。")]))
            return
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
            name="analyze_log", args={"log_text": text}, id=f"c-{uuid.uuid4().hex[:6]}"))]))


def analyze_log(log_text: str) -> dict:
    """ログを解析して原因を返す（本物: 入力に応じて結果が変わる）。"""
    lower = log_text.lower()
    if "no space" in lower or "容量" in log_text:
        return {"cause": "ディスク容量不足", "action": "不要ファイルを削除"}
    if "timeout" in lower:
        return {"cause": "DB接続タイムアウト", "action": "接続設定を確認"}
    return {"cause": "不明", "action": "詳細ログを確認"}


def analyze_log_stub(log_text: str) -> dict:
    """ハリボテ: 引数を無視して固定値を返す。"""
    return {"cause": "正常に解析しました", "action": "問題ありません"}


analyze_log_stub.__name__ = "analyze_log"

Q1 = "No space left on device のエラーが出ました"
Q2 = "DB connection timeout が発生しました"


def _run(tool, call_tools=True) -> str:
    agent = Agent(name="log_bot", model=ToolCallingLlm(call_tools=call_tools), instruction="ログを解析する", tools=[tool])
    data = asyncio.run(smoke.run_smoke(agent, Q1, Q2))
    return "```text\n" + smoke.format_report(data, "python smoke_test.py ...") + "\n```"


def test_real_agent_passes_script_and_hitman():
    out = _run(analyze_log)
    assert "SMOKE_RESULT: PASS" in out
    assert out.splitlines()[1] == smoke.MARKER
    judged = agent_module.judge_smoke_output(out)
    assert judged["status"] == "PASS", judged


def test_stub_tool_is_detected():
    out = _run(analyze_log_stub)
    assert "SMOKE_RESULT: FAIL" in out
    judged = agent_module.judge_smoke_output(out)
    assert judged["status"] == "FAIL"
    assert "no_stub_suspect" in judged["reason"]
    assert "analyze_log" in judged["reason"]


def test_agent_without_tool_calls_fails():
    judged = agent_module.judge_smoke_output(_run(analyze_log, call_tools=False))
    assert judged["status"] == "FAIL"
    assert "tool_called" in judged["reason"] and "replies_differ" in judged["reason"]


def test_tampered_output_is_rejected():
    out = _run(analyze_log_stub)
    forged = out.replace("SMOKE_RESULT: FAIL", "SMOKE_RESULT: PASS").replace('"passed":false', '"passed":true')
    assert agent_module.judge_smoke_output(forged)["status"] == "TAMPERED"
    # 判定の元データ（結果ハッシュ）を書き換えても検知される
    forged2 = re.sub(r'"result_hash":"[0-9a-f]{12}"', '"result_hash":"000000000000"', out, count=1)
    assert agent_module.judge_smoke_output(forged2)["status"] == "TAMPERED"


def test_truncated_output_is_broken():
    out = _run(analyze_log)
    truncated = "\n".join(l for l in out.splitlines() if not l.startswith("SMOKE_DIGEST"))
    assert agent_module.judge_smoke_output(truncated)["status"] == "BROKEN"


def test_script_and_hitman_use_same_digest_and_checks():
    out = _run(analyze_log_stub)
    data = json.loads(re.search(r"^SMOKE_JSON: (.*)$", out, re.M).group(1))
    assert smoke.digest_of(data) == agent_module._smoke_digest(data)
    checks, suspects = agent_module._smoke_checks(data["runs"])
    assert checks == data["checks"] and suspects == data["stub_suspects"]


@pytest.mark.parametrize("tool,expected", [(analyze_log, "VERIFIED_APPROVED"), (analyze_log_stub, "BLOCKED_RETRY")])
def test_verify_step_t3_uses_smoke_result(tool, expected):
    store: dict = {}
    ctx = type("Ctx", (), {"state": store})()
    agent_module.set_operation_mode("TRAINING", tool_context=ctx)
    agent_module.set_training_course("original", tool_context=ctx)
    agent_module.HitmanState(store).results = {"T-1": "SUCCESS", "T-2": "SUCCESS"}
    agent_module.HitmanState(store).current_step = "T-3"
    res = agent_module.verify_step_output("T-3", _run(tool), tool_context=ctx)
    assert res["w_check_status"] == expected
    assert agent_module.HitmanState(store).current_step == ("T-4" if expected == "VERIFIED_APPROVED" else "T-3")


def test_code_listing_alone_no_longer_passes_t3():
    """旧来の ls / head agent.py だけの提出はスモークテストを求める案内になる。"""
    store: dict = {}
    ctx = type("Ctx", (), {"state": store})()
    agent_module.set_operation_mode("TRAINING", tool_context=ctx)
    agent_module.HitmanState(store).results = {"T-1": "SUCCESS", "T-2": "SUCCESS"}
    agent_module.HitmanState(store).current_step = "T-3"
    res = agent_module.verify_step_output(
        "T-3", "$ ls -la my_agent\n-rw-r--r-- agent.py\nfrom google.adk.agents import Agent\nroot_agent = Agent(name='x')", tool_context=ctx)
    assert res["verdict"] == "FAILED" and res["w_check_status"] == "TRAINING_GUIDANCE"
    assert "ipp-agent-smoke-test" in res["message"]


class GeminiLikeLogBot(BaseLlm):
    """見本（障害ログ解析Bot）用: ログ → analyze_stacktrace → recommend_fix_commands → 回答 の順に動くダミー。"""

    model: str = "gemini-like"

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False):
        last = llm_request.contents[-1]
        fr = next((p.function_response for p in last.parts or [] if p.function_response), None)

        def call(name, args):
            return LlmResponse(content=types.Content(role="model", parts=[types.Part(
                function_call=types.FunctionCall(name=name, args=args, id=f"c-{uuid.uuid4().hex[:6]}"))]))

        if fr is None:
            text = next((p.text for p in last.parts or [] if p.text), "")
            yield call("analyze_stacktrace", {"log_content": text})
        elif fr.name == "analyze_stacktrace":
            yield call("recommend_fix_commands", {"error_type": fr.response["error_type"]})
        else:
            cmds = " / ".join(c["cmd"] for c in fr.response["commands"])
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=f"{fr.response['error_type']}: {cmds}")]))


def test_bundled_course_a_sample_passes_smoke():
    """同梱の見本（ipp-agent-workspace/log_analyzer_bot）が、ダミーでない実装としてスモークテストに合格すること。"""
    root, _ = smoke.load_root_agent(str(REPO_ROOT / "ipp-agent-workspace" / "log_analyzer_bot"))
    root.model = GeminiLikeLogBot()
    data = asyncio.run(smoke.run_smoke(
        root,
        "OSError: [Errno 28] No space left on device: '/var/backup/app.tar.gz'",
        "psycopg2.OperationalError: could not connect to server: Connection refused (port 5432)",
    ))
    out = smoke.format_report(data, "python smoke_test.py ...")
    assert agent_module.judge_smoke_output(out)["status"] == "PASS", out


def test_smoke_auth_detects_vertex_express_key_and_never_prints_it(monkeypatch, capsys):
    """AQ. で始まるキーは Vertex AI Express として扱い、キーと同時指定できない PROJECT/LOCATION を外す。
    キーの値そのものは出力しない（Antigravity がキーをコマンドに直書きして漏らした事例への対策）。"""
    fake_key = "AQ.test-not-a-real-key-123"
    # 関数が書き換える環境変数をすべて monkeypatch に登録し、テスト後に元へ戻す
    # （存在しない変数の delenv は記録されないため、いったん setenv してから消す）
    for name in ("GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GENAI_USE_ENTERPRISE",
                 "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"):
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)
    monkeypatch.setenv("GEMINI_API_KEY", fake_key)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    mode = smoke._configure_gemini_auth()
    import os
    assert "Vertex AI Express" in mode
    assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "true" == os.environ["GOOGLE_GENAI_USE_ENTERPRISE"]
    assert "GOOGLE_CLOUD_PROJECT" not in os.environ and "GOOGLE_CLOUD_LOCATION" not in os.environ
    assert fake_key not in mode and fake_key not in capsys.readouterr().out

    monkeypatch.setenv("GEMINI_API_KEY", "AIza-studio-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert "Developer API" in smoke._configure_gemini_auth()
    assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "false"
