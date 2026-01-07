import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any
from pydantic import BaseModel
from session_manager import SessionManager
from coder_agent import CoderAgent
from manager_agent import ManagerAgent
from llm_client import LLMClient
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

class ClientEventRequest(BaseModel):
    type: str
    role: str
    source: str
    content: str

class BranchConfig(BaseModel):
    name: Optional[str] = None
    source_branch: Optional[str] = "main"
# ---------------------

# Global Session Manager and Agents
manager = SessionManager()
llm_client = LLMClient()
coder_agent = CoderAgent(llm_client, max_steps=30, max_retries=2)
manager_agent = ManagerAgent(llm_client, coder_agent, max_retries=2)

@app.on_event("startup")
async def startup_event():
    print("Starting Kestrel Session Manager...")

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down all agent sessions...")
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

def _summary_model() -> str:
    return os.environ.get(
        "LLM_SUMMARIZER_MODEL",
        os.environ.get("GOOSE_SUMMARIZER_MODEL", os.environ.get("LLM_MODEL", "qwen3-coder:30b-a3b-q4_K_M")),
    )

async def generate_summary(source_text: str) -> str:
    """Generate a voice-safe summary in 'I did / I learned / Next?' format."""
    prompt = (
        "Summarize the assistant's response as a short, spoken end-of-task recap.\n"
        "Include brief mentions of any code blocks, shell commands, file changes, or outputs.\n"
        "Only use facts present in the text; do not invent details.\n"
        "Output exactly three sentences in this order:\n"
        "1) \"I did ...\"\n"
        "2) \"I learned ...\"\n"
        "3) \"Next ...?\" (ask whether we should proceed)\n"
        "Keep each sentence concise and factual. No bullet points or preamble.\n\n"
        f"---\n{source_text}\n---"
    )

    def normalize_summary(raw_summary: str, source_text: str) -> str:
        def has_format(text: str) -> bool:
            return (
                text.strip().startswith("I did")
                and "I learned" in text
                and "Next" in text
                and "?" in text
            )

        def enforce_next_question(text: str) -> str:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
            if len(sentences) < 3:
                lowered = text.lower()
                if any(token in lowered for token in ("proceed", "continue", "answer")):
                    return text.strip()
                if "next" in lowered:
                    return re.sub(r"(?i)next\s*[^.?!]*\??", "Next, should I proceed?", text.strip())
                return text.strip().rstrip() + " Next, should I proceed?"
            next_sentence = sentences[2]
            if any(token in next_sentence.lower() for token in ("proceed", "continue", "answer")):
                return text.strip()
            sentences[2] = "Next, should I proceed?"
            return " ".join(sentences)

        if raw_summary:
            raw_summary = enforce_next_question(raw_summary.strip())
        if raw_summary and has_format(raw_summary):
            return raw_summary

        code_blocks = len(re.findall(r"```[\s\S]*?```", source_text))
        clean = re.sub(r"```[\s\S]*?```", " code block ", source_text)
        clean = re.sub(r"\s+", " ", clean).strip()
        snippet_words = clean.split()[:12]
        snippet = " ".join(snippet_words) if snippet_words else "the current task context"
        block_phrase = f"{code_blocks} code block(s)" if code_blocks else "no code blocks"
        return enforce_next_question(
            f"I did review the response and noted {block_phrase}.\n"
            f"I learned {snippet}.\n"
            f"Next should we proceed to validate the output and iterate on any remaining gaps?"
        )

    try:
        raw_summary = await llm_client.chat(
            [
                {"role": "system", "content": "You are a concise summarizer."},
                {"role": "user", "content": prompt},
            ],
            model_override=_summary_model(),
        )
    except Exception:
        raw_summary = ""
    return normalize_summary(raw_summary, source_text)


@app.post("/summarize")
async def summarize_text(request: SummarizeRequest):
    try:
        summary = await generate_summary(request.text)
        return {"summary": summary}
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to LLM: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {e}")

@app.post("/session/{session_id}/event")
async def record_client_event(session_id: str, request: ClientEventRequest):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    event = {
        "type": request.type,
        "role": request.role,
        "content": request.content,
        "timestamp": time.time(),
        "metadata": {},
        "source": request.source
    }
    manager.record_event(session_id, event)
    return {"status": "recorded"}

def is_replace_request(text: str) -> bool:
    normalized = text.strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "stop and", "stop this", "cancel this", "cancel that",
            "start over", "new plan", "change direction", "change the plan",
            "ignore previous", "replace plan", "drop the plan",
        )
    )

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

@app.post("/project/{project_name}/branch/{branch_name}/merge")
async def merge_branch(project_name: str, branch_name: str):
    try:
        if manager.merge_branch_into_main(project_name, branch_name):
            return {"status": "merged", "project": project_name, "branch": branch_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {e}")
    raise HTTPException(status_code=404, detail="Branch not found")

@app.post("/project/{project_name}/branch/{branch_name}/sync")
async def sync_branch(project_name: str, branch_name: str):
    try:
        if manager.sync_branch_from_main(project_name, branch_name):
            return {"status": "synced", "project": project_name, "branch": branch_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")
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

@app.get("/session/{session_id}/transcript")
async def get_session_transcript(session_id: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return manager.get_transcript(session_id)

@app.get("/session/{session_id}/transcript/download")
async def download_session_transcript(session_id: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    events = manager.get_transcript(session_id)
    lines = []
    for event in events:
        source = event.get("source") or event.get("role") or event.get("type") or "unknown"
        role = event.get("role") or "unknown"
        content = str(event.get("content", "")).rstrip()
        if not content:
            continue
        lines.append(f"[{source}/{role}] {content}")
    body = "\n\n".join(lines)
    return PlainTextResponse(body)

@app.delete("/session/{session_id}")
async def kill_session(session_id: str, request: Request):
    print(f"--- KILL SESSION REQUEST RECEIVED for {session_id} ---")
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

    def make_event(event_type: str, role: str, content: str, metadata: Optional[dict] = None, source: Optional[str] = None):
        return {
            "type": event_type,
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
            "source": source or role or event_type
        }

    def is_detail_request(text: str) -> Optional[str]:
        match = re.match(r"^\s*read\s+(?:the\s+)?(?:file|script)\s+(.+)$", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.match(r"^\s*read\s+([\w./-]+)$", text, re.IGNORECASE)
        if match and "." in match.group(1):
            return match.group(1).strip()
        return None

    async def send_detail_response(path_hint: str):
        meta = manager.get_session_metadata(session_id) or {}
        cwd = meta.get("cwd")
        if not cwd:
            return
        file_path = os.path.abspath(os.path.join(cwd, path_hint))
        if not file_path.startswith(os.path.abspath(cwd)):
            detail_event = make_event(
                event_type="detail",
                role="controller",
                content="Sorry, I can only read files within the session directory.",
                source="detail"
            )
            manager.record_event(session_id, detail_event)
            await websocket.send_text(json.dumps(detail_event))
            return
        if not os.path.isfile(file_path):
            detail_event = make_event(
                event_type="detail",
                role="controller",
                content=f"I couldn't find {path_hint} in this session.",
                source="detail"
            )
            manager.record_event(session_id, detail_event)
            await websocket.send_text(json.dumps(detail_event))
            return
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read()
        except Exception:
            detail_event = make_event(
                event_type="detail",
                role="controller",
                content=f"I couldn't read {path_hint}.",
                source="detail"
            )
            manager.record_event(session_id, detail_event)
            await websocket.send_text(json.dumps(detail_event))
            return

        header = make_event(
            event_type="detail",
            role="controller",
            content=f"Reading {path_hint}.",
            source="detail"
        )
        manager.record_event(session_id, header)
        await websocket.send_text(json.dumps(header))

        chunk_size = 1200
        for idx in range(0, len(content), chunk_size):
            chunk = content[idx: idx + chunk_size]
            detail_event = make_event(event_type="detail", role="controller", content=chunk, source="detail")
            manager.record_event(session_id, detail_event)
            await websocket.send_text(json.dumps(detail_event))

    async def handle_request(user_text: str) -> None:
        """Handle a request using the hierarchical Manager + Coder system."""
        meta = manager.get_session_metadata(session_id) or {}
        context_seed = meta.get("context_seed")

        async for event in manager_agent.process_request(session, user_text, context_seed):
            event_type = event.get("type", "manager")
            role = event.get("role", "manager")
            content = event.get("content", "")
            source = event.get("source", role)
            event_metadata = event.get("metadata", {})

            # Handle clarification requests
            if event_type == "clarify":
                clarify_event = make_event(
                    event_type="assistant",
                    role="controller",
                    content=f"I need clarification: {content}",
                    metadata={"controller_action": "clarify"},
                    source="controller",
                )
                manager.record_event(session_id, clarify_event)
                await websocket.send_text(json.dumps(clarify_event))

                # Store pending clarification
                meta["pending_clarify"] = {"original_request": user_text}
                return

            # Handle plan proposals
            if event_type == "plan":
                plan_event = make_event(
                    event_type="assistant",
                    role="controller",
                    content=content,
                    metadata=event_metadata,
                    source="controller",
                )
                manager.record_event(session_id, plan_event)
                await websocket.send_text(json.dumps(plan_event))
                continue

            # Handle task lifecycle events
            if event_type in ("task_complete", "task_failed", "task_start"):
                task_event = make_event(
                    event_type=event_type,
                    role=role,
                    content=content,
                    metadata=event_metadata,
                    source=source,
                )
                manager.record_event(session_id, task_event)
                await websocket.send_text(json.dumps(task_event))
                continue

            # Handle summary (final output for voice)
            if event_type == "summary":
                summary_event = make_event(
                    event_type="summary",
                    role="system",
                    content=content,
                    metadata=event_metadata,
                    source="summary",
                )
                manager.record_event(session_id, summary_event)
                await websocket.send_text(json.dumps(summary_event))
                continue

            # Default: forward event as-is
            outgoing = make_event(
                event_type=event_type,
                role=role,
                content=content,
                metadata=event_metadata,
                source=source,
            )
            manager.record_event(session_id, outgoing)
            await websocket.send_text(json.dumps(outgoing))

    # Send welcome message
    meta = manager.get_session_metadata(session_id) or {}
    cwd = meta.get("cwd", "unknown")
    if not meta.get("welcome_sent"):
        welcome_event = make_event(
            event_type="system",
            role="system",
            content="Hello, I'm Kestrel. What are we working on today?",
            source="system"
        )
        manager.record_event(session_id, welcome_event)
        await websocket.send_text(json.dumps(welcome_event))
        cwd_event = make_event(
            event_type="system",
            role="system",
            content=f"Working directory: {cwd}",
            source="system",
        )
        manager.record_event(session_id, cwd_event)
        await websocket.send_text(json.dumps(cwd_event))
        meta["welcome_sent"] = True

    try:
        while True:
            data = await websocket.receive_text()
            print(f"[{session_id}] Received: {data}")
            event = make_event(event_type="user", role="user", content=data, source="user")
            manager.record_event(session_id, event)

            # Handle detail requests (read file)
            detail_path = is_detail_request(data)
            if detail_path:
                await send_detail_response(detail_path)
                continue

            # Handle cancel/replace requests
            meta = manager.get_session_metadata(session_id) or {}
            if is_replace_request(data):
                meta["pending_clarify"] = None
                # Continue to handle as new request

            # Handle pending clarification
            pending = meta.get("pending_clarify")
            if pending:
                # Append user response as clarification and retry
                original = pending.get("original_request", "")
                clarified = f"{original}\n\nUser clarification: {data}"
                meta["pending_clarify"] = None
                await handle_request(clarified)
                continue

            # Handle new request via Manager
            await handle_request(data)

    except WebSocketDisconnect:
        print(f"Client disconnected from {session_id}")
    except Exception as e:
        import traceback
        print(f"Error in session {session_id}: {type(e).__name__}: {e}")
        traceback.print_exc()
        try:
            await websocket.send_json({
                "type": "error",
                "role": "system",
                "content": f"Session error: {type(e).__name__}: {e}",
                "source": "system",
            })
        except Exception:
            pass  # WebSocket may already be closed
