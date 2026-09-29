# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""コースAの要件定義書（project_brief.md）の書式検査のテスト。"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

import app.agent as agent_module
from app.project_brief import BRIEF_TEMPLATE, parse_brief
from tests.unit.brief_fixtures import CALENDAR_BRIEF, LOG_BRIEF

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_SCRIPTS = REPO_ROOT / ".agents" / "skills" / "pick-your-agent-project" / "scripts"


def test_calendar_brief_is_parsed_as_the_students_own_project():
    b = parse_brief(CALENDAR_BRIEF)
    assert b["ok"], b["errors"]
    assert b["agent_name"] == "calendar_journal_agent"
    assert [f["id"] for f in b["features"]] == ["F1", "F2", "F3"]
    assert [t["name"] for t in b["tools"]] == ["add_event", "upsert_task", "summarize_week"]
    assert [s["features"] for s in b["screens"]] == [["F1"], ["F2"], ["F3"]]
    assert b["q1"] != b["q2"]


def test_template_itself_is_not_a_valid_brief():
    """書式の見本（<…>のまま）をそのまま出しても合格しない。"""
    assert parse_brief(BRIEF_TEMPLATE)["ok"] is False


@pytest.mark.parametrize("mutate,expect", [
    (lambda t: t.replace("## 3. 画面", "## 3. その他"), "画面"),
    (lambda t: t.replace("- エージェント名: calendar_journal_agent", "- エージェント名: Calendar App"), "エージェント名"),
    (lambda t: t.replace(" ／ 受け入れ条件: 開始日・終了日・進捗率を持つタスクが横棒で表示される", ""), "受け入れ条件"),
    (lambda t: t.replace("使う機能: F3", "使う機能: F1").replace("／ 使う機能: F3", ""), "F3"),
    (lambda t: t.replace("- Q2: 今週の日記と予定から振り返りをまとめて", "- Q2: 10月3日に歯医者の予定を入れて"), "Q1 と Q2"),
    (lambda t: t.replace("GEMINI_API_KEY: ローカルは .env から読み込む。", "GEMINI_API_KEY: 環境変数から読む。"), ".env"),
    (lambda t: t.replace("- 家族との共有（ログイン・権限管理）\n", ""), "作らないもの"),
])
def test_incomplete_brief_is_rejected_with_actionable_errors(mutate, expect):
    b = parse_brief(mutate(CALENDAR_BRIEF))
    assert not b["ok"]
    assert any(expect in e for e in b["errors"]), b["errors"]


def test_skill_copy_of_parser_is_identical():
    """受講生側の brief_check.py と HITMAN は同じ解析ロジックを使う。"""
    assert (SKILL_SCRIPTS / "project_brief.py").read_bytes() == (REPO_ROOT / "hitman" / "app" / "project_brief.py").read_bytes()


def test_brief_check_output_passes_hitman_t2(tmp_path):
    """brief_check.py の出力をそのまま貼ると T-2 に合格し、企画書が設計図として保存される。"""
    path = tmp_path / "project_brief.md"
    path.write_text(CALENDAR_BRIEF, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SKILL_SCRIPTS / "brief_check.py"), str(path)],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    assert out.splitlines()[1] == "[skill:pick-your-agent-project@v1]"

    store: dict = {}
    ctx = type("Ctx", (), {"state": store})()
    agent_module.set_operation_mode("TRAINING", tool_context=ctx)
    agent_module.set_training_course("original", tool_context=ctx)
    st = agent_module.HitmanState(store)
    st.results, st.current_step = {"T-1": "SUCCESS"}, "T-2"
    res = agent_module.verify_step_output("T-2", out, tool_context=ctx)
    assert res["w_check_status"] == "VERIFIED_APPROVED", res["message"]
    assert not res["skills_missing"]
    assert st.brief["agent_name"] == "calendar_journal_agent" and st.current_step == "T-3"


def test_brief_check_rejects_incomplete_brief(tmp_path):
    path = tmp_path / "project_brief.md"
    path.write_text(CALENDAR_BRIEF.replace("## 4. 関数ツール", "## 4. メモ"), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SKILL_SCRIPTS / "brief_check.py"), str(path)],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 1
    assert "BRIEF_CHECK: FAIL" in proc.stdout and "[skill:" not in proc.stdout


def test_hitman_has_no_keyword_templates_for_course_a():
    """『カレンダー』等のキーワードで企画を別物（WBS Bot 等）に置き換える仕組みが残っていないこと。"""
    src = (REPO_ROOT / "hitman" / "app" / "agent.py").read_text(encoding="utf-8")
    for name in ("derive_agent_slug_and_name", "_derive_agent_q_examples", "_plan_skills_and_points",
                 "schedule_wbs_agent", "WBS＆スケジュール管理Bot", "get_schedule_and_wbs"):
        assert name not in src, name


def test_log_brief_fixture_is_valid():
    assert parse_brief(LOG_BRIEF)["ok"]


def test_heading_variants_and_forbidden_question_chars():
    text = CALENDAR_BRIEF.replace("## 7. 今回は作らないもの", "## 7. 今回は作らない機能")
    assert parse_brief(text)["ok"], parse_brief(text)["errors"]
    bad = CALENDAR_BRIEF.replace("- Q1: 10月3日に歯医者の予定を入れて", "- Q1: $(whoami) の予定を入れて")
    assert not parse_brief(bad)["ok"]


def test_custom_workspace_is_not_doubled_in_course_a_commands():
    from tests.unit.brief_fixtures import set_brief
    st = agent_module.HitmanState({})
    agent_module.select_training_course(st, "original")
    set_brief(st, CALENDAR_BRIEF)
    st.issue_t3_nonce()
    sop = agent_module.get_training_sop("original", params={"WORKSPACE_DIR": r"C:\work\ipp-agent-workspace"}, state=st)
    for sid in ("T-3", "T-4", "T-5", "T-6"):
        cmd = sop[sid]["command"]
        assert cmd.count("ipp-agent-workspace") == 1, (sid, cmd)
        assert r"C:\work\ipp-agent-workspace\calendar_journal_agent" in cmd, (sid, cmd)


@pytest.mark.parametrize("brief", [
    {"agent_name": "calendar_journal_agent", "features": ["x"], "screens": [], "tools": [{"name": "add_event"}], "q1": "a", "q2": "b"},
    {"agent_name": "calendar_journal_agent", "features": [{"id": "F1"}, {"id": "F2"}], "screens": [{"id": "S1"}],
     "tools": [{"name": "add_event"}], "q1": "$(rm)", "q2": "b"},
    {"agent_name": "../../etc", "tools": [{"name": "x_y_z"}], "q1": "a", "q2": "b"},
    "not a dict",
])
def test_forged_client_brief_is_rejected_without_crashing(brief):
    assert agent_module._restore_brief(brief) == {}
