# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""認証情報を平文で扱わないための仕組みのテスト。

- HITMAN: チャット・提出ログに API キーがあれば遮断（app/secret_guard.py）
- 受講生側スキル ipp-secure-credentials: .env の用意（値を表示しない）と漏えい検査
- 受講生側スキル ipp-cloud-run-deploy: キーを引数に入れず標準入力で Secret Manager へ渡す
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

import app.agent as agent_module
from app.secret_guard import SECRET_PATTERNS, find_secrets, redact

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = REPO_ROOT / ".agents" / "skills"
FAKE_AISTUDIO = "AIza" + "Sy" + "B" * 33
FAKE_EXPRESS = "AQ." + "Ab8RN6" + "x" * 40


def _load(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("text", [
    f"key={FAKE_AISTUDIO}",
    f"$env:GEMINI_API_KEY=\"{FAKE_AISTUDIO}\"",
    f"gcloud run deploy x --set-env-vars GEMINI_API_KEY={FAKE_EXPRESS}",
    "GOOGLE_API_KEY=abcdefGhijklmnopqrstuvwxyz0123",
    "キーは" + FAKE_EXPRESS,  # 日本語の直後でも検知する
    "ghp_" + "a" * 36,
    "-----BEGIN PRIVATE KEY-----\nMIIE",
])
def test_secrets_are_detected_and_redacted(text):
    assert find_secrets(text)
    assert not find_secrets(redact(text))


@pytest.mark.parametrize("text", [
    "GEMINI_API_KEY: ローカルは .env から読み込む。本番は Secret Manager から渡す。",
    "GEMINI_API_KEY=",
    "GEMINI_API_KEY=<あなたのキー>",
    "--set-secrets=GEMINI_API_KEY=calendar-journal-agent-gemini-api-key:latest",
    "GEMINI_API_KEY: 設定済み",
    "genai.Client(api_key=settings.gemini_api_key)",
    "GEMINI_API_KEY = my-agent-gemini-api-key-v2",
    "ACCESS_TOKEN: the_token_you_get_from_console",
])
def test_safe_texts_are_not_flagged(text):
    assert find_secrets(text) == [], text


def test_secret_scan_rules_on_the_setting_side_match_hitman():
    """受講生側（スキル）と HITMAN で、同じ判定ルールを使う。"""
    assert (SKILLS / "ipp-secure-credentials" / "scripts" / "secret_guard.py").read_bytes() == \
        (REPO_ROOT / "hitman" / "app" / "secret_guard.py").read_bytes()
    html = (REPO_ROOT / "hitman" / "frontend" / "static" / "index.html").read_text(encoding="utf-8")
    body = html[html.index("const SECRET_PATTERNS = ["):]
    body = body[: body.index("];")]
    js = re.findall(r"^  /(.*)/[a-z]*,$", body, re.M)
    assert len(js) == len(SECRET_PATTERNS)
    anchors = ["AIza", "AQ\\.", "ya29\\.", "gh[pousr]_", "PRIVATE KEY-----", "private_key", "(?=[0-9A-Za-z_\\-]*[A-Z])"]
    for (_kind, pat), js_src, anchor in zip(SECRET_PATTERNS, js, anchors, strict=True):
        assert anchor in pat.pattern and anchor in js_src, (anchor, js_src)


def test_verify_never_approves_logs_containing_keys():
    store: dict = {}
    ctx = type("Ctx", (), {"state": store})()
    agent_module.set_operation_mode("TRAINING", tool_context=ctx)
    log = "[skill:ipp-skill-check@v1]\nPS C:\\work> Get-ChildItem .agents\\skills -Name\nipp-skill-check\n" + f"GEMINI_API_KEY={FAKE_AISTUDIO}"
    res = agent_module.verify_step_output("T-1", log, tool_context=ctx)
    assert res["verdict"] == "FAILED" and res["w_check_status"] == "SECRET_LEAK_BLOCKED"
    assert FAKE_AISTUDIO not in json.dumps(res, ensure_ascii=False)
    assert agent_module.HitmanState(store).current_step == "T-1"


def test_all_prompts_forbid_plaintext_keys():
    """AntiGravity 用プロンプトが、キーを平文で扱う手順を案内していないこと。"""
    from tests.unit.brief_fixtures import CALENDAR_BRIEF, set_brief

    st = agent_module.HitmanState({})
    agent_module.select_training_course(st, "original")
    set_brief(st, CALENDAR_BRIEF)
    st.issue_t3_nonce()
    for course in ("original", "hitman_clone"):
        sop = agent_module.get_training_sop(course, state=st)
        for sid, step in sop.items():
            text = json.dumps(step, ensure_ascii=False)
            assert not re.search(r"--set-env-vars[= ]\S*(GEMINI|GOOGLE)_API_KEY", text), (course, sid)
            assert "$env:GEMINI_API_KEY" not in text and "export GEMINI_API_KEY" not in text, (course, sid)
            assert find_secrets(text) == [], (course, sid)
        for sid in ("T-3", "T-5", "T-6"):
            assert "ipp-secure-credentials" in sop[sid]["agy_prompt"] or "secret_scan.py" in sop[sid]["agy_prompt"], (course, sid)


# --- 受講生側スキル: ipp-secure-credentials ---------------------------------------------

def test_env_setup_creates_ignored_env_and_never_prints_value(tmp_path, capsys):
    env_setup = _load(SKILLS / "ipp-secure-credentials" / "scripts" / "env_setup.py", "ipp_env_setup")
    app = tmp_path / "calendar_journal_agent"
    assert env_setup.main(["--agent-dir", str(app)]) == 1  # まだキーが無い
    out = capsys.readouterr().out
    assert "GEMINI_API_KEY: 未設定" in out
    for name in (".gitignore", ".dockerignore", ".gcloudignore"):
        assert ".env" in (app / name).read_text(encoding="utf-8").splitlines()
    assert "#!include:.gitignore" in (app / ".gcloudignore").read_text(encoding="utf-8")
    assert (app / ".env.example").read_text(encoding="utf-8").strip().endswith("GEMINI_API_KEY=")

    # 受講生がエディタでキーを書いた想定
    (app / ".env").write_text(f"GEMINI_API_KEY={FAKE_AISTUDIO}\n", encoding="utf-8")
    assert env_setup.main(["--agent-dir", str(app), "--check"]) == 0
    out = capsys.readouterr().out
    assert "GEMINI_API_KEY: 設定済み" in out
    assert FAKE_AISTUDIO not in out and FAKE_AISTUDIO[:6] not in out
    # 既存の .env は上書きしない
    env_setup.main(["--agent-dir", str(app)])
    assert FAKE_AISTUDIO in (app / ".env").read_text(encoding="utf-8")


def test_secret_scan_finds_hardcoded_key_but_ignores_env(tmp_path, capsys):
    env_setup = _load(SKILLS / "ipp-secure-credentials" / "scripts" / "env_setup.py", "ipp_env_setup2")
    scan = _load(SKILLS / "ipp-secure-credentials" / "scripts" / "secret_scan.py", "ipp_secret_scan")
    app = tmp_path / "app1"
    env_setup.main(["--agent-dir", str(app)])
    (app / ".env").write_text(f"GEMINI_API_KEY={FAKE_AISTUDIO}\n", encoding="utf-8")
    (app / "agent.py").write_text("import credentials\ncredentials.configure()\n", encoding="utf-8")
    capsys.readouterr()
    assert scan.main([str(app)]) == 0
    assert "SECRET_SCAN: PASS" in capsys.readouterr().out

    (app / "main.py").write_text(f'API_KEY = "{FAKE_AISTUDIO}"\n', encoding="utf-8")
    assert scan.main([str(app)]) == 1
    out = capsys.readouterr().out
    assert "SECRET_SCAN: FAIL" in out and "main.py" in out
    assert FAKE_AISTUDIO not in out


def test_credentials_helper_reads_env_and_switches_vertex(tmp_path, monkeypatch):
    src = SKILLS / "ipp-build-app-from-brief" / "scripts" / "credentials.py"
    app = tmp_path / "app2"
    app.mkdir()
    (app / "credentials.py").write_bytes(src.read_bytes())
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GENAI_USE_ENTERPRISE"):
        monkeypatch.delenv(k, raising=False)
    creds = _load(app / "credentials.py", "ipp_credentials_a")
    with pytest.raises(RuntimeError) as e:
        creds.configure()
    assert ".env" in str(e.value)

    (app / ".env").write_text(f"GEMINI_API_KEY={FAKE_EXPRESS}\n", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "p")
    mode = creds.configure()
    import os
    assert "Vertex" in mode and os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "true"
    assert "GOOGLE_CLOUD_PROJECT" not in os.environ
    assert FAKE_EXPRESS not in mode


# --- 受講生側スキル: ipp-cloud-run-deploy ------------------------------------------------

def test_deploy_script_passes_key_only_via_stdin_and_secret_reference(tmp_path, monkeypatch, capsys):
    deploy = _load(SKILLS / "ipp-cloud-run-deploy" / "scripts" / "deploy.py", "ipp_deploy")
    env_setup = _load(SKILLS / "ipp-secure-credentials" / "scripts" / "env_setup.py", "ipp_env_setup3")
    app = tmp_path / "calendar_journal_agent"
    env_setup.main(["--agent-dir", str(app)])
    (app / ".env").write_text(f"GEMINI_API_KEY={FAKE_AISTUDIO}\n", encoding="utf-8")
    (app / "main.py").write_text("print('ok')\n", encoding="utf-8")
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)

    calls = []

    class P:
        def __init__(self, stdout="", rc=0):
            self.stdout, self.stderr, self.returncode = stdout, "", rc

    def fake_run(args, *, stdin=None, check=True, capture=True):
        calls.append((list(args), stdin))
        if args[:3] == ["config", "get-value", "project"]:
            return P("my-proj\n")
        if args[:2] == ["secrets", "describe"]:
            return P(rc=1)
        if args[:2] == ["projects", "describe"]:
            return P(json.dumps({"projectNumber": "123"}))
        if args[:3] == ["run", "services", "describe"]:
            # 1回目: 以前のデプロイで平文の環境変数にキーが入っていた状態 / 2回目: デプロイ後の URL
            if not any(a[:3] == ["run", "services", "describe"] for a, _ in calls[:-1]):
                env = [{"name": "GEMINI_API_KEY", "value": "(平文のキー)"}, {"name": "OTHER", "value": "x"}]
                return P(json.dumps({"spec": {"template": {"spec": {"containers": [{"env": env}]}}}}))
            return P(json.dumps({"status": {"url": "https://calendar-journal-agent-xyz.asia-northeast1.run.app"}}))
        return P()

    monkeypatch.setattr(deploy, "_run", fake_run)
    monkeypatch.setattr(deploy, "health_check", lambda url, path, q, attempts=3: {
        "checks": {"health_http": True, "chat_http": True, "chat_reply": True},
        "status_health": 200, "status_chat": 200, "reply_excerpt": "登録しました"})
    rc = deploy.main(["--agent-dir", str(app), "--service", "calendar-journal-agent", "--nonce", "T3-ABC123", "--q", "予定を入れて"])
    out = capsys.readouterr()
    assert rc == 0
    # キーは引数・画面に出ない。標準入力で1回だけ渡す
    assert all(FAKE_AISTUDIO not in " ".join(a) for a, _ in calls)
    assert FAKE_AISTUDIO not in out.out + out.err
    stdin_calls = [a for a, s in calls if s is not None]
    assert stdin_calls == [["secrets", "versions", "add", "calendar-journal-agent-gemini-api-key", "--data-file=-", "--quiet", "--project", "my-proj"]]
    update = next(a for a, _ in calls if a[:3] == ["run", "services", "update"])
    assert "--remove-env-vars=GEMINI_API_KEY" in update  # 平文の環境変数は削除し、再発行を促す
    assert "無効化" in out.err
    run_deploy = next(a for a, _ in calls if a[:2] == ["run", "deploy"])
    assert "--set-secrets=GEMINI_API_KEY=calendar-journal-agent-gemini-api-key:latest" in run_deploy
    assert not any("API_KEY" in a for a in run_deploy if a.startswith("--set-env-vars"))
    # 出力は HITMAN の T-5 判定で合格する（同じ digest）
    block = out.out.split("```text\n", 1)[1].split("\n```", 1)[0]
    dep = agent_module.judge_deploy_output(block, expected_nonce="T3-ABC123", expected_service="calendar-journal-agent")
    assert dep["status"] == "PASS", dep


def test_deploy_script_refuses_when_key_is_hardcoded(tmp_path, monkeypatch):
    deploy = _load(SKILLS / "ipp-cloud-run-deploy" / "scripts" / "deploy.py", "ipp_deploy2")
    app = tmp_path / "agent_x"
    app.mkdir()
    (app / "agent.py").write_text(f'KEY = "{FAKE_AISTUDIO}"\n', encoding="utf-8")
    called = []
    monkeypatch.setattr(deploy, "_run", lambda *a, **k: called.append(a))
    with pytest.raises(SystemExit):
        deploy.main(["--agent-dir", str(app), "--service", "agent-x", "--q", "hi"])
    assert called == []  # gcloud を一度も呼ばない


def test_deploy_digest_is_shared_with_hitman():
    deploy = _load(SKILLS / "ipp-cloud-run-deploy" / "scripts" / "deploy.py", "ipp_deploy3")
    data = {"service": "a", "nonce": "T3-1", "checks": {"health_http": True}}
    assert deploy.digest_of(data) == agent_module._deploy_digest(data)
    assert deploy.MARKER == agent_module.DEPLOY_MARKER


@pytest.mark.parametrize("url,ok", [
    ("https://calendar-journal-agent-abc.asia-northeast1.run.app", True),
    ("http://calendar-journal-agent-abc.asia-northeast1.run.app", False),
    ("https://evil.example.com/calendar-journal-agent-abc.run.app", False),
    ("https://calendar-journal-agent-abc.run.app.evil.com", False),
    ("https://other-service-abc.asia-northeast1.run.app", False),
    ("https://user:pw@calendar-journal-agent-abc.asia-northeast1.run.app", False),
    ("https://calendar-journal-agent-abc.asia-northeast1.run.app:8443", False),
])
def test_hitman_only_accesses_the_students_cloud_run_url(url, ok):
    """公開URLの実地確認で、HITMAN が任意の URL へアクセスさせられない（SSRF 対策）。"""
    assert agent_module._is_cloud_run_url(url, "calendar-journal-agent") is ok


def test_live_check_does_not_follow_redirects(monkeypatch):
    """受講生のサービスが 302 で別の宛先へ誘導しても、HITMAN は追いかけない。"""
    import urllib.request

    seen = []

    class FakeResp:
        def __init__(self, status, body=b""):
            self.status, self._b = status, body

        def read(self, n=-1):
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    real_build = urllib.request.build_opener

    def build_opener(*handlers):
        opener = real_build(*handlers)
        assert any(getattr(h, "__name__", "") == "_NoRedirect" or type(h).__name__ == "_NoRedirect" for h in handlers)

        class O:
            def open(self, req, timeout=None):
                seen.append(req.full_url)
                return FakeResp(200, json.dumps({"reply": "ok"}).encode())
        return O()

    monkeypatch.setattr(urllib.request, "build_opener", build_opener)
    res = agent_module.live_deploy_check("https://calendar-journal-agent-x.asia-northeast1.run.app", "q")
    assert res["ok"] is True
    assert seen == ["https://calendar-journal-agent-x.asia-northeast1.run.app/health",
                    "https://calendar-journal-agent-x.asia-northeast1.run.app/chat"]


def test_malformed_port_does_not_crash_url_check():
    assert agent_module._is_cloud_run_url("https://calendar-journal-agent-1.x.run.app:abc/", "calendar-journal-agent") is False
