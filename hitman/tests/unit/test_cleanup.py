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
