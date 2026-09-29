#!/usr/bin/env python
"""IPP AI研修: フォルダ内のファイルに認証情報（API キー等）が平文で書かれていないか検査する。

- .env / .env.* （.env.example を除く）はキーを置く場所なので検査対象外。代わりに除外設定を確認する
- 見つかった場合はファイルのパスと種類だけを表示する（値は表示しない）
- 最後に SECRET_SCAN: PASS / FAIL を表示する

使い方:
  python .agents/skills/ipp-secure-credentials/scripts/secret_scan.py ipp-agent-workspace/<エージェント名>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secret_guard import find_secrets  # noqa: E402

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache"}
MAX_BYTES = 2_000_000


def is_env_file(p: Path) -> bool:
    return p.name == ".env" or (p.name.startswith(".env.") and p.name != ".env.example")


def scan(root: Path) -> tuple[list[tuple[str, list[str]]], list[str]]:
    findings: list[tuple[str, list[str]]] = []
    problems: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if is_env_file(p):
            continue
        if p.name.endswith((".json",)) and "application_default_credentials" in p.name:
            findings.append((str(p), ["gcloud の認証情報ファイル"]))
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        kinds = find_secrets(text)
        if kinds:
            findings.append((str(p), kinds))
    for name in (".gitignore", ".dockerignore", ".gcloudignore"):
        f = root / name
        if not f.is_file() or ".env" not in f.read_text(encoding="utf-8").splitlines():
            problems.append(f"{f} に .env の除外設定がありません（env_setup.py を実行してください）")
    return findings, problems


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("使い方: secret_scan.py <フォルダ>", file=sys.stderr)
        return 2
    root = Path(args[0])
    findings, problems = scan(root)
    print(f"[secret-scan] 対象: {root}")
    for path, kinds in findings:
        print(f"NG {path}: {'、'.join(kinds)}（値は表示しません）")
    for msg in problems:
        print(f"NG {msg}")
    ok = not findings and not problems
    print("SECRET_SCAN: " + ("PASS" if ok else "FAIL"))
    if findings:
        print("→ 見つかったキーは漏えいしたものとして無効化・再発行し、コードからは .env 経由で読み込むよう直してください。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
