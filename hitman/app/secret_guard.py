# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""認証情報（API キー・トークン・秘密鍵）の平文混入を検知する。

研修では受講生が Gemini API キーを持って参加する。キーは各自の `.env` にだけ置き、
チャット・提出ログ・コマンドライン・デプロイ設定・Git に平文で出してはならない。
HITMAN は次の場所でこのモジュールを使い、検知したら処理を止める（値そのものは一切記録・表示しない）。

- /chat: 受講生のメッセージを Gemini に送る前（送らずに警告だけ返す）
- verify_step_output: 提出ログに含まれていたら不合格（合格させない）

同じ判定を受講生側でも使えるよう、`.agents/skills/ipp-secure-credentials/scripts/secret_scan.py`
にも同じパターンを置いている（両者の一致は tests/unit/test_secret_guard.py で検査する）。
"""

from __future__ import annotations

import re

# (種類, パターン)。種類名は受講生への案内に使う。値は絶対に返さない。
# 日本語の直後に続くキーも検知できるよう、単語境界は \b ではなく「英数字・_ でない」で判定する
_B = r"(?<![A-Za-z0-9_])"

# (種類, パターン)。種類名は受講生への案内に使う。値は絶対に返さない。
SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Gemini / Google API キー", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Vertex AI Express キー", re.compile(r"AQ\.[0-9A-Za-z_\-]{30,}")),
    ("Google OAuth アクセストークン", re.compile(r"ya29\.[0-9A-Za-z_\-]{20,}")),
    ("GitHub トークン", re.compile(_B + r"(?:gh[pousr]_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{30,})")),
    ("秘密鍵（PEM）", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----")),
    ("サービスアカウント鍵（JSON）", re.compile(r"\"private_key\"\s*:\s*\"-----BEGIN")),
    # KEY=値 の形でキーを直書きしたもの（.env の中身の貼り付け、--set-env-vars への埋め込みなど）。
    # 変数名は大文字の定数名だけ（コードの api_key=settings.x を誤検知しない）。値は同じ行で、
    # 英大文字・英小文字・数字をすべて含む 20 文字以上のランダムな文字列だけを対象にする
    # （Secret Manager の参照 name:latest、<プレースホルダ>、$VAR、説明文は値ではない）。
    (
        "API キーの直書き（KEY=値）",
        re.compile(
            _B + r"(?:GEMINI_API_KEY|GOOGLE_API_KEY|API_KEY|SECRET_KEY|ACCESS_TOKEN)[ \t]*[=:][ \t]*[\"']?"
            r"(?=[0-9A-Za-z_\-]*[0-9])(?=[0-9A-Za-z_\-]*[A-Z])(?=[0-9A-Za-z_\-]*[a-z])"
            r"[0-9A-Za-z_\-]{20,}(?![0-9A-Za-z_\-]*:(?:latest|\d+))"
        ),
    ),
]


def find_secrets(text: str) -> list[str]:
    """テキストに含まれる認証情報の『種類』の一覧を返す（重複なし・出現順）。値は返さない。"""
    if not text:
        return []
    kinds: list[str] = []
    for kind, pat in SECRET_PATTERNS:
        if pat.search(text) and kind not in kinds:
            kinds.append(kind)
    return kinds


def redact(text: str) -> str:
    """認証情報を [REDACTED] に置き換えた文字列を返す（ログに残す必要がある場合用）。"""
    if not text:
        return text
    out = text
    for _kind, pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def leak_guidance(kinds: list[str]) -> str:
    """検知時に受講生へ見せる案内文（値は含めない）。"""
    names = "、".join(kinds)
    return (
        f"🔒 入力に認証情報（{names}）が含まれていたため、処理を止めました。この内容は AI に送信・保存していません。\n"
        "・キーは『漏えいしたもの』として扱い、すぐに無効化して再発行してください（Gemini API キーは Google AI Studio の API キー画面から削除・再作成できます）。\n"
        "・新しいキーは、エディタで各自の `.env` ファイルに直接書き込んでください。チャット・コマンドライン・提出ログには書かないでください。\n"
        "・提出ログにキーが含まれる場合は、`.env` の中身を表示するコマンド（cat .env 等）や、キーをコマンドに埋め込む操作をしていないか確認してください。"
    )
