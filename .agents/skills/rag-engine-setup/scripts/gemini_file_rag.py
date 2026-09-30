#!/usr/bin/env python
"""IPP AI実践研修: Gemini File API を活用した即席 RAG 検索スクリプト

特徴:
- Google Cloud の GCS バケットや Vector Search は一切不要。
- 受講生の GEMINI_API_KEY だけで PDF / テキスト / CSV をアップロードして検索・質問応答（グラウンディング）が可能。
- ADK エージェントの関数ツールとしてそのまま組み込み可能。

使い方:
  python gemini_file_rag.py --file docs/sample_rules.txt --query "交通費の申請期限はいつまでですか？"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def setup_gemini_client():
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("環境変数 GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。")
    return genai.Client(api_key=api_key)


def search_file_with_gemini(file_path: str, query: str) -> str:
    """PDF / テキストファイルをアップロードし、Gemini に質問して根拠付き回答を得る。"""
    client = setup_gemini_client()
    p = Path(file_path)
    if not p.is_file():
        return f"エラー: 指定されたファイルが存在しません: {file_path}"

    print(f"📄 ファイル `{p.name}` を Gemini File API へアップロード中...")
    uploaded_file = client.files.upload(file=str(p))
    print(f"✅ アップロード完了 (URI: {uploaded_file.uri})。質問を送信中: '{query}'")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            uploaded_file,
            (
                "あなたは正確なドキュメント検索・QAアシスタントです。"
                "アップロードされた資料の内容のみに基づいて、以下の質問に簡潔かつ正確に回答してください。"
                "資料に記載のない事項は「資料には記載がありません」と明記してください。\n\n"
                f"質問: {query}"
            ),
        ],
    )
    return response.text or "回答を生成できませんでした。"


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemini File API による即時 RAG 検索")
    parser.add_argument("--file", required=True, help="検索対象のドキュメント (PDF, TXT, CSV 等)")
    parser.add_argument("--query", required=True, help="質問文")
    args = parser.parse_args()

    answer = search_file_with_gemini(args.file, args.query)
    print("\n【回答結果】")
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
