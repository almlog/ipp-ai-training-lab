from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.agent import (
    HitmanState,
    MODE_TRAINING,
    get_training_sop,
    set_operation_mode,
    set_training_course,
    verify_step_output,
)

ROOT = Path(__file__).resolve().parents[3]
CLEANUP_SCRIPT = ROOT / ".agents" / "skills" / "ipp-cloud-run-deploy" / "scripts" / "cleanup.py"


def test_cleanup_script_exists():
    assert CLEANUP_SCRIPT.is_file(), f"{CLEANUP_SCRIPT} does not exist"


def test_cleanup_script_help():
    proc = subprocess.run(
        [sys.executable, str(CLEANUP_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0
    assert "--service" in proc.stdout
    assert "--agent-dir" in proc.stdout
    assert "--region" in proc.stdout


def test_t6_success_message_contains_cleanup_prompt():
    set_operation_mode(MODE_TRAINING)
    set_training_course("original")
    state = HitmanState.of(None)
    state.current_step = "T-6"

    t6_log = (
        "Enumerating objects: 42, done.\n"
        "To https://github.com/suzuki-shunpei/my-agent.git\n"
        " * [new branch]      main -> main"
    )
    res = verify_step_output("T-6", t6_log)
    assert res["verdict"] == "SUCCESS"
    assert "cleanup.py" in res["message"]
    assert "【AntiGravity投入用: 演習環境クリーンアッププロンプト】" in res["message"]
    assert "課金防止" in res["message"]


def test_sop_t6_cautions_mention_cleanup():
    sop_a = get_training_sop("original")
    assert "クリーンアップ" in sop_a["T-6"]["cautions"] or "安全停止" in sop_a["T-6"]["cautions"]

    sop_b = get_training_sop("hitman_clone")
    assert "クリーンアップ" in sop_b["T-6"]["cautions"] or "安全停止" in sop_b["T-6"]["cautions"]


def test_cleanup_success_log_approved():
    set_operation_mode(MODE_TRAINING)
    set_training_course("original")
    state = HitmanState.of(None)
    state.current_step = "T-6"
    results = state.results
    results["T-6"] = "SUCCESS"
    state.results = results
    state.cleanup_done = False

    cleanup_log = (
        "bash\n"
        "[skill:ipp-cloud-run-deploy@v1]\n"
        "# IPP AI研修: 演習環境クリーンアップ実行レポート\n"
        "- **プロジェクト**: `altx-ai-training-lab`\n"
        "- **対象サービス**: `calendar-wbs-agent`\n"
        "- **リージョン**: `asia-northeast1`\n"
        "## 1. Cloud Run サービスの破棄（課金・外部アクセス停止）\n"
        "- Cloud Run サービス `calendar-wbs-agent` が検出されました。削除を実行します...\n"
        "- [SUCCESS] Cloud Run サービス `calendar-wbs-agent` を正常に削除しました。\n"
        "## 2. Secret Manager の破棄（クラウド上のAPIキー完全消去）\n"
        "- Secret `calendar-wbs-agent-gemini-api-key` が検出されました。削除を実行します...\n"
        "- [SUCCESS] Secret `calendar-wbs-agent-gemini-api-key` を正常に削除しました。\n"
        "CLEANUP_RESULT: SUCCESS"
    )

    res = verify_step_output("T-6", cleanup_log)
    assert res["verdict"] == "SUCCESS"
    assert res["w_check_status"] == "VERIFIED_APPROVED"
    assert state.cleanup_done is True
    assert "クリーンアップ完了" in res["message"]
    assert "改修・回収要望" in res["message"] or "パートナーモード" in res["message"]


def test_post_graduation_flexible_mode_no_retry():
    set_operation_mode(MODE_TRAINING)
    set_training_course("original")
    state = HitmanState.of(None)
    state.current_step = "T-6"
    results = state.results
    results["T-6"] = "SUCCESS"
    state.results = results

    # 受講生の自然言語メッセージや回収要望の相談
    user_msg = "お疲れ様でした！自作ツールの回収要望があります。カレンダー表示を月間だけでなく週単位でも見られるようにしたいです。"
    res = verify_step_output("T-6", user_msg)
    assert res["verdict"] == "SUCCESS"
    assert res["w_check_status"] == "VERIFIED_APPROVED"
    assert "修了認定済み" in res["message"] or "回収要望" in res["message"]


def test_request_tool_improvement():
    from app.agent import request_tool_improvement

    set_operation_mode(MODE_TRAINING)
    set_training_course("original")
    state = HitmanState.of(None)
    state.brief = {
        "agent_name": "calendar_wbs_agent",
        "display_name": "カレンダーWBSタスクマネージャー",
    }
    state.agent_slug = "calendar_wbs_agent"

    res = request_tool_improvement(
        title="週表示カレンダー機能の追加",
        details="月間カレンダーに加えて週間ビューを切り替えられるボタンと表示機能を追加したい。",
        improvement_type="feature_add",
    )

    assert res["status"] == "REGISTERED"
    assert res["agent_name"] == "カレンダーWBSタスクマネージャー"
    assert "AntiGravity投入用プロンプト" in res["agy_prompt"]
    assert "calendar_wbs_agent" in res["agy_prompt"]
    assert "週表示カレンダー機能の追加" in res["agy_prompt"]
    assert len(state.tool_improvements) >= 1
    assert state.tool_improvements[-1]["title"] == "週表示カレンダー機能の追加"

