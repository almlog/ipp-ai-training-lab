#!/usr/bin/env python
"""IPP AI実践研修: ローカル永続化（SQLite / JSON）による長期記憶ツール

特徴:
- Google Cloud の Agent Platform / Reasoning Engine は一切不要。
- 受講生の GEMINI_API_KEY だけで、ローカル環境・コンテナ内で会話や好みを永続記憶できる。
- ADK エージェントの関数ツールとしてそのまま登録可能。

使い方（CLIテスト）:
  python local_memory_tool.py --remember "user_name" "山田太郎"
  python local_memory_tool.py --remember "preference" "回答は常に箇条書きで簡潔に"
  python local_memory_tool.py --recall
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("user_memory.db")


def _init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return conn


def remember_user_fact(key: str, value: str, db_path: Path = DB_PATH) -> str:
    """ユーザーに関する重要な情報、設定、好み（キーと値）を長期記憶データベースに保存します。

    Args:
        key: 記憶の分類または項目名（例: 'user_role', 'preferred_format', 'favorite_topics'）
        value: 記憶する具体的な内容（例: '経理部マネージャー', '表形式で出力', '税制改正'）
    """
    conn = _init_db(db_path)
    with conn:
        conn.execute("""
            INSERT INTO memories (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key.strip(), value.strip()))
    return f"【記憶完了】項目 `{key}` を `{value}` として保存しました。"


def recall_user_facts(query: str = "", db_path: Path = DB_PATH) -> str:
    """これまでに保存されたユーザーの長期記憶（設定・好み・属性）を検索・取得します。

    Args:
        query: 検索キーワード（省略時はすべての記憶を一覧表示）
    """
    conn = _init_db(db_path)
    cursor = conn.cursor()
    if query:
        cursor.execute("SELECT key, value, updated_at FROM memories WHERE key LIKE ? OR value LIKE ?", (f"%{query}%", f"%{query}%"))
    else:
        cursor.execute("SELECT key, value, updated_at FROM memories ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    if not rows:
        return "保存された長期記憶はありません。"

    lines = ["【保存されている長期記憶一覧】"]
    for k, v, t in rows:
        lines.append(f"- **{k}**: {v} (更新: {t})")
    return "\n".join(lines)


def clear_user_facts(db_path: Path = DB_PATH) -> str:
    """保存された長期記憶をすべて初期化（消去）します。"""
    conn = _init_db(db_path)
    with conn:
        conn.execute("DELETE FROM memories")
    return "長期記憶をすべてクリアしました。"


def main() -> int:
    parser = argparse.ArgumentParser(description="ローカル長期記憶ツール (SQLite)")
    parser.add_argument("--remember", nargs=2, metavar=("KEY", "VALUE"), help="記憶を保存")
    parser.add_argument("--recall", action="store_true", help="記憶をすべて表示")
    parser.add_argument("--query", default="", help="特定の記憶を検索")
    parser.add_argument("--clear", action="store_true", help="記憶を全消去")
    args = parser.parse_args()

    if args.remember:
        k, v = args.remember
        print(remember_user_fact(k, v))
    elif args.clear:
        print(clear_user_facts())
    elif args.recall or args.query:
        print(recall_user_facts(args.query))
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
