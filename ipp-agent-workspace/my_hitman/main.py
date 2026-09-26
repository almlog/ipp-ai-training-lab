"""
FastAPI Server for HITMAN Lite
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import verify_step_output, get_sop_step_info, DEFAULT_SOP, root_agent

APP_NAME = "hitman_lite"
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
_sessions: dict = {}

app = FastAPI(title="HITMAN Lite Operator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "app": "HITMAN Lite Operator", "steps_count": len(DEFAULT_SOP)}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/verify")
async def verify(req: Request):
    body = await req.json()
    step_id = body.get("step_id", "1-1")
    terminal_output = body.get("terminal_output", "")
    res = verify_step_output(step_id, terminal_output)
    return JSONResponse(content=res)

@app.post("/chat")
async def chat(req: Request):
    """ADK エージェント（root_agent）で応答する。利用者ごとに1つのセッションを使い回して会話履歴を保持する。"""
    body = await req.json()
    message = str(body.get("message", "")).strip()
    user_id = str(body.get("user_id") or "web-user")[:80]
    if not message:
        return JSONResponse(content={"parts": []})
    sid = _sessions.get(user_id)
    sess = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=sid) if sid else None
    if sess is None:
        sess = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
        _sessions[user_id] = sess.id
    content = types.Content(role="user", parts=[types.Part.from_text(text=message)])
    final_text = ""
    async for event in runner.run_async(user_id=user_id, session_id=sess.id, new_message=content):
        if event.content and event.author == root_agent.name:
            texts = [p.text for p in event.content.parts or [] if getattr(p, "text", None)]
            if texts:
                final_text = "\n".join(texts)
    return JSONResponse(content={"parts": [{"kind": "text", "text": final_text or "(応答がありませんでした)"}]})


@app.get("/sop")
def get_sop():
    return JSONResponse(content=DEFAULT_SOP)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
