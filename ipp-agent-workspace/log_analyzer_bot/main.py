"""
社内障害ログ自動解析Bot — FastAPI サーバ（Cloud Run 用）

/chat は必ず ADK エージェント（root_agent）を実行して応答する。LLM を通さずに固定文を返さない。
利用者ごとに1つの ADK セッションを使い回し、会話履歴を保持する。
"""

from __future__ import annotations

import os
import re
import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import root_agent

APP_NAME = "log_analyzer_bot"
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_TAG_RE = re.compile(r"<a2ui-json>([\s\S]*?)</a2ui-json>", re.IGNORECASE)

app = FastAPI(title="社内障害ログ自動解析Bot")
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
_sessions: dict[str, str] = {}


async def _session_id_for(user_id: str) -> str:
    """利用者ごとのセッションを取得（無ければ作成）する。app_name と user_id は必須引数。"""
    sid = _sessions.get(user_id)
    if sid:
        sess = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=sid)
        if sess is not None:
            return sid
    sess = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    _sessions[user_id] = sess.id
    return sess.id


def _to_parts(text: str) -> list[dict]:
    """応答テキストを、文章パートと A2UI カードのパートに分ける。"""
    parts: list[dict] = []
    prose = _TAG_RE.sub("", text).strip()
    if prose:
        parts.append({"kind": "text", "text": prose})
    for m in _TAG_RE.finditer(text):
        try:
            msgs = json.loads(m.group(1))
            for msg in msgs if isinstance(msgs, list) else [msgs]:
                parts.append({"kind": "a2ui", "data": msg})
        except json.JSONDecodeError:
            parts.append({"kind": "text", "text": m.group(1).strip()})
    return parts


@app.get("/health")
async def health():
    return {"status": "ok", "agent": root_agent.name}


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    message = str(body.get("message", "")).strip()
    user_id = str(body.get("user_id") or "web-user")
    if not _USER_ID_RE.match(user_id):
        user_id = "web-user"
    if not message:
        return JSONResponse({"parts": []})

    session_id = await _session_id_for(user_id)
    content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
    final_text = ""
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.content and event.author == root_agent.name:
            texts = [p.text for p in event.content.parts or [] if getattr(p, "text", None)]
            if texts:
                final_text = "\n".join(texts)
    return JSONResponse({"parts": _to_parts(final_text) or [{"kind": "text", "text": "(応答がありませんでした)"}]})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
