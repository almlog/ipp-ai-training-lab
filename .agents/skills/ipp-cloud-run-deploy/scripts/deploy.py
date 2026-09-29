#!/usr/bin/env python
"""IPP AI研修 T-5: 受講生のアプリを Cloud Run へ安全にデプロイし、実際に動くことを確かめる。

認証情報の扱い（平文を残さない）:
- Gemini API キーは <agent-dir>/.env（または環境変数）から読み、Secret Manager に「標準入力で」登録する
  （コマンドライン引数・画面・ログにキーの値を出さない）
- Cloud Run には --set-secrets で Secret Manager の参照だけを渡す（--set-env-vars にキーを書かない）
- .env は .gcloudignore / .dockerignore で除外し、ソースのアップロード・コンテナに含めない
- デプロイ前に secret_scan で、コード等にキーが直書きされていないことを確認する

デプロイ後の確認（HITMAN に提出する客観ログ）:
- GET  <URL>/health が 200
- POST <URL>/chat（{"message": 質問}）が 200 で、AI の応答テキストが返る

使い方（ワークスペースのルートで）:
  python .agents/skills/ipp-cloud-run-deploy/scripts/deploy.py --agent-dir ipp-agent-workspace/<エージェント名> \
      --service <サービス名> --nonce <確認コード> --q "<動作確認の質問>"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MARKER = "[skill:ipp-cloud-run-deploy@v1]"
DIGEST_SALT = "ipp-deploy-v1"
KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

_SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_SKILLS / "ipp-secure-credentials" / "scripts"))
from env_setup import ensure_ignored  # noqa: E402
from secret_scan import scan  # noqa: E402


def digest_of(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((DIGEST_SALT + canonical).encode("utf-8")).hexdigest()[:16]


def _read_key(agent_dir: Path) -> str:
    """キーの値を返す（呼び出し元は絶対に表示・ログ出力しないこと）。"""
    for k in KEY_NAMES:
        if os.environ.get(k):
            return os.environ[k].strip()
    env = agent_dir / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() in KEY_NAMES and v.strip().strip('"').strip("'"):
                return v.strip().strip('"').strip("'")
    return ""


def _gcloud() -> str:
    path = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not path:
        raise SystemExit("gcloud コマンドが見つかりません。Google Cloud CLI をインストールし、gcloud auth login を実行してください。")
    return path


def _run(args: list[str], *, stdin: str | None = None, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """gcloud を実行する。キーを渡すときは必ず stdin を使い、引数には入れない。"""
    proc = subprocess.run(
        [_gcloud(), *args],
        input=stdin,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    if check and proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()[-5:]
        raise SystemExit(f"gcloud {' '.join(args[:3])} が失敗しました:\n" + "\n".join(err))
    return proc


def _http(method: str, url: str, body: dict | None = None, timeout: int = 90) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001  接続失敗も結果として記録する
        return 0, f"{type(e).__name__}: {e}"


def reply_text(raw: str) -> str:
    """/chat の応答（{"reply": ...} または {"parts": [...]}）から AI の応答テキストを取り出す。"""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if isinstance(obj, dict):
        if isinstance(obj.get("reply"), str):
            return obj["reply"].strip()
        texts = [p.get("text", "") for p in obj.get("parts") or [] if isinstance(p, dict)]
        return "\n".join(t for t in texts if t).strip()
    return ""


def health_check(url: str, health_path: str, question: str, attempts: int = 3) -> dict:
    checks = {"health_http": False, "chat_http": False, "chat_reply": False}
    status_health = status_chat = 0
    reply = ""
    for i in range(attempts):
        status_health, _ = _http("GET", url.rstrip("/") + "/health", timeout=30)
        status_chat, raw = _http("POST", url.rstrip("/") + health_path, {"message": question, "user_id": "ipp-deploy-check"})
        reply = reply_text(raw)
        checks = {
            "health_http": status_health == 200,
            "chat_http": status_chat == 200,
            "chat_reply": bool(reply) and not reply.lower().startswith(("error", "⚠️")),
        }
        if all(checks.values()):
            break
        if i + 1 < attempts:
            time.sleep(10)  # コールドスタート待ち
    return {"checks": checks, "status_health": status_health, "status_chat": status_chat, "reply_excerpt": reply[:200]}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="IPP AI研修: Cloud Run への安全なデプロイと動作確認")
    ap.add_argument("--agent-dir", required=True)
    ap.add_argument("--service", required=True)
    ap.add_argument("--nonce", default="")
    ap.add_argument("--q", required=True, help="デプロイ後に /chat へ送る動作確認の質問")
    ap.add_argument("--region", default="asia-northeast1")
    ap.add_argument("--health-path", default="/chat")
    ap.add_argument("--project", default="")
    args = ap.parse_args(argv)

    agent_dir = Path(args.agent_dir)
    if not agent_dir.is_dir():
        raise SystemExit(f"{agent_dir} が見つかりません。")

    # 1. 除外設定と漏えい検査（キーがコード等に直書きされていたらデプロイしない）
    ensure_ignored(agent_dir)
    findings, problems = scan(agent_dir)
    if findings or problems:
        for p, kinds in findings:
            print(f"NG {p}: {'、'.join(kinds)}（値は表示しません）", file=sys.stderr)
        for m in problems:
            print(f"NG {m}", file=sys.stderr)
        raise SystemExit("認証情報の漏えいの恐れがあるためデプロイを中止しました。secret_scan.py の結果を直してください。")

    key = _read_key(agent_dir)
    if not key:
        raise SystemExit(f"{agent_dir / '.env'} に GEMINI_API_KEY が設定されていません（エディタで設定してください）。")
    vertex = "true" if key.startswith("AQ.") else "false"

    project = args.project or _run(["config", "get-value", "project"]).stdout.strip()
    if not project:
        raise SystemExit("Google Cloud のプロジェクトが未設定です。gcloud config set project <プロジェクトID> を実行してください。")
    pflag = ["--project", project]

    print(f"[deploy] プロジェクト: {project} / サービス: {args.service} / リージョン: {args.region}", file=sys.stderr)
    _run(["services", "enable", "run.googleapis.com", "cloudbuild.googleapis.com",
          "artifactregistry.googleapis.com", "secretmanager.googleapis.com", "--quiet", *pflag])

    # 2. Secret Manager にキーを登録（標準入力で渡す。引数・画面には出さない）
    secret = f"{args.service}-gemini-api-key"[:255]
    if _run(["secrets", "describe", secret, *pflag], check=False).returncode != 0:
        _run(["secrets", "create", secret, "--replication-policy=automatic", "--quiet", *pflag])
    _run(["secrets", "versions", "add", secret, "--data-file=-", "--quiet", *pflag], stdin=key)
    key = ""  # 以降は使わない
    print(f"[deploy] Secret Manager に登録しました: {secret}（値は表示しません）", file=sys.stderr)

    # --format=value(...) の括弧は Windows の gcloud.cmd 経由で壊れることがあるため JSON で受け取る
    number = str(json.loads(_run(["projects", "describe", project, "--format=json"]).stdout or "{}").get("projectNumber", ""))
    if not number:
        raise SystemExit("プロジェクト番号を取得できませんでした（gcloud projects describe）。")
    runtime_sa = f"{number}-compute@developer.gserviceaccount.com"
    _run(["secrets", "add-iam-policy-binding", secret, f"--member=serviceAccount:{runtime_sa}",
          "--role=roles/secretmanager.secretAccessor", "--quiet", *pflag])

    # 3. 以前に --set-env-vars でキーを平文で渡していた場合は取り除く（同名の変数があると --set-secrets が失敗する）
    plaintext_removed = False
    existing = _run(["run", "services", "describe", args.service, "--region", args.region, "--format=json", *pflag], check=False)
    if existing.returncode == 0 and existing.stdout.strip():
        try:
            containers = json.loads(existing.stdout)["spec"]["template"]["spec"]["containers"]
            plain = sorted({e.get("name") for c in containers for e in c.get("env") or []
                            if e.get("name") in KEY_NAMES and "value" in e})
        except (ValueError, KeyError, TypeError):
            plain = []
        if plain:
            _run(["run", "services", "update", args.service, "--region", args.region, "--quiet",
                  f"--remove-env-vars={','.join(plain)}", *pflag])
            plaintext_removed = True
            print("[deploy] ⚠️ 以前のデプロイで API キーが平文の環境変数として設定されていたため削除しました。"
                  "古いリビジョンの設定には残っているため、このキーは漏えいしたものとして無効化・再発行し、.env を更新してから再実行してください。",
                  file=sys.stderr)

    # 4. デプロイ（キーは Secret Manager の参照だけを渡す）
    print("[deploy] Cloud Run へデプロイ中（数分かかります）…", file=sys.stderr)
    deploy = _run([
        "run", "deploy", args.service, "--source", str(agent_dir), "--region", args.region,
        "--allow-unauthenticated", "--max-instances", "1", "--quiet",
        f"--set-secrets=GEMINI_API_KEY={secret}:latest",
        f"--set-env-vars=GOOGLE_GENAI_USE_VERTEXAI={vertex},GOOGLE_GENAI_USE_ENTERPRISE={vertex}",
        *pflag,
    ], check=False)
    deployed = deploy.returncode == 0
    url = ""
    if deployed:
        desc = _run(["run", "services", "describe", args.service, "--region", args.region, "--format=json", *pflag]).stdout
        url = str(json.loads(desc or "{}").get("status", {}).get("url", ""))
    else:
        tail = "\n".join((deploy.stderr or "").strip().splitlines()[-8:])
        print(f"[deploy] デプロイに失敗しました:\n{tail}", file=sys.stderr)

    # 5. 実際に動くかを確認する
    hc = health_check(url, args.health_path, args.q) if url else {
        "checks": {"health_http": False, "chat_http": False, "chat_reply": False},
        "status_health": 0, "status_chat": 0, "reply_excerpt": "",
    }
    data = {
        "service": args.service,
        "region": args.region,
        "nonce": args.nonce,
        "url": url,
        "secret_ref": secret,
        "deployed": deployed,
        "checks": hc["checks"],
        "status_health": hc["status_health"],
        "status_chat": hc["status_chat"],
        "reply_excerpt": hc["reply_excerpt"],
        "plaintext_env_removed": plaintext_removed,
    }
    data["passed"] = bool(deployed and url and all(hc["checks"].values()))

    lines = [
        MARKER,
        f"$ python .agents/skills/ipp-cloud-run-deploy/scripts/deploy.py --agent-dir {agent_dir.as_posix()} --service {args.service} --nonce {args.nonce}",
        f"service: {args.service}  region: {args.region}  nonce: {args.nonce}",
        f"secret: {secret}（Secret Manager 参照。値は表示しません）",
        f"Service URL: {url or '(なし)'}",
    ]
    for k, v in hc["checks"].items():
        lines.append(f"check {k}: {'OK' if v else 'NG'}")
    lines.append(f"http: health={hc['status_health']} chat={hc['status_chat']}")
    lines.append("reply: " + hc["reply_excerpt"].replace("\n", " ")[:150])
    lines.append("DEPLOY_RESULT: " + ("PASS" if data["passed"] else "FAIL"))
    lines.append("DEPLOY_JSON: " + json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    lines.append("DEPLOY_DIGEST: " + digest_of(data))
    print("```text")
    print("\n".join(lines))
    print("```")
    if not data["passed"]:
        print("DEPLOY_RESULT が FAIL です。Cloud Run のログ（gcloud run services logs read "
              f"{args.service} --region {args.region} --limit 50）で原因を確認して直し、再実行してください。", file=sys.stderr)
    return 0 if data["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
