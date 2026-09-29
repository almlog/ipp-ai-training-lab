#!/usr/bin/env python
"""IPP AI研修: エージェント／アプリのフォルダに .env を安全に用意する。

- <agent-dir>/.env.example を作る（キーの値は空）
- <agent-dir>/.env が無ければ、値が空のものを作る（既存の .env は一切読み取り表示しない・上書きしない）
- <agent-dir> の .gitignore / .dockerignore / .gcloudignore に .env を追加する
- GEMINI_API_KEY が設定済みかどうかだけを表示する（値・長さ・先頭文字は表示しない）

使い方:
  python .agents/skills/ipp-secure-credentials/scripts/env_setup.py --agent-dir ipp-agent-workspace/<エージェント名>
  python .agents/skills/ipp-secure-credentials/scripts/env_setup.py --agent-dir ipp-agent-workspace/<エージェント名> --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
ENV_EXAMPLE = (
    "# Gemini API キー（各自のキーを .env に書く。このファイル .env.example には値を書かない）\n"
    "GEMINI_API_KEY=\n"
)
ENV_TEMPLATE = (
    "# ここにご自身の Gemini API キーを貼り付けて保存してください（チャットには貼らないこと）\n"
    "# このファイルは Git・コンテナに含まれません（.gitignore / .dockerignore / .gcloudignore で除外済み）\n"
    "GEMINI_API_KEY=\n"
)
IGNORE_FILES = (".gitignore", ".dockerignore", ".gcloudignore")
IGNORE_LINES = (".env", ".env.*", "!.env.example")


def key_is_set(env_path: Path) -> bool:
    """.env に GEMINI_API_KEY（または GOOGLE_API_KEY）の値が入っているか。値そのものは返さない。"""
    if not env_path.is_file():
        return False
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() in KEY_NAMES and v.strip().strip('"').strip("'"):
            return True
    return False


def ensure_ignored(agent_dir: Path) -> list[str]:
    changed = []
    for name in IGNORE_FILES:
        p = agent_dir / name
        existing = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
        missing = [ln for ln in IGNORE_LINES if ln not in existing]
        if name == ".gcloudignore" and not p.is_file():
            # .gcloudignore を新規作成すると gcloud は .gitignore を自動では使わなくなるため、明示的に取り込む
            missing = ["#!include:.gitignore", *missing]
        if missing:
            with p.open("a", encoding="utf-8") as f:
                if existing and existing[-1].strip():
                    f.write("\n")
                f.write("\n".join(missing) + "\n")
            changed.append(name)
    return changed


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="IPP AI研修: .env を安全に用意する")
    ap.add_argument("--agent-dir", required=True)
    ap.add_argument("--check", action="store_true", help="作成はせず、設定状況だけを表示する")
    args = ap.parse_args(argv)

    agent_dir = Path(args.agent_dir)
    env_path = agent_dir / ".env"
    if not args.check:
        agent_dir.mkdir(parents=True, exist_ok=True)
        example = agent_dir / ".env.example"
        if not example.is_file():
            example.write_text(ENV_EXAMPLE, encoding="utf-8")
            print(f"作成: {example}")
        if not env_path.is_file():
            env_path.write_text(ENV_TEMPLATE, encoding="utf-8")
            print(f"作成: {env_path}（値は空です）")
        for name in ensure_ignored(agent_dir):
            print(f"更新: {agent_dir / name} に .env の除外設定を追加")

    ignored = all(
        (agent_dir / n).is_file() and ".env" in (agent_dir / n).read_text(encoding="utf-8").splitlines()
        for n in IGNORE_FILES
    )
    print(f".env の除外設定（.gitignore/.dockerignore/.gcloudignore）: {'OK' if ignored else '不足（--check を外して実行してください）'}")
    if key_is_set(env_path):
        print("GEMINI_API_KEY: 設定済み")
        return 0 if ignored else 1
    print("GEMINI_API_KEY: 未設定")
    print(f"→ エディタで {env_path} を開き、GEMINI_API_KEY= の後ろにご自身のキーを貼り付けて保存してください（チャットには貼らないこと）。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
