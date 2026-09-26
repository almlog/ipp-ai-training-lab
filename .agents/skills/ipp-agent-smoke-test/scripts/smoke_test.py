#!/usr/bin/env python
# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
"""IPP AI研修: 自作エージェントの動作確認（スモークテスト）

受講生のエージェント（root_agent）に「異なる2つの質問」を実際に送り、次を記録する:
  - 応答が返るか / 2つの応答が入力に応じて異なるか
  - 自作の関数ツールが実際に呼ばれたか
  - 同じツールが異なる引数で呼ばれたのに同じ結果を返していないか（固定値を返すだけのダミー実装の疑い）

出力の SMOKE_JSON 行は HITMAN がそのまま再判定する（PASS/FAIL の表示ではなく生データで判定する）。
SMOKE_DIGEST は SMOKE_JSON の改変検知用。

使い方（ワークスペースのルートで実行）:
  python .agents/skills/ipp-agent-smoke-test/scripts/smoke_test.py \
      --agent-dir ipp-agent-workspace/my_agent \
      --q1 "（エージェントの用途に沿った質問1）" --q2 "（質問1とは内容が異なる質問2）"
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

MARKER = "[skill:ipp-agent-smoke-test@v1]"
DIGEST_SALT = "ipp-smoke-v1"
_MAX_TEXT = 400


def digest_of(data: dict) -> str:
    """SMOKE_JSON の改変検知用ダイジェスト（HITMAN 側でも同じ計算で照合する）。"""
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((DIGEST_SALT + canonical).encode("utf-8")).hexdigest()[:16]


def _short_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:12]


def load_root_agent(agent_dir: str):
    """agent_dir から root_agent を読み込む（agent.py 直置き / app/agent.py / パッケージ の順に探す）。"""
    base = Path(agent_dir).resolve()
    candidates = [base / "agent.py", base / "app" / "agent.py", base / "__init__.py"]
    for path in candidates:
        if not path.is_file():
            continue
        # 同じフォルダの補助モジュール（a2ui_utils.py 等）を import できるようにする
        for p in {str(path.parent), str(path.parent.parent)}:
            if p not in sys.path:
                sys.path.insert(0, p)
        spec = importlib.util.spec_from_file_location(f"_ipp_smoke_{uuid.uuid4().hex[:6]}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        agent = getattr(module, "root_agent", None)
        if agent is not None:
            return agent, str(path)
    raise SystemExit(f"root_agent が見つかりません: {agent_dir} （agent.py に root_agent を定義してください）")


async def _ask(runner, question: str) -> dict:
    from google.genai import types

    user_id = "ipp-smoke"
    session = await runner.session_service.create_session(app_name=runner.app_name, user_id=user_id)
    calls: list[dict] = []
    responses: list[dict] = []
    texts: list[str] = []
    content = types.Content(role="user", parts=[types.Part.from_text(text=question)])
    async for event in runner.run_async(user_id=user_id, session_id=session.id, new_message=content):
        for part in (getattr(event.content, "parts", None) or []) if event.content else []:
            fc = getattr(part, "function_call", None)
            fr = getattr(part, "function_response", None)
            if fc:
                calls.append({"name": fc.name, "args": dict(fc.args or {})})
            elif fr:
                responses.append({"name": fr.name, "response": fr.response})
            elif getattr(part, "text", None) and event.author != "user":
                texts.append(part.text)
    reply = "\n".join(texts).strip()
    return {
        "question": question[:200],
        "reply_excerpt": reply[:_MAX_TEXT],
        "reply_hash": _short_hash(reply),
        "tool_calls": [
            {"name": c["name"], "args_hash": _short_hash(c["args"])} for c in calls
        ],
        "tool_results": [
            {"name": r["name"], "result_hash": _short_hash(r["response"])} for r in responses
        ],
    }


def evaluate(runs: list[dict]) -> dict:
    """生データから合否の観点を計算する（HITMAN も同じ観点で再判定する）。"""
    replies_ok = all(r["reply_excerpt"] for r in runs)
    replies_differ = len({r["reply_hash"] for r in runs}) == len(runs)
    tool_call_count = sum(len(r["tool_calls"]) for r in runs)
    stub_suspects = []
    if len(runs) == 2:
        a, b = runs
        for name in {c["name"] for c in a["tool_calls"]} & {c["name"] for c in b["tool_calls"]}:
            args_a = {c["args_hash"] for c in a["tool_calls"] if c["name"] == name}
            args_b = {c["args_hash"] for c in b["tool_calls"] if c["name"] == name}
            res_a = {r["result_hash"] for r in a["tool_results"] if r["name"] == name}
            res_b = {r["result_hash"] for r in b["tool_results"] if r["name"] == name}
            if args_a != args_b and res_a and res_a == res_b:
                stub_suspects.append(name)
    checks = {
        "replies_nonempty": replies_ok,
        "replies_differ": replies_differ,
        "tool_called": tool_call_count > 0,
        "no_stub_suspect": not stub_suspects,
    }
    return {"checks": checks, "tool_call_count": tool_call_count, "stub_suspects": sorted(stub_suspects),
            "passed": all(checks.values())}


async def run_smoke(root_agent, q1: str, q2: str) -> dict:
    from google.adk.runners import InMemoryRunner

    runs = []
    for q in (q1, q2):
        runner = InMemoryRunner(agent=root_agent, app_name="ipp_smoke")  # 質問ごとに独立したセッション
        runs.append(await _ask(runner, q))
    result = evaluate(runs)
    return {
        "version": 1,
        "agent": getattr(root_agent, "name", "unknown"),
        "tools": sorted(getattr(t, "__name__", getattr(t, "name", type(t).__name__)) for t in (getattr(root_agent, "tools", None) or [])),
        "runs": runs,
        **result,
    }


def format_report(data: dict, command: str) -> str:
    lines = [MARKER, f"$ {command}", f"agent: {data['agent']}  tools: {', '.join(data['tools']) or '(なし)'}"]
    for i, r in enumerate(data["runs"], start=1):
        called = ", ".join(c["name"] for c in r["tool_calls"]) or "(ツール呼び出しなし)"
        lines.append(f"--- Q{i}: {r['question']}")
        lines.append(f"tools called: {called}")
        lines.append("reply: " + r["reply_excerpt"].replace("\n", " ")[:200])
    for k, v in data["checks"].items():
        lines.append(f"check {k}: {'OK' if v else 'NG'}")
    if data["stub_suspects"]:
        lines.append("stub suspects (異なる入力で同じ結果を返したツール): " + ", ".join(data["stub_suspects"]))
    lines.append("SMOKE_RESULT: " + ("PASS" if data["passed"] else "FAIL"))
    lines.append("SMOKE_JSON: " + json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    lines.append("SMOKE_DIGEST: " + digest_of(data))
    return "\n".join(lines)


def _load_dotenv_files(agent_dir: str) -> None:
    """.env を読み込む（既に設定済みの環境変数は上書きしない）。python-dotenv が無ければ簡易パーサで読む。"""
    for path in (Path(agent_dir) / ".env", Path.cwd() / ".env", Path.cwd() / "hitman" / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def _configure_gemini_auth() -> str:
    """API キーの種類に応じて Gemini の接続方式を決める。キーの値は表示しない。

    - AQ. で始まるキー（Vertex AI Express モード）: GOOGLE_GENAI_USE_VERTEXAI=true とし、
      API キーと同時に指定できない GOOGLE_CLOUD_PROJECT / LOCATION をこのプロセス内でだけ外す
    - それ以外のキー（Google AI Studio）: Gemini Developer API として使う
    """
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    if key and not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = key
    # google-genai の新しい版は GOOGLE_GENAI_USE_ENTERPRISE、古い版は GOOGLE_GENAI_USE_VERTEXAI を見る。
    # 両方を同じ値にしておけば、どちらの版でも同じ動作になる（値が食い違うと警告が出る）。
    if key.startswith("AQ."):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "true"
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        os.environ.pop("GOOGLE_CLOUD_LOCATION", None)
        return "Vertex AI Express（APIキー）"
    if key:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "false"
        return "Gemini Developer API（APIキー）"
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return "Vertex AI（gcloud 認証）"
    return ""


def main(argv: list[str] | None = None) -> int:
    # Windows のコンソール（CP932）でも、Gemini の応答に含まれる絵文字等で落ちないようにする
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="IPP AI研修: 自作エージェントのスモークテスト")
    ap.add_argument("--agent-dir", required=True, help="root_agent を定義した agent.py があるフォルダ")
    ap.add_argument("--q1", required=True, help="エージェントの用途に沿った質問1")
    ap.add_argument("--q2", required=True, help="質問1とは内容が異なる質問2")
    args = ap.parse_args(argv)
    if args.q1.strip() == args.q2.strip():
        print("q1 と q2 は異なる内容にしてください（入力に応じて結果が変わることを確認するため）", file=sys.stderr)
        return 2
    _load_dotenv_files(args.agent_dir)
    auth = _configure_gemini_auth()
    if not auth:
        print("Gemini の認証情報が見つかりません。.env に GEMINI_API_KEY を設定してください"
              "（キーをコマンドやチャットに直接書かないこと）。", file=sys.stderr)
        return 2
    print(f"[smoke] 接続方式: {auth}", file=sys.stderr)
    root_agent, _ = load_root_agent(args.agent_dir)
    data = asyncio.run(run_smoke(root_agent, args.q1, args.q2))
    cmd = f"python .agents/skills/ipp-agent-smoke-test/scripts/smoke_test.py --agent-dir {args.agent_dir} --q1 \"{args.q1[:40]}\" --q2 \"{args.q2[:40]}\""
    print("```text")
    print(format_report(data, cmd))
    print("```")
    return 0 if data["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
