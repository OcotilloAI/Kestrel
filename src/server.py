import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
from session_manager import SessionManager
import os
import httpx
import json
import time
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class SessionConfig(BaseModel):
    cwd: Optional[str] = None
    copy_from_path: Optional[str] = None

class RenameConfig(BaseModel):
    name: str

class SummarizeRequest(BaseModel):
    text: str

class BranchConfig(BaseModel):
    name: Optional[str] = None
    source_branch: Optional[str] = "main"
# ---------------------

# Global Session Manager
manager = SessionManager()
CONTROLLER_ENABLED = os.environ.get("GOOSE_CONTROLLER_ENABLED", "0") == "1"
CONTROLLER_MODEL = os.environ.get("GOOSE_CONTROLLER_MODEL", os.environ.get("GOOSE_MODEL", "qwen3-coder:30b-a3b-q4_K_M"))

@app.on_event("startup")
async def startup_event():
    print("Starting Kestrel Session Manager...")

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down all Goose sessions...")
    manager.shutdown_all()

# Serve Frontend
dist_dir = os.path.join(os.path.dirname(__file__), "..", "ui", "web", "dist")

if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

@app.get("/")
async def get():
    path = os.path.join(dist_dir, "index.html")
    if os.path.exists(path):
        print(f"Serving frontend from: {path}")
        return FileResponse(path)
    print(f"Frontend build not found at {path}, falling back to legacy")
    return FileResponse('static/index.html.bak')

@app.post("/summarize")
async def summarize_text(request: SummarizeRequest):
    ollama_host = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
    summarizer_model = os.environ.get("GOOSE_SUMMARIZER_MODEL", os.environ.get("GOOSE_MODEL", "qwen3-coder:30b-a3b-q4_K_M"))
    prompt = (
        "Summarize the assistant's response as a short, spoken end-of-task recap.\n"
        "Include brief mentions of any code blocks, shell commands, file changes, or outputs.\n"
        "Output exactly three sentences in this order:\n"
        "1) \"I did ...\"\n"
        "2) \"I learned ...\"\n"
        "3) \"Next ...\"\n"
        "Keep each sentence concise and factual. No bullet points or preamble.\n\n"
        f"---\n{request.text}\n---"
    )
    def normalize_summary(raw_summary: str, source_text: str) -> str:
        def has_format(text: str) -> bool:
            return (
                text.strip().startswith("I did")
                and "I learned" in text
                and "Next" in text
            )

        if raw_summary and has_format(raw_summary):
            return raw_summary.strip()

        code_blocks = len(re.findall(r"```[\\s\\S]*?```", source_text))
        clean = re.sub(r"```[\\s\\S]*?```", " code block ", source_text)
        clean = re.sub(r"\\s+", " ", clean).strip()
        snippet_words = clean.split()[:12]
        snippet = " ".join(snippet_words) if snippet_words else "the current task context"
        block_phrase = f"{code_blocks} code block(s)" if code_blocks else "no code blocks"
        return (
            f"I did review the response and noted {block_phrase}.\n"
            f"I learned {snippet}.\n"
            f"Next validate the output and iterate on any remaining gaps."
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ollama_host}/api/generate",
                json={"model": summarizer_model, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            data = response.json()
            raw_summary = data.get("response", "").strip()
            return {"summary": normalize_summary(raw_summary, request.text)}
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Ollama: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {e}")

async def controller_decision(user_text: str) -> Optional[dict]:
    if not CONTROLLER_ENABLED:
        return None
    ollama_host = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
    prompt = (
        "You are the controller for a voice-first software development assistant.\n"
        "Decide whether to ask a clarifying question BEFORE execution.\n"
        "If clarification is needed, return JSON:\n"
        "{\"action\":\"clarify\",\"question\":\"<short question>\"}\n"
        "If no clarification is needed, return JSON:\n"
        "{\"action\":\"execute\",\"task\":\"<normalized task>\"}\n"
        "Return JSON only, no extra text.\n\n"
        f"User request:\n{user_text}\n"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ollama_host}/api/generate",
                json={"model": CONTROLLER_MODEL, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "").strip()
            return json.loads(raw)
    except Exception:
        return None

@app.get("/sessions")
async def list_sessions():
    return manager.list_sessions()

@app.get("/projects")
async def list_projects():
    return manager.list_projects()

@app.get("/project/{project_name}/branches")
async def list_branches(project_name: str):
    return manager.list_branches(project_name)

@app.delete("/project/{project_name}")
async def delete_project(project_name: str):
    if manager.delete_project(project_name):
        return {"status": "deleted", "project": project_name}
    raise HTTPException(status_code=404, detail="Project not found")

@app.post("/project/{project_name}/branch")
async def create_branch(project_name: str, config: BranchConfig):
    try:
        branch_name = manager.create_branch(
            project_name=project_name,
            branch_name=config.name,
            source_branch=config.source_branch or "main",
        )
        return {"status": "created", "project": project_name, "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/project/{project_name}/branch/{branch_name}")
async def delete_branch(project_name: str, branch_name: str):
    if manager.delete_branch(project_name, branch_name):
        return {"status": "deleted", "project": project_name, "branch": branch_name}
    raise HTTPException(status_code=404, detail="Branch not found")

@app.post("/project/{project_name}/branch/{branch_name}/session")
async def open_branch_session(project_name: str, branch_name: str):
    branch_dir = manager.workdir_root / project_name / branch_name
    if not branch_dir.exists():
        raise HTTPException(status_code=404, detail="Branch not found")
    try:
        session_id = manager.create_session(cwd=str(branch_dir))
        metadata = manager.get_session_metadata(session_id)
        return {"session_id": session_id, "cwd": metadata["cwd"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/create")
async def create_session(config: SessionConfig):
    cwd_param = config.cwd
    if cwd_param == ".":
        cwd_param = None
    if cwd_param and not os.path.exists(cwd_param):
        raise HTTPException(status_code=400, detail=f"Directory {cwd_param} does not exist")
    try:
        session_id = manager.create_session(cwd=cwd_param, copy_from_path=config.copy_from_path)
        metadata = manager.get_session_metadata(session_id)
        return {"session_id": session_id, "cwd": metadata["cwd"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/{session_id}/rename")
async def rename_session(session_id: str, config: RenameConfig):
    if manager.rename_session(session_id, config.name):
        return {"status": "renamed", "session_id": session_id, "new_name": config.name}
    raise HTTPException(status_code=404, detail="Session not found")

@app.delete("/session/{session_id}")
async def kill_session(session_id: str, request: Request):
    print(f"--- KILL SESSION REQUEST RECEIVED for {session_id} ---")
    print(f"Headers: {request.headers}")
    print(f"Client: {request.client}")
    if manager.kill_session(session_id):
        return {"status": "terminated", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    session = manager.get_session(session_id)
    if not session:
        await websocket.accept()
        await websocket.close(code=1008, reason="Session not found")
        return
    await websocket.accept()
    print(f"Client connected to session {session_id}")
    def make_event(event_type: str, role: str, content: str, metadata: Optional[dict] = None):
        return {
            "type": event_type,
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }

    welcome_event = make_event(
        event_type="system",
        role="system",
        content="Welcome to Kestrel, Goose is ready to help you code from Kestrel's translations."
    )
    manager.record_event(session_id, welcome_event)
    await websocket.send_text(json.dumps(welcome_event))
    try:
        async def sender():
            while True:
                chunks = list(session.get_output())
                for chunk in chunks:
                    if chunk:
                        if "starting session | provider:" in chunk or \
                           "goose is running!" in chunk or \
                           "Context: ○" in chunk or \
                           "working directory:" in chunk or \
                           "session id:" in chunk:
                            continue
                        event_type = "assistant"
                        role = "coder"
                        content = chunk
                        if chunk.startswith("[LOG]"):
                            event_type = "system"
                            role = "system"
                        event = make_event(event_type=event_type, role=role, content=content)
                        manager.record_event(session_id, event)
                        await websocket.send_text(json.dumps(event))
                if not session.is_alive():
                    code = session.return_code()
                    error_msg = f"ERROR: Backend process exited unexpectedly with code {code}"
                    print(error_msg)
                    event = make_event(event_type="system", role="system", content=error_msg)
                    manager.record_event(session_id, event)
                    await websocket.send_text(json.dumps(event))
                    await websocket.close()
                    break
                await asyncio.sleep(0.1)
        sender_task = asyncio.create_task(sender())
        while True:
            data = await websocket.receive_text()
            print(f"[{session_id}] Received: {data}")
            event = make_event(event_type="user", role="user", content=data)
            manager.record_event(session_id, event)

            decision = await controller_decision(data)
            if decision and isinstance(decision, dict):
                action = decision.get("action")
                if action == "clarify" and decision.get("question"):
                    controller_event = make_event(
                        event_type="assistant",
                        role="controller",
                        content=decision["question"],
                        metadata={"controller_action": "clarify"}
                    )
                    manager.record_event(session_id, controller_event)
                    await websocket.send_text(json.dumps(controller_event))
                    continue
                if action == "execute" and decision.get("task"):
                    data = decision["task"]

            session.send_input(data)
    except WebSocketDisconnect:
        print(f"Client disconnected from {session_id}")
        sender_task.cancel()
    except Exception as e:
        print(f"Error in session {session_id}: {e}")
        sender_task.cancel()
