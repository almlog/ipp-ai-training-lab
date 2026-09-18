"""
FastAPI Server for HITMAN Lite
"""

import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from agent import verify_step_output, get_sop_step_info, DEFAULT_SOP

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

@app.get("/sop")
def get_sop():
    return JSONResponse(content=DEFAULT_SOP)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
