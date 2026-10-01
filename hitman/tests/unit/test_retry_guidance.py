"""研修モードでの不合格・リトライ時のコマンド・プロンプト案内機能のテスト。"""

import pytest
from app.agent import HitmanState, verify_step_output, MODE_TRAINING, DEMO_BRIEF


def test_t3_smoke_tampered_includes_retry_command_and_prompt():
    """T-3 でスモークテストログが改変・途中切れ検知された場合、再実行コマンドとプロンプトが付与されること。"""
    store = {}
    ctx = type("Ctx", (), {"state": store})()
    state = HitmanState(store)
    state.mode = MODE_TRAINING
    state.course = "original"
    state.current_step = "T-2"
    
    # まず T-2 を合格させて企画書（DEMO_BRIEF）を確定し、T-3 へ進める
    res_t2 = verify_step_output("T-2", DEMO_BRIEF, tool_context=ctx)
    assert res_t2["verdict"] == "SUCCESS"
    assert state.current_step == "T-3"

    # 改変・途中切れのスモークテストログ（SMOKE_DIGEST 不一致）
    tampered_log = """
[skill:ipp-agent-smoke-test@v1]
$ python .agents/skills/ipp-agent-smoke-test/scripts/smoke_test.py --agent-dir ipp-agent-workspace/equipment_lending_agent --q1 "foo" --q2 "bar"
SMOKE_RESULT: PASS
SMOKE_JSON: {"agent_dir":"equipment_lending_agent","nonce":"dummy","runs":[],"tools":[],"passed":true}
SMOKE_DIGEST: 0000000000000000
"""
    res_t3 = verify_step_output("T-3", tampered_log, tool_context=ctx)
    assert res_t3["verdict"] == "FAILED"
    assert res_t3["w_check_status"] == "BLOCKED_RETRY"
    assert "retry_command" in res_t3
    assert "smoke_test.py" in res_t3["retry_command"]
    assert "equipment_lending_agent" in res_t3["retry_command"]
    assert res_t3.get("retry_prompt")
    assert "【再実行コマンド】" in res_t3["message"]
    assert "smoke_test.py" in res_t3["message"]
    assert len(res_t3.get("hints", [])) > 0


def test_t1_guidance_includes_retry_command():
    """T-1 でクローンのみのログを提出した場合、ガイダンスと再実行用コマンド/プロンプトが付与されること。"""
    store = {}
    ctx = type("Ctx", (), {"state": store})()
    state = HitmanState(store)
    state.mode = MODE_TRAINING
    state.course = "original"
    state.current_step = "T-1"

    incomplete_log = "Cloning into 'ipp-agent-workspace/ipp-ai-training-lab'...\nUnpacking objects: 100%"
    res_t1 = verify_step_output("T-1", incomplete_log, tool_context=ctx)
    assert res_t1["verdict"] == "FAILED"
    assert res_t1["w_check_status"] == "TRAINING_GUIDANCE"
    assert "retry_command" in res_t1
    assert "ipp-agent-workspace" in res_t1["retry_command"]
    assert "retry_prompt" in res_t1
    assert "【再実行コマンド】" in res_t1["message"]
