# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""研修スキル（リポジトリ直下 .agents/skills/）と、それを参照する HITMAN・マニュアル・画面の整合性テスト。

背景: HITMAN のプロンプトが存在しないスキル（google-agents-cli-adk-code-ja 等）を指定していたり、
スキルの name とフォルダ名が食い違っていた（build-rag / rag-engine-setup 等）ため、
Antigravity（Gemini）が参照すべき手順書を見つけられない状態になっていた。
"""

import re
from pathlib import Path

import pytest

import app.agent as agent_module

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO_ROOT / ".agents" / "skills"
REFERENCING_FILES = [
    REPO_ROOT / "hitman" / "app" / "agent.py",
    REPO_ROOT / "hitman" / "frontend" / "static" / "index.html",
    REPO_ROOT / "TRAINING_LAB_MANUAL.md",
]

_SKILL_PHRASE = re.compile(r"スキル((?:「[A-Za-z0-9_-]+」(?:および|、|と|,\s*)?)+)")
_BRACKETED = re.compile(r"「([A-Za-z0-9_-]+)」")
_SKILL_PATH = re.compile(r"\.agents[/\\]skills[/\\]([A-Za-z0-9_-]+)")
_MARKER = re.compile(r"\[skill:([a-z0-9-]+)@v\d+\]")


def _frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md に YAML frontmatter がありません"
    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)", fm, re.M)
    desc = re.search(r"^description:\s*(.*)", fm, re.M)
    return {"name": name.group(1) if name else None, "description": (desc.group(1) if desc else "").strip()}


def _installed_skills() -> set[str]:
    return {d.name for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file()}


def _referenced_skills(text: str) -> set[str]:
    refs: set[str] = set()
    for phrase in _SKILL_PHRASE.findall(text):
        refs.update(_BRACKETED.findall(phrase))
    refs.update(_SKILL_PATH.findall(text))
    refs.update(_MARKER.findall(text))
    return refs


def test_skills_directory_exists():
    assert SKILLS_DIR.is_dir(), f"{SKILLS_DIR} がありません"
    assert "ipp-skill-check" in _installed_skills()


@pytest.mark.parametrize("skill_dir", sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir()))
def test_skill_name_matches_folder_and_has_marker(skill_dir):
    text = (SKILLS_DIR / skill_dir / "SKILL.md").read_text(encoding="utf-8")
    fm = _frontmatter(text)
    # Antigravity の / 候補やスラッシュコマンドは name で表示される。フォルダ名と一致させて参照ずれを防ぐ
    assert fm["name"] == skill_dir, f"name '{fm['name']}' がフォルダ名 '{skill_dir}' と一致しません"
    assert fm["description"], "description は必須です（Antigravity はこれでスキルの起動可否を判断する）"
    assert f"[skill:{skill_dir}@v1]" in text, "HITMAN 使用証跡の出力ルール（[skill:名前@v1]）がありません"


@pytest.mark.parametrize("path", REFERENCING_FILES, ids=lambda p: p.name)
def test_every_referenced_skill_exists(path):
    text = path.read_text(encoding="utf-8")
    missing = sorted(_referenced_skills(text) - _installed_skills())
    assert not missing, f"{path.name} が存在しないスキルを参照しています: {missing}"


def test_summoned_and_expected_skills_exist():
    installed = _installed_skills()
    ideas = [
        "障害ログを自動解析するボット",
        "社内規程マニュアルのFAQ検索Bot",
        "前回の好みを記憶して提案するアシスタント",
        "写真から部品を認識する点検アプリ",
    ]
    for idea in ideas:
        res = agent_module.guide_training_app_creation(idea, "original", is_confirmed=False)
        missing = sorted(set(res["summoned_skills"]) - installed)
        assert not missing, f"guide_training_app_creation が存在しないスキルを召喚: {missing} (idea={idea})"
    for step, skills in agent_module.EXPECTED_SKILLS_BY_STEP.items():
        assert set(skills) <= installed, f"{step} の想定スキルが存在しません: {skills}"


def test_t1_copies_skills_to_workspace_root():
    """Antigravity はワークスペース直下の .agents/skills しか読まない。T-1 はそこへコピーさせること。"""
    for course in ("original", "hitman_clone"):
        t1 = agent_module.get_training_sop(course)["T-1"]
        assert "copytree" in t1["command"] and "'.agents'" in t1["command"]
        assert "/ipp-skill-check" in t1["agy_prompt"]
        assert "新しい会話" in t1["agy_prompt"]


def _bundled_evidences() -> dict:
    """画面の『🧪 ログ注入』用サンプル（index.html の TEST_EVIDENCES）を取り出す。"""
    html = (REPO_ROOT / "hitman" / "frontend" / "static" / "index.html").read_text(encoding="utf-8")
    start = html.index("const TEST_EVIDENCES = {")
    body = html[start: html.index("\n};", start)]
    courses = {}
    for course in ("original", "hitman_clone"):
        seg = body[body.index(f"{course}: {{"):]
        seg = seg[: seg.index("\n  }")]
        courses[course] = {
            k: v.replace("\\\\", "\\") for k, v in re.findall(r'"(T-\d)": `([^`]*)`', seg)
        }
    return courses


@pytest.mark.parametrize("course", ["original", "hitman_clone"])
def test_bundled_sample_logs_follow_current_rules(course):
    """デモ用サンプルログ（🧪ログ注入）が現行の判定ルールと乖離していないこと。
    - T-2: コースAは企画未確定なら不合格。確定した企画（サンプルと同じエージェント名）なら合格
    - T-3: サンプルは受講生ごとの確認コードを持たないため、貼り付けだけでは合格しない（実機で起きた誤合格の防止）
    - T-1/T-4/T-5/T-6: そのまま合格"""
    from tests.unit.test_smoke_judge import _run, analyze_log

    evid = _bundled_evidences()[course]
    assert sorted(evid) == ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6"]
    store: dict = {}
    ctx = type("Ctx", (), {"state": store})()
    agent_module.set_operation_mode("TRAINING", tool_context=ctx)
    agent_module.set_training_course(course, tool_context=ctx)
    st = agent_module.HitmanState(store)

    def ok(step, text):
        res = agent_module.verify_step_output(step, text, tool_context=ctx)
        assert res["w_check_status"] == "VERIFIED_APPROVED", (step, res.get("message"))
        assert not res["skills_missing"], (step, res["skills_missing"])

    ok("T-1", evid["T-1"])
    slug = "my_hitman" if course == "hitman_clone" else "my_agent"
    if course == "original":
        res = agent_module.verify_step_output("T-2", evid["T-2"], tool_context=ctx)
        assert res["verdict"] == "FAILED" and st.current_step == "T-2"
        st.agent_slug, st.plan_confirmed = slug, True  # サンプルと同じ企画で確定した想定
    ok("T-2", evid["T-2"])
    res = agent_module.verify_step_output("T-3", evid["T-3"], tool_context=ctx)
    assert res["w_check_status"] == "BLOCKED_RETRY" and st.current_step == "T-3", res.get("message")
    ok("T-3", "[skill:ipp-agent-smoke-test@v1]\n" + _run(analyze_log, nonce=st.t3_nonce, agent_dir=slug))
    for step in ["T-4", "T-5", "T-6"]:
        ok(step, evid[step])
    assert st.snapshot()["completed"] is True


@pytest.mark.parametrize("skill_dir", sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir()))
def test_skill_frontmatter_is_valid_yaml(skill_dir):
    """frontmatter が YAML として読めないスキルは Antigravity に読み込まれない（record-demo で発生していた）。"""
    import yaml
    text = (SKILLS_DIR / skill_dir / "SKILL.md").read_text(encoding="utf-8")
    fm = re.match(r"---\n(.*?)\n---\n", text, re.S).group(1)
    data = yaml.safe_load(fm)
    assert data["name"] == skill_dir and data["description"]


def _bundled_ng_evidences() -> dict:
    """🧪ログ注入の異常パターン（index.html の TEST_EVIDENCES_NG）を取り出す。"""
    html = (REPO_ROOT / "hitman" / "frontend" / "static" / "index.html").read_text(encoding="utf-8")
    start = html.index("const TEST_EVIDENCES_NG = {")
    body = html[start: html.index("\n};", start)]
    seg = body[body.index("original: {"):]
    seg = seg[: seg.index("\n  }")]
    orig = {k: v.replace("\\\\", "\\") for k, v in re.findall(r'"(T-\d)": `([^`]*)`', seg)}
    tail = html[html.index("TEST_EVIDENCES_NG.hitman_clone = Object.assign"):]
    tail = tail[: tail.index("});")]
    hc = dict(orig, **{k: v.replace("\\\\", "\\") for k, v in re.findall(r'"(T-\d)": `([^`]*)`', tail)})
    return {"original": orig, "hitman_clone": hc}


@pytest.mark.parametrize("course", ["original", "hitman_clone"])
def test_log_injection_normal_and_abnormal_patterns(course):
    """🧪ログ注入: 各ステップで『正常＝合格』『異常＝不合格（ステップは進まない）』になること。
    T-2（コースA）/T-3 の正常と T-3 の異常は、受講生の企画・確認コードに紐づけてサーバが生成する。"""
    ok_static = _bundled_evidences()[course]
    ng_static = _bundled_ng_evidences()[course]
    assert sorted(ng_static) == ["T-1", "T-2", "T-4", "T-5", "T-6"]
    store: dict = {}
    ctx = type("Ctx", (), {"state": store})()
    agent_module.set_operation_mode("TRAINING", tool_context=ctx)
    agent_module.set_training_course(course, tool_context=ctx)
    st = agent_module.HitmanState(store)
    if course == "original":
        # 企画未確定なら T-2 の正常ログは生成しない（案内のみ）
        assert agent_module.build_demo_evidence("T-2", "ok", st)["text"] is None
        agent_module.update_project_plan("カレンダーとタスクと写真日記をまとめるツール", "confirmed",
                                         agent_name="photo_diary_agent", tool_context=ctx)

    def ok_log(step):
        gen = agent_module.build_demo_evidence(step, "ok", st)["text"]
        return gen or ok_static[step]

    def ng_log(step):
        gen = agent_module.build_demo_evidence(step, "ng", st)["text"]
        return gen or ng_static[step]

    for step in ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6"]:
        res = agent_module.verify_step_output(step, ng_log(step), tool_context=ctx)
        assert res["verdict"] == "FAILED" and st.current_step == step, (step, res.get("message"))
        res = agent_module.verify_step_output(step, ok_log(step), tool_context=ctx)
        assert res["w_check_status"] == "VERIFIED_APPROVED", (step, res.get("message"))
    assert st.snapshot()["completed"] is True
    if course == "original":
        assert "photo_diary_agent" in ok_log("T-3")


def test_demo_evidence_endpoint_is_disabled_on_cloud_run(monkeypatch):
    import frontend.main as main_module
    monkeypatch.delenv("HITMAN_DEMO_EVIDENCE", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert main_module._demo_evidence_enabled() is True
    monkeypatch.setenv("K_SERVICE", "hitman")
    assert main_module._demo_evidence_enabled() is False
    monkeypatch.setenv("HITMAN_DEMO_EVIDENCE", "1")
    assert main_module._demo_evidence_enabled() is True
