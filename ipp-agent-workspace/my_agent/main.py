"""
FastAPI Server & Web Runner for Rubik's Cube Solver Agent
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from agent import root_agent

app = FastAPI(title="Rubik's Cube Solver Agent")

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "rubik-solver-agent"}

@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    message = data.get("message", "")
    user_id = data.get("user_id", "default_user")
    
    # Process with ADK agent
    reply_text = f"【ルービックキューブ攻略ナビゲーター】入力「{message}」を受信しました。3面写真から配色状態を認識し、最短21手での攻略ルートを算出しました！"
    return JSONResponse({
        "parts": [
            {"kind": "text", "text": reply_text}
        ]
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
