# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""研修コースAの要件定義書（project_brief.md）の書式を解析・検査する。

コースAでは、受講生が Antigravity と相談して作った project_brief.md が「唯一の設計図」になる。
HITMAN は T-2 でこの書式を検査し、合格した内容（エージェント名・機能・画面・ツール・確認用の質問）から
T-3〜T-6 の手順とプロンプトを組み立てる。キーワード表や固定テンプレートで企画を置き換えない。

標準ライブラリだけで動くこと（受講生側の検査スクリプトと同じファイルを使うため）。
このファイルは `.agents/skills/pick-your-agent-project/scripts/project_brief.py` と同一内容に保つ
（tests/unit/test_project_brief.py で検査する）。
"""

from __future__ import annotations

import re

AGENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
_SEP_RE = re.compile(r"\s*(?:／|\||｜)\s*")
_ITEM_RE = re.compile(r"^\s*[-*・]\s+(.*\S)\s*$")
_FEATURE_ID_RE = re.compile(r"(?<![A-Za-z0-9])F(\d{1,2})(?!\d)")
# 動作確認の質問はコマンドの "..." に埋め込むため、シェルが解釈する文字を禁止する（PowerShell / bash 共通）
QUESTION_FORBIDDEN = ('"', "`", "$", "\\")
_TOOL_RE = re.compile(r"^`?([a-z_][a-z0-9_]{2,60})\s*\(([^)]*)\)")

# 見出しのキーワード → セクションID（見出しの番号や前後の語は問わない）
# 先に書いたものから順に照合する（『今回は作らない機能』が『機能』と誤認されないよう、具体的な語を先に置く）
SECTION_KEYS: list[tuple[str, tuple[str, ...]]] = [
    ("basic", ("基本情報",)),
    ("out_of_scope", ("作らない", "スコープ外")),
    ("checks", ("動作確認",)),
    ("credentials", ("認証情報", "認証")),
    ("tools", ("関数ツール", "ツール")),
    ("screens", ("画面",)),
    ("data", ("データ",)),
    ("features", ("機能一覧", "機能")),
]

SECTION_TITLES = {
    "basic": "## 1. 基本情報",
    "features": "## 2. 機能一覧",
    "screens": "## 3. 画面",
    "tools": "## 4. 関数ツール",
    "data": "## 5. データと保存先",
    "credentials": "## 6. 認証情報",
    "out_of_scope": "## 7. 今回は作らないもの",
    "checks": "## 8. 動作確認",
}

MAX_FEATURES = 12


def _section_id(heading: str) -> str | None:
    for sid, words in SECTION_KEYS:
        if any(w in heading for w in words):
            return sid
    return None


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            current = _section_id(line[3:])
            if current:
                sections.setdefault(current, [])
            continue
        if line.startswith("# "):
            current = None
            continue
        if current:
            m = _ITEM_RE.match(line)
            if m:
                sections[current].append(m.group(1))
    return sections


def _kv(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items:
        m = re.match(r"^\**([^:：*]+?)\**\s*[:：]\s*(.+)$", it)
        if m:
            out[m.group(1).strip()] = m.group(2).strip().strip("`")
    return out


def parse_brief(text: str) -> dict:
    """要件定義書を解析する。

    Returns:
        ok（書式どおりか）、errors（直すべき点の一覧）、および解析結果
        （agent_name, display_name, users, problem, features, screens, tools, data, out_of_scope, q1, q2）。
    """
    sections = _split_sections(text)
    errors: list[str] = []

    for sid, title in SECTION_TITLES.items():
        if sid not in sections:
            errors.append(f"見出し『{title}』がありません。")

    basic = _kv(sections.get("basic", []))
    agent_name = basic.get("エージェント名", "").strip().lower()
    display_name = basic.get("表示名", "").strip()
    users = basic.get("利用者", "").strip()
    problem = basic.get("解決する課題", "").strip()
    if not AGENT_NAME_RE.match(agent_name):
        errors.append("『エージェント名』は英小文字で始まる英小文字・数字・アンダースコアの名前にしてください（例: calendar_journal_agent）。")
    if not display_name:
        errors.append("『表示名』がありません。")
    if not problem:
        errors.append("『解決する課題』がありません。")

    features: list[dict] = []
    for it in sections.get("features", []):
        m = re.match(r"^\**F(\d{1,2})\**\s*[:：]\s*(.+)$", it)
        if not m:
            continue
        parts = _SEP_RE.split(m.group(2), maxsplit=1)
        accept = ""
        if len(parts) > 1:
            accept = re.sub(r"^受け入れ条件\s*[:：]\s*", "", parts[1]).strip()
        features.append({"id": f"F{int(m.group(1))}", "name": parts[0].strip(), "acceptance": accept})
    if len(features) < 2:
        errors.append("『機能一覧』に F1, F2 … の形で機能を2つ以上書いてください。")
    if len(features) > MAX_FEATURES:
        errors.append(f"機能が多すぎます（{len(features)}個）。研修時間で作れる {MAX_FEATURES} 個以内に絞り、残りは『今回は作らないもの』へ移してください。")
    for f in features:
        if not f["acceptance"]:
            errors.append(f"{f['id']} に『受け入れ条件』（どうなれば完成か）がありません。")
    ids = [f["id"] for f in features]
    if len(ids) != len(set(ids)):
        errors.append("機能の番号（F1, F2 …）が重複しています。")

    screens: list[dict] = []
    for it in sections.get("screens", []):
        m = re.match(r"^\**S(\d{1,2})\**\s*[:：]\s*(.+)$", it)
        if m:
            parts = _SEP_RE.split(m.group(2))
            screens.append({
                "id": f"S{int(m.group(1))}",
                "name": parts[0].strip(),
                "detail": " ／ ".join(p.strip() for p in parts[1:]),
                "features": sorted(set(f"F{int(n)}" for n in _FEATURE_ID_RE.findall(m.group(2)))),
            })
    if not screens:
        errors.append("『画面』に S1: 画面名 ／ 要素 ／ 使う機能 の形で画面を1つ以上書いてください。")

    tools: list[dict] = []
    for it in sections.get("tools", []):
        m = _TOOL_RE.match(it)
        if m:
            tools.append({
                "name": m.group(1),
                "signature": it.split("／")[0].split("|")[0].strip().strip("`"),
                "detail": it,
                "features": sorted(set(f"F{int(n)}" for n in _FEATURE_ID_RE.findall(it))),
            })
    if not tools:
        errors.append("『関数ツール』に 関数名(引数: 型, …) -> 返り値 ／ 役割 ／ 使う機能 の形でツールを1つ以上書いてください。")

    used = {fid for s in screens for fid in s["features"]} | {fid for t in tools for fid in t["features"]}
    unused = [f["id"] for f in features if f["id"] not in used]
    if features and unused:
        errors.append(f"{', '.join(unused)} がどの画面・ツールからも使われていません（『使う機能』に書くか、機能を見直してください）。")

    data = sections.get("data", [])
    if "data" in sections and not data:
        errors.append("『データと保存先』に、扱うデータと保存先を1つ以上書いてください。")

    cred_text = " ".join(sections.get("credentials", []))
    if "credentials" in sections and ".env" not in cred_text:
        errors.append("『認証情報』に、Gemini API キーを .env から読み込むことを書いてください（キーの値は書かない）。")

    out_of_scope = sections.get("out_of_scope", [])
    if "out_of_scope" in sections and not out_of_scope:
        errors.append("『今回は作らないもの』を1つ以上書いてください（ない場合は『なし』と書く）。")

    checks = _kv(sections.get("checks", []))
    q1 = checks.get("Q1", "").strip()
    q2 = checks.get("Q2", "").strip()
    if not q1 or not q2:
        errors.append("『動作確認』に Q1: と Q2: の2つの質問を書いてください。")
    elif q1 == q2:
        errors.append("動作確認の Q1 と Q2 は、内容がはっきり異なる質問にしてください。")
    for q in (q1, q2):
        if any(c in q for c in QUESTION_FORBIDDEN):
            errors.append("動作確認の質問には \" ` $ \\ を使わないでください（コマンドに埋め込むため）。")
            break

    return {
        "ok": not errors,
        "errors": errors,
        "agent_name": agent_name,
        "display_name": display_name,
        "users": users,
        "problem": problem,
        "features": features,
        "screens": screens,
        "tools": tools,
        "data": data,
        "out_of_scope": out_of_scope,
        "q1": q1,
        "q2": q2,
    }


def service_name_for(agent_name: str) -> str:
    """Cloud Run のサービス名（英小文字・数字・ハイフン）。"""
    return (agent_name or "my-agent").replace("_", "-")[:49].strip("-")


BRIEF_TEMPLATE = """# <表示名>: Project Brief

## 1. 基本情報
- エージェント名: <英小文字スネークケース 例: calendar_journal_agent>
- 表示名: <画面に出す名前>
- 利用者: <だれが使うか>
- 解決する課題: <どんな困りごとを解決するか>

## 2. 機能一覧
- F1: <機能> ／ 受け入れ条件: <どうなれば完成か>
- F2: <機能> ／ 受け入れ条件: <どうなれば完成か>

## 3. 画面
- S1: <画面名> ／ 要素: <入力欄・ボタン・一覧・カレンダー等> ／ 使う機能: F1, F2

## 4. 関数ツール
- <関数名>(<引数>: <型>, ...) -> <返り値> ／ 役割: <何をするか> ／ 使う機能: F1

## 5. データと保存先
- <データ> ／ 保存先: <メモリ / ローカルファイル / Firestore 等>

## 6. 認証情報
- GEMINI_API_KEY: ローカルは .env から読み込む。本番（Cloud Run）は Secret Manager から渡す。キーの値はどこにも書かない。

## 7. 今回は作らないもの
- <研修時間内では作らない機能（なければ『なし』）>

## 8. 動作確認
- Q1: <エージェントへの質問1>
- Q2: <内容がはっきり異なる質問2>
"""
