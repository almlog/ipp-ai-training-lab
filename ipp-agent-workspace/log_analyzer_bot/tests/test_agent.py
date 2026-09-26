"""
社内障害ログ自動解析Bot のテスト。
ツールが「入力に応じて」結果を変えること（固定値を返すダミーでないこと）を中心に検証する。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from agent import analyze_stacktrace, recommend_fix_commands, root_agent

DISK_LOG = """2026-09-26 10:02:11 ERROR backup.py: write failed
OSError: [Errno 28] No space left on device: '/var/backup/app.tar.gz'"""

DB_LOG = """Traceback (most recent call last):
  File "/app/db.py", line 42, in connect
    conn = psycopg2.connect(dsn, connect_timeout=5)
psycopg2.OperationalError: could not connect to server: Connection refused (port 5432)"""

JAVA_LOG = """java.lang.NullPointerException
    at com.example.order.OrderService.calc(OrderService.java:88)
    at com.example.order.OrderController.post(OrderController.java:31)"""


@pytest.mark.parametrize(
    "log,expected_type,expected_severity",
    [
        (DISK_LOG, "DISK_FULL", "CRITICAL"),
        (DB_LOG, "DB_CONNECTION", "CRITICAL"),
        ("ERROR 1213 (40001): Deadlock found when trying to get lock", "DB_LOCK", "WARNING"),
        ("open('/etc/app.conf'): Permission denied", "PERMISSION", "WARNING"),
        (JAVA_LOG, "APPLICATION_EXCEPTION", "WARNING"),
        ("service started normally", "UNKNOWN", "INFO"),
    ],
)
def test_analyze_stacktrace_classifies_by_content(log, expected_type, expected_severity):
    res = analyze_stacktrace(log)
    assert res["error_type"] == expected_type
    assert res["severity"] == expected_severity


def test_analyze_stacktrace_extracts_evidence_and_location():
    res = analyze_stacktrace(DB_LOG)
    assert "Connection refused" in res["evidence_line"]
    assert res["exception_class"] == "OperationalError"
    assert res["location"] == "/app/db.py:42"
    java = analyze_stacktrace(JAVA_LOG)
    assert java["exception_class"] == "NullPointerException"
    assert java["location"].startswith("com.example.order.OrderController.post")


def test_different_inputs_give_different_results():
    """同じツールに違うログを渡したら結果が変わる（スモークテストの no_stub_suspect に相当）。"""
    assert analyze_stacktrace(DISK_LOG) != analyze_stacktrace(DB_LOG)
    assert recommend_fix_commands("DISK_FULL") != recommend_fix_commands("DB_CONNECTION")


def test_recommend_fix_commands_uses_service_name_and_flags_changes():
    res = recommend_fix_commands("OUT_OF_MEMORY", service_name="order-api")
    cmds = [c["cmd"] for c in res["commands"]]
    assert "systemctl restart order-api" in cmds
    assert any("【変更あり】" in c["note"] for c in res["commands"])
    assert recommend_fix_commands("no-such-type")["error_type"] == "UNKNOWN"


def test_root_agent_wires_tools_and_a2ui():
    names = {t.__name__ for t in root_agent.tools}
    assert names == {"analyze_stacktrace", "recommend_fix_commands"}
    assert root_agent.after_model_callback is not None
    assert "analyze_stacktrace" in root_agent.instruction
    # enable-a2ui の手順どおり A2UI v0.8 のスキーマがシステムプロンプトに入っていること（独自JSON防止）
    assert "surfaceUpdate" in root_agent.instruction and "beginRendering" in root_agent.instruction
