#!/usr/bin/env python
"""IPP AI実践研修: 社内資料検索（RAG）実行スクリプト

特徴:
- Google Cloud の GCS バケットや Vector Search は一切不要。
- 受講生の GEMINI_API_KEY だけで、テキスト・マークダウン・規程ファイルを検索し、根拠付き回答（QA）を生成。
- 企業アカウント等で File API が制限されている場合でも、ローカルファイル直接読込フォールバックにより 100% 確実に動作。

使い方:
  python .agents/skills/rag-engine-setup/scripts/gemini_file_rag.py --file docs/sample_rules.txt --query "旅費の申請期限はいつまでですか？"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# .env の安全な自動読み込み
for p in (Path.cwd() / ".env", Path.cwd() / "hitman" / ".env", Path.cwd().parent / ".env"):
    if p.is_file():
        try:
            from dotenv import load_dotenv
            load_dotenv(p)
            break
        except ImportError:
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _configure_auth():
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    if not key:
        raise ValueError("環境変数 GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
    if not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = key
    if key.startswith("AQ."):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "true"
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        os.environ.pop("GOOGLE_CLOUD_LOCATION", None)
    else:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "false"
    return key


def search_file_with_gemini(file_path: str, query: str) -> str:
    """ファイルを読み込み、Gemini に質問して根拠付き回答を得る。"""
    _configure_auth()
    from google import genai
    client = genai.Client()

    p = Path(file_path)
    if not p.is_file():
        return f"エラー: 指定されたファイルが存在しません: {file_path}"

    print(f"📄 資料 `{p.name}` を解析中...")
    file_text = p.read_text(encoding="utf-8", errors="replace")

    print(f"🔍 Gemini に質問を送信中: '{query}'")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            (
                "あなたは社内規程・ドキュメントの正確なQAアシスタントです。"
                "以下の【参考資料】に書かれている内容のみに基づいて、質問に正確かつ簡潔に回答してください。"
                "資料に書かれていない内容は『資料には記載がありません』と明記してください。\n\n"
                f"【参考資料（{p.name}）】\n{file_text}\n\n"
                f"【質問】\n{query}"
            ),
        ],
    )
    return response.text or "回答を生成できませんでした。"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="軽量 RAG ドキュメント検索")
    parser.add_argument("--file", required=True, help="検索対象のドキュメント (TXT, MD, CSV 等)")
    parser.add_argument("--query", required=True, help="質問文")
    args = parser.parse_args()

    answer = search_file_with_gemini(args.file, args.query)
    print("\n【回答結果】")
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
