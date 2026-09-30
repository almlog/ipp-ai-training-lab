#!/usr/bin/env python
"""IPP AI実践研修: 演習環境セットアップスクリプト (Skills & MCP 自動配置)

目的:
1. 研修スキル (.agents/skills) をワークスペース直下に自動配置し、AntiGravity に読み込ませる。
2. 研修用 MCP 定義 (.agents/mcp) を受講生のホームディレクトリ (~/.gemini/antigravity/mcp) へ配置し、
   「Developer Knowledge MCP」および「Firebase MCP」を AntiGravity に即時認識させる。
"""

from __future__ import annotations

import os
import pathlib
import shutil
import sys


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    cwd = pathlib.Path.cwd().resolve()
    script_dir = pathlib.Path(__file__).resolve().parent
    repo_agents_dir = script_dir.parent  # .../.agents

    print("================================================================================")
    print("🚀 IPP AI実践研修: 演習環境（Skills & MCP）自動同期セットアップ")
    print("================================================================================")

    # 1. ワークスペース直下の .agents へスキル群を同期
    dest_workspace_agents = cwd / ".agents"
    if repo_agents_dir.resolve() != dest_workspace_agents.resolve():
        print(f"📦 1. 研修スキル群をワークスペース直下へ同期中...\n   -> {dest_workspace_agents}")
        shutil.copytree(repo_agents_dir, dest_workspace_agents, dirs_exist_ok=True)
    else:
        print(f"📦 1. 研修スキル群はすでにワークスペース直下に配置されています。")

    skills_dir = dest_workspace_agents / "skills"
    skill_count = len(list(skills_dir.iterdir())) if skills_dir.is_dir() else 0
    print(f"   [OK] {skill_count} 個の Skills が同期されました。")

    # 2. AntiGravity の MCP ディレクトリ (~/.gemini/antigravity/mcp) へ同期
    home_dir = pathlib.Path.home()
    antigravity_mcp_dir = home_dir / ".gemini" / "antigravity" / "mcp"
    src_mcp_dir = dest_workspace_agents / "mcp"

    print(f"\n☎️ 2. AntiGravity MCP（直通ツール）をユーザー環境へ同期中...\n   -> {antigravity_mcp_dir}")
    antigravity_mcp_dir.mkdir(parents=True, exist_ok=True)

    if src_mcp_dir.is_dir():
        for item in src_mcp_dir.iterdir():
            if item.is_dir():
                target_server_dir = antigravity_mcp_dir / item.name
                shutil.copytree(item, target_server_dir, dirs_exist_ok=True)
                tool_count = len(list(target_server_dir.glob("*.json")))
                print(f"   [OK] MCP サーバー `{item.name}` ({tool_count} ツール) を同期完了")
    else:
        print("   [WARN] .agents/mcp が見つかりませんでした。")

    print("\n--------------------------------------------------------------------------------")
    print("✨ 【セットアップ完了】以下の秘密道具が AntiGravity で利用可能になりました！")
    print("  ・Skills: 企画壁打ち、リッチUI、APIキー保護、デプロイ、長期記憶、RAG、GitHub公開 等")
    print("  ・MCPs  : Developer Knowledge MCP (Google公式情報直通)、Firebase MCP (DB・公開)")
    print("--------------------------------------------------------------------------------")
    print("\n【次のステップ】")
    print("⚠️ スキルと MCP は会話の開始時に読み込まれます。")
    print("AntiGravity で【新しい会話（New Conversation）】を開き、チャット欄に")
    print("  /ipp-skill-check")
    print("と入力して送信してください。表示されたコードブロックを HITMAN に提出します。")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
