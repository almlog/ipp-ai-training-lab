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
def test_bundled_sample_logs_pass_every_step(course):
    """デモ用サンプルログが、現行の判定ルールで T-1〜T-6 を順に合格できること（判定ルールとの乖離を防ぐ）。"""
    evid = _bundled_evidences()[course]
    assert sorted(evid) == ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6"]
    store: dict = {}
    ctx = type("Ctx", (), {"state": store})()
    agent_module.set_operation_mode("TRAINING", tool_context=ctx)
    agent_module.set_training_course(course, tool_context=ctx)
    for step in ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6"]:
        res = agent_module.verify_step_output(step, evid[step], tool_context=ctx)
        assert res["w_check_status"] == "VERIFIED_APPROVED", (step, res.get("message"))
        assert not res["skills_missing"], (step, res["skills_missing"])
    assert agent_module.HitmanState(store).snapshot()["completed"] is True
