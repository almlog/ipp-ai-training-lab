# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
# Developed by Shunpei Suzuki <suzuki.shunpei@ipp.local>
#
"""FastAPI proxy for the HITMAN Agent Frontend.

Supports:
1. Local development mode (connecting to ADK Playground on http://127.0.0.1:8080)
2. Cloud production mode (connecting over A2A protocol when AGENT_ENGINE_RESOURCE_NAME is set)
"""

import json
import os
import re
import time
import uuid
from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

load_dotenv()

# Cloud deployment resource configuration
RESOURCE = os.environ.get("AGENT_ENGINE_RESOURCE_NAME")
LOCAL_AGENT_URL = os.environ.get("LOCAL_AGENT_URL", "http://127.0.0.1:8080")
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")

app = FastAPI(title="HITMAN Ops Assistant Frontend")

# Local session store: user_id -> session_id
_local_sessions: dict[str, str] = {}
# Cloud A2A context store: user_id -> context_id
_cloud_contexts: dict[str, str] = {}

_A2UI_MIME = "application/json+a2ui"
_TAG_RE = re.compile(r"<a2ui-json>([\s\S]*?)</a2ui-json>", re.IGNORECASE)


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


def _parse_local_event_text(text: str) -> list[dict]:
    """Parse text from local agent, extracting prose and <a2ui-json> blocks."""
    parts: list[dict] = []
    a2ui_match = _TAG_RE.search(text)
    if a2ui_match:
        a2ui_str = a2ui_match.group(1).strip()
        prose = _TAG_RE.sub("", text).strip()
        if prose:
            parts.append({"kind": "text", "text": prose})
        try:
            a2ui_messages = json.loads(a2ui_str)
            if isinstance(a2ui_messages, list):
                for msg in a2ui_messages:
                    parts.append({"kind": "a2ui", "data": msg})
            elif isinstance(a2ui_messages, dict):
                parts.append({"kind": "a2ui", "data": a2ui_messages})
        except Exception:
            parts.append({"kind": "text", "text": a2ui_str})
    else:
        if text.strip():
            parts.append({"kind": "text", "text": text.strip()})
    return parts


async def _chat_local(user_id: str, message: str) -> list[dict]:
    """Communicate with local ADK Web server on port 8080."""
    parts: list[dict] = []
    async with httpx.AsyncClient(timeout=120) as client:
        session_id = _local_sessions.get(user_id)
        if not session_id:
            res_sess = await client.post(
                f"{LOCAL_AGENT_URL}/apps/{AGENT_DIRECTORY}/users/{user_id}/sessions"
            )
            if res_sess.status_code == 200:
                session_id = res_sess.json().get("id")
                _local_sessions[user_id] = session_id
            else:
                session_id = str(uuid.uuid4())
                _local_sessions[user_id] = session_id

        payload = {
            "app_name": AGENT_DIRECTORY,
            "user_id": user_id,
            "session_id": session_id,
            "new_message": {
                "role": "user",
                "parts": [{"text": message}],
            },
            "streaming": False,
        }
        res_run = await client.post(f"{LOCAL_AGENT_URL}/run", json=payload)
        res_run.raise_for_status()
        events = res_run.json()

        for event in events:
            if event.get("author") in ("hitman", "model", "bot", "assistant"):
                content = event.get("content") or {}
                content_parts = content.get("parts") or []
                for p in content_parts:
                    txt = p.get("text")
                    if txt:
                        parts.extend(_parse_local_event_text(txt))

    return parts


async def _chat_cloud(user_id: str, message: str) -> list[dict]:
    """Communicate with deployed Agent Runtime via A2A protocol."""
    import google.auth
    import google.auth.transport.requests
    from a2a.client import ClientConfig, ClientFactory
    from a2a.types import (
        AgentCard,
        FilePart,
        Message,
        Part,
        Role,
        TaskArtifactUpdateEvent,
        TextPart,
        TransportProtocol,
    )

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }

    location = RESOURCE.split("/locations/")[1].split("/")[0]
    a2a_base = (
        f"https://{location}-aiplatform.googleapis.com/reasoningEngines/v1/"
        f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
    )
    a2a_card_url = f"{a2a_base}/.well-known/agent-card.json"

    parts: list[dict] = []
    async with httpx.AsyncClient(headers=headers, timeout=120) as client:
        resp = await client.get(a2a_card_url)
        resp.raise_for_status()
        card = AgentCard(**resp.json())
        card.url = a2a_base

        factory = ClientFactory(
            ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=message))],
            context_id=_cloud_contexts.get(user_id),
        )

        last_task = None
        got_artifact_update = False
        async for event in a2a_client.send_message(msg):
            if not isinstance(event, tuple):
                continue
            task, update = event
            if task is not None:
                last_task = task
                if getattr(task, "context_id", None):
                    _cloud_contexts[user_id] = task.context_id
            if isinstance(update, TaskArtifactUpdateEvent):
                got_artifact_update = True
                for p in update.artifact.parts:
                    root = getattr(p, "root", p)
                    if isinstance(root, TextPart) and getattr(root, "text", None):
                        parts.append({"kind": "text", "text": root.text})
                    elif getattr(root, "data", None) is not None:
                        parts.append({"kind": "a2ui", "data": root.data})

        if not got_artifact_update and last_task is not None:
            for artifact in getattr(last_task, "artifacts", None) or []:
                for p in artifact.parts:
                    root = getattr(p, "root", p)
                    if isinstance(root, TextPart) and getattr(root, "text", None):
                        parts.append({"kind": "text", "text": root.text})
                    elif getattr(root, "data", None) is not None:
                        parts.append({"kind": "a2ui", "data": root.data})

    return parts


_direct_runner = None
_direct_session_service = None


def _get_direct_runner():
    global _direct_runner, _direct_session_service
    if _direct_runner is None:
        import sys
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from app.agent import root_agent

        _direct_session_service = InMemorySessionService()
        _direct_runner = Runner(
            agent=root_agent,
            session_service=_direct_session_service,
            app_name="hitman",
        )
    return _direct_runner, _direct_session_service


async def _chat_direct(user_id: str, message: str) -> list[dict]:
    """Execute ADK agent directly in-process when local HTTP server is not running."""
    import asyncio
    from google.genai import types

    runner, session_service = _get_direct_runner()
    session_id = _local_sessions.get(user_id)
    sess = None
    if session_id:
        try:
            sess = session_service.get_session_sync(session_id=session_id)
        except Exception:
            sess = None

    if not sess:
        sess = session_service.create_session_sync(user_id=user_id, app_name="hitman")
        session_id = sess.id
        _local_sessions[user_id] = session_id

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    def _sync_run():
        return list(
            runner.run(
                new_message=content,
                user_id=user_id,
                session_id=session_id,
            )
        )

    events = await asyncio.to_thread(_sync_run)
    parts: list[dict] = []
    for event in events:
        if getattr(event, "author", None) in ("hitman", "model", "bot", "assistant"):
            c = getattr(event, "content", None)
            if c:
                for p in getattr(c, "parts", []):
                    txt = getattr(p, "text", None)
                    if txt:
                        parts.extend(_parse_local_event_text(txt))
    return parts


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.post("/chat")
async def chat(req: Request):
    t0 = time.perf_counter()
    body = await req.json()
    message = body.get("message", "").strip()
    user_id = body.get("user_id") or "web-user"
    mode = body.get("mode")
    course = body.get("course")
    current_step = body.get("current_step")

    if mode or course or current_step:
        try:
            import app.agent as agent_module
            if mode:
                agent_module.ACTIVE_OPERATION_MODE = mode
            if course:
                agent_module.ACTIVE_TRAINING_COURSE = course
            if current_step:
                agent_module.CURRENT_STEP = current_step
        except Exception as ex:
            logger.warning(f"Failed to sync agent state: {ex}")

    if not message:
        return JSONResponse({"parts": [], "metrics": None})

    # Construct context-enriched message for LLM to ensure accurate step identification
    import app.agent as agent_module
    effective_step = current_step or getattr(agent_module, "CURRENT_STEP", "1-1")
    effective_mode = mode or getattr(agent_module, "ACTIVE_OPERATION_MODE", "NORMAL")
    effective_course = course or getattr(agent_module, "ACTIVE_TRAINING_COURSE", "original")

    if not message.startswith("[HITMAN 運用コンテキスト"):
        context_header = (
            f"[HITMAN 運用コンテキスト: モード={effective_mode}, "
            f"コース={effective_course}, 現在進行中ステップ={effective_step}]\n"
        )
        llm_message = f"{context_header}{message}"
    else:
        llm_message = message

    if RESOURCE:
        parts = await _chat_cloud(user_id, llm_message)
    elif os.environ.get("USE_LOCAL_AGENT_SERVER", "false").lower() == "true":
        try:
            parts = await _chat_local(user_id, llm_message)
        except Exception:
            parts = await _chat_direct(user_id, llm_message)
    else:
        parts = await _chat_direct(user_id, llm_message)

    if not parts:
        parts = [{"kind": "text", "text": "(応答がありませんでした。もう一度お試しください。)"}]

    latency_sec = time.perf_counter() - t0
    latency_ms = round(latency_sec * 1000, 1)

    # Calculate token count and estimated cost
    # Gemini 2.5 Flash: $0.075 / 1M input tokens, $0.30 / 1M output tokens (1 USD = 150 JPY)
    # Cloud Run: 1 vCPU ($0.000024/s) + 512MB RAM ($0.00000125/s) = $0.00002525 / s
    gemini_in_rate = 0.00001125    # JPY per input token
    gemini_out_rate = 0.000045      # JPY per output token
    cloud_run_rate = 0.0037875      # JPY per second of request processing

    # Estimate input tokens: message + base SOP/system prompt context (~450 tokens)
    input_cjk = len(re.findall(r'[\u3000-\u9fff\uff00-\uffef]', message))
    input_tokens = int(input_cjk * 1.3 + (len(message) - input_cjk) * 0.35) + 450

    # Estimate output tokens: texts + A2UI JSON payload
    out_text = "".join(
        p.get("text", "") for p in parts if p.get("kind") == "text" or "text" in p
    )
    for p in parts:
        if p.get("kind") == "a2ui":
            out_text += json.dumps(p.get("data", {}), ensure_ascii=False)
    out_cjk = len(re.findall(r'[\u3000-\u9fff\uff00-\uffef]', out_text))
    output_tokens = max(25, int(out_cjk * 1.3 + (len(out_text) - out_cjk) * 0.35))

    gemini_cost = (input_tokens * gemini_in_rate) + (output_tokens * gemini_out_rate)
    cloud_run_cost = latency_sec * cloud_run_rate
    total_cost = gemini_cost + cloud_run_cost

    metrics = {
        "prompt_tokens": input_tokens,
        "candidate_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "latency_ms": latency_ms,
        "latency_sec": round(latency_sec, 2),
        "gemini_cost_jpy": round(gemini_cost, 4),
        "cloud_run_cost_jpy": round(cloud_run_cost, 4),
        "total_cost_jpy": round(total_cost, 4),
        "free_tier_applied": True,
        "effective_cost_jpy": 0.0,
    }

    return JSONResponse({"parts": parts, "metrics": metrics})


@app.get("/api/sop")
async def get_sop(mode: str = None, course: str = None, workspace: str = None, agent: str = None, env: str = None):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import (
        get_active_approval,
        get_active_branch_rules,
        get_active_parameters,
        get_active_sop,
        get_active_step_sequence,
        set_operation_mode,
    )
    if mode:
        set_operation_mode(mode)
    custom_params = {}
    if workspace:
        custom_params["WORKSPACE_DIR"] = workspace
    if agent:
        custom_params["AGENT_NAME"] = agent
    if env:
        custom_params["PYTHON_ENV"] = env

    return JSONResponse(content={
        "sop": get_active_sop(mode=mode, course=course, params=custom_params if custom_params else None),
        "sequence": get_active_step_sequence(mode=mode, course=course),
        "parameters": get_active_parameters(mode=mode),
        "approval": get_active_approval(mode=mode, course=course),
        "branch_rules": get_active_branch_rules(),
    })


@app.post("/api/training/parameters")
async def set_training_params(req: Request):
    body = await req.json()
    ws = body.get("workspace_dir", "").strip()
    agent_name = body.get("agent_name", "").strip()
    py_env = body.get("python_env", "").strip()

    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import set_training_environment
    res = set_training_environment(workspace_dir=ws, agent_name=agent_name, python_env=py_env)
    return JSONResponse(content=res)


@app.post("/api/sop/import")
async def api_sop_import(req: Request):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import (
        ACTIVE_STEP_SEQUENCE,
        get_active_approval,
        get_active_branch_rules,
        get_active_parameters,
        get_active_sop,
        import_sop_procedure,
    )

    body = await req.json()
    content = body.get("content", "")
    format_type = body.get("format_type", "auto")

    res = import_sop_procedure(content=content, format_type=format_type)
    return JSONResponse(content={
        "result": res,
        "sop": get_active_sop(),
        "sequence": ACTIVE_STEP_SEQUENCE,
        "parameters": get_active_parameters(),
        "approval": get_active_approval(),
        "branch_rules": get_active_branch_rules(),
    })


@app.post("/api/sop/upload-excel")
async def api_sop_upload_excel(file: UploadFile = File(...)):
    """現場Excel手順書（.xlsm / .xlsx）ファイルをアップロードして解析・反映する。"""
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import (
        ACTIVE_STEP_SEQUENCE,
        get_active_approval,
        get_active_branch_rules,
        get_active_parameters,
        get_active_sop,
        import_excel_sop_procedure,
    )

    contents = await file.read()
    res = import_excel_sop_procedure(contents)
    return JSONResponse(content={
        "result": res,
        "sop": get_active_sop(),
        "sequence": ACTIVE_STEP_SEQUENCE,
        "parameters": get_active_parameters(),
        "approval": get_active_approval(),
        "branch_rules": get_active_branch_rules(),
    })


@app.get("/api/sop/sample-xlsm")
async def api_sop_sample_xlsm():
    """実務検証用のサンプルExcel手順書（.xlsm）をダウンロード返却する。"""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sample_path = os.path.join(root_dir, "knowledge", "standard_web_release_sop_v2.1.xlsm")
    legacy_path = os.path.join(root_dir, "knowledge", "現場標準_Webアプリ本番リリース手順書_v2.1.xlsm")
    target_path = sample_path if os.path.exists(sample_path) else legacy_path

    if not os.path.exists(target_path):
        import sys
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        from knowledge.generate_sample_xlsm import generate_sample_xlsm
        generate_sample_xlsm(sample_path)
        target_path = sample_path

    return FileResponse(
        target_path,
        media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
        filename="現場標準_Webアプリ本番リリース手順書_v2.1.xlsm",
    )


@app.post("/api/sop/reset")
async def api_sop_reset(req: Request):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import (
        ACTIVE_STEP_SEQUENCE,
        get_active_approval,
        get_active_branch_rules,
        get_active_parameters,
        get_active_sop,
        reset_active_sop,
    )

    res = reset_active_sop()
    return JSONResponse(content={
        "result": res,
        "sop": get_active_sop(),
        "sequence": ACTIVE_STEP_SEQUENCE,
        "parameters": get_active_parameters(),
        "approval": get_active_approval(),
        "branch_rules": get_active_branch_rules(),
    })


@app.post("/api/sql/analyze")
async def api_analyze_sql(req: Request):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import analyze_sql_impact

    body = await req.json()
    step_number = body.get("step_number", "3-3")
    pre_select_log = body.get("pre_select_log", "")
    sql_content = body.get("sql_content", "")
    sop_requirement = body.get(
        "sop_requirement",
        "テナントT100のstatusをACTIVE、planをENTERPRISEに更新し、他テナントに影響を与えないこと",
    )

    res = analyze_sql_impact(step_number, pre_select_log, sql_content, sop_requirement)
    return JSONResponse(content=res)


@app.post("/api/escalation/gate")
async def api_escalation_gate(req: Request):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import evaluate_escalation_gate

    body = await req.json()
    escalation_result = body.get("escalation_result", "")
    decision = body.get("decision", "")
    grounds = body.get("grounds", "")
    is_standard = body.get("is_standard_procedure", True)
    supervisor_name = body.get("supervisor_name", "")

    res = evaluate_escalation_gate(
        escalation_result=escalation_result,
        decision=decision,
        grounds=grounds,
        is_standard_procedure=is_standard,
        supervisor_name=supervisor_name,
    )
    return JSONResponse(content=res)


@app.post("/api/report/generate")
async def api_report_generate(req: Request):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import generate_final_report

    body = await req.json()
    start_time = body.get("start_time", "")
    end_time = body.get("end_time", "")
    duration_minutes = body.get("duration_minutes", 15)
    mode = body.get("mode", "NORMAL")
    supervisor_name = body.get("supervisor_name", "")
    sop_results = body.get("sop_results", {})
    escalation_record = body.get("escalation_record")

    report = generate_final_report(
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
        mode=mode,
        supervisor_name=supervisor_name,
        sop_results=sop_results,
        escalation_record=escalation_record,
    )
    return JSONResponse(content=report)


@app.get("/api/mode")
async def api_get_mode():
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import get_operation_mode
    return JSONResponse(content=get_operation_mode())


@app.post("/api/mode")
async def api_set_mode(req: Request):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import (
        get_active_approval,
        get_active_branch_rules,
        get_active_parameters,
        get_active_sop,
        get_active_step_sequence,
        set_operation_mode,
    )

    body = await req.json()
    mode = body.get("mode", "NORMAL")
    course = body.get("course", None)
    supervisor_name = body.get("supervisor_name", "")
    supervisor_role = body.get("supervisor_role", "")
    res = set_operation_mode(mode, supervisor_name, supervisor_role)
    effective_mode = res.get("mode", mode)
    res["sop"] = get_active_sop(mode=effective_mode, course=course)
    res["sequence"] = get_active_step_sequence(mode=effective_mode, course=course)
    res["parameters"] = get_active_parameters(mode=effective_mode)
    res["approval"] = get_active_approval(mode=effective_mode, course=course)
    res["branch_rules"] = get_active_branch_rules()
    return JSONResponse(content=res)


@app.post("/api/training/course")
async def api_training_course(req: Request):
    """研修モードの受講コース（'original' / 'hitman_clone'）を切り替える。"""
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import (
        get_active_approval,
        get_active_branch_rules,
        get_active_parameters,
        set_training_course,
    )

    body = await req.json()
    course = body.get("course", "original")
    res = set_training_course(course)
    return JSONResponse(content={
        "result": res,
        "course": res.get("course"),
        "course_name": res.get("course_name"),
        "sop": res.get("sop"),
        "sequence": res.get("step_sequence"),
        "parameters": get_active_parameters(mode="TRAINING"),
        "approval": get_active_approval(mode="TRAINING", course=course),
        "branch_rules": get_active_branch_rules(),
    })


@app.post("/api/supervisor/skip")
async def api_supervisor_skip(req: Request):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import request_supervisor_step_skip

    body = await req.json()
    step = body.get("step_to_skip", "")
    name = body.get("supervisor_name", "")
    role = body.get("supervisor_role", "")
    rationale = body.get("skip_rationale", "")
    confirmed = body.get("user_responsibility_confirmed", False)

    res = request_supervisor_step_skip(step, name, role, rationale, confirmed)
    return JSONResponse(content=res)


@app.post("/api/training/guidance")
async def api_training_guidance(req: Request):
    import sys
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from app.agent import guide_training_app_creation

    body = await req.json()
    idea = body.get("idea", "")
    course_type = body.get("course_type", "custom")
    res = guide_training_app_creation(idea, course_type)
    return JSONResponse(content=res)



# Static UI mount with no-cache headers for index.html
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

@app.get("/")
async def serve_index():
    idx_path = os.path.join(static_dir, "index.html")
    response = FileResponse(idx_path)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 3000))
    uvicorn.run(app, host="0.0.0.0", port=port)
