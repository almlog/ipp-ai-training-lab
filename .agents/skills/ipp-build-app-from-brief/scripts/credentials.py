"""Gemini の認証情報を安全に読み込む（IPP AI研修 共通）。

このファイルは `.agents/skills/ipp-build-app-from-brief/scripts/credentials.py` からアプリのフォルダへコピーして使う。
agent.py / main.py の先頭で `import credentials; credentials.configure()` を呼ぶ。

- 環境変数 GEMINI_API_KEY / GOOGLE_API_KEY（Cloud Run では Secret Manager から注入）を優先する
- 無ければ、このファイルと同じフォルダの .env を読む
- AQ. で始まるキー（Vertex AI Express）なら Vertex AI 接続に切り替える
- キーの値は表示・ログ出力しない。見つからないときは、値を含まないエラーで止める
"""

from __future__ import annotations

import os
from pathlib import Path

_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def configure() -> str:
    """認証情報を環境変数に設定し、接続方式（表示用の説明）を返す。キーの値は返さない。"""
    if not any(os.environ.get(k) for k in _KEY_NAMES):
        _load_dotenv(Path(__file__).resolve().parent / ".env")
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    if not key:
        raise RuntimeError(
            "Gemini API キーが見つかりません。アプリのフォルダの .env に GEMINI_API_KEY を設定してください"
            "（Cloud Run では Secret Manager から渡します）。キーをコードやコマンドに直接書かないこと。"
        )
    os.environ["GOOGLE_API_KEY"] = key
    vertex = "true" if key.startswith("AQ.") else "false"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = vertex
    os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = vertex
    if vertex == "true":
        # Vertex AI Express のキーは、プロジェクト・リージョン指定と同時に使えない
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        os.environ.pop("GOOGLE_CLOUD_LOCATION", None)
        return "Vertex AI Express（APIキー）"
    return "Gemini Developer API（APIキー）"
