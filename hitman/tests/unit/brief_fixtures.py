# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""研修コースAのテスト用: 受講生と Antigravity が作った想定の要件定義書と、T-2 / T-5 の提出ログを作る。"""

import json

import app.agent as agent_module
from app.project_brief import parse_brief

# スモークテストのテスト（analyze_log ツール）と整合する企画書
LOG_BRIEF = """# 社内障害ログ解析アシスタント: Project Brief

## 1. 基本情報
- エージェント名: log_analyzer_bot
- 表示名: 社内障害ログ解析アシスタント
- 利用者: 運用チーム
- 解決する課題: 障害ログの一次切り分けに時間がかかる

## 2. 機能一覧
- F1: ログの原因解析 ／ 受け入れ条件: ログを貼ると原因と一次対応が表示される
- F2: 解析履歴の一覧 ／ 受け入れ条件: 過去の解析結果が新しい順に一覧表示される

## 3. 画面
- S1: 解析画面 ／ 要素: ログ入力欄、解析ボタン、結果カード ／ 使う機能: F1
- S2: 履歴画面 ／ 要素: 解析履歴の一覧表 ／ 使う機能: F2

## 4. 関数ツール
- analyze_log(log_text: str) -> dict ／ 役割: ログから原因と対応を判定する ／ 使う機能: F1, F2

## 5. データと保存先
- 解析履歴 ／ 保存先: メモリ

## 6. 認証情報
- GEMINI_API_KEY: ローカルは .env から読み込む。本番は Secret Manager。値は書かない。

## 7. 今回は作らないもの
- なし

## 8. 動作確認
- Q1: No space left on device のエラーが出ました
- Q2: DB connection timeout が発生しました
"""

from pathlib import Path

# 2026-09-30 の実機テストで作ろうとした『カレンダー＋ガント＋日記』の企画（WBS Bot にすり替えられてはならない）
CALENDAR_BRIEF = (Path(__file__).parent / "fixtures" / "calendar_brief.md").read_text(encoding="utf-8")


def t2_log(brief_text: str = LOG_BRIEF) -> str:
    """brief_check.py が PASS したときの出力と同じ形の T-2 提出ログ。"""
    b = parse_brief(brief_text)
    assert b["ok"], b["errors"]
    return (
        "[skill:pick-your-agent-project@v1]\n"
        "$ python .agents/skills/pick-your-agent-project/scripts/brief_check.py ipp-agent-workspace/project_brief.md\n"
        f"BRIEF_CHECK: PASS  agent: {b['agent_name']}  features: {len(b['features'])}  screens: {len(b['screens'])}  tools: {len(b['tools'])}\n"
        + brief_text
    )


def set_brief(state: "agent_module.HitmanState", brief_text: str = LOG_BRIEF) -> dict:
    b = parse_brief(brief_text)
    assert b["ok"], b["errors"]
    state.brief = agent_module._brief_public(b)
    state.agent_slug = b["agent_name"]
    state.plan_confirmed = True
    return b


def deploy_log(nonce: str, service: str, *, chat_status: int = 200, url: str | None = None) -> str:
    """ipp-cloud-run-deploy の deploy.py と同じ形の出力（digest 付き）。"""
    url = url if url is not None else f"https://{service}-123456789.asia-northeast1.run.app"
    ok = chat_status == 200
    data = {
        "service": service, "region": "asia-northeast1", "nonce": nonce, "url": url,
        "secret_ref": f"{service}-gemini-api-key", "deployed": True,
        "checks": {"health_http": True, "chat_http": ok, "chat_reply": ok},
        "status_health": 200, "status_chat": chat_status,
        "reply_excerpt": "原因はディスク容量不足です。" if ok else "",
        "passed": ok,
    }
    return "\n".join([
        agent_module.DEPLOY_MARKER,
        f"Service URL: {url}",
        "DEPLOY_RESULT: " + ("PASS" if ok else "FAIL"),
        "DEPLOY_JSON: " + json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
        "DEPLOY_DIGEST: " + agent_module._deploy_digest(data),
    ])
