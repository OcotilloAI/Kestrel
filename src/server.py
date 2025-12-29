import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
from session_manager import SessionManager
from agent_runner import AgentRunner
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

# Global Session Manager
manager = SessionManager()
llm_client = LLMClient()
agent_runner = AgentRunner(llm_client)
CONTROLLER_ENABLED = os.environ.get("GOOSE_CONTROLLER_ENABLED", "0") == "1"
CONTROLLER_MODEL = os.environ.get(
    "LLM_CONTROLLER_MODEL",
    os.environ.get("GOOSE_CONTROLLER_MODEL", os.environ.get("LLM_MODEL", "qwen3-coder:30b-a3b-q4_K_M")),
)

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

        def extract_required_phrases(source: str) -> list[str]:
            phrases: list[str] = []
            for match in re.findall(r"\"([^\"]{3,})\"", source):
                phrases.append(match)
            for match in re.findall(r"'([^']{3,})'", source):
                phrases.append(match)
            for match in re.findall(r"`([^`]{3,})`", source):
                phrases.append(match)
            return phrases

        def mentions_source(text: str, source: str) -> bool:
            tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]+", source.lower())
            stopwords = {
                "the", "and", "with", "that", "this", "from", "into", "were", "then",
                "just", "only", "also", "have", "has", "had", "your", "you", "for",
                "are", "was", "will", "would", "could", "should", "about", "what",
                "when", "where", "which", "able", "make", "made", "over", "under",
                "after", "before", "into", "onto", "from", "been", "being", "more",
            }
            keywords = [t for t in tokens if t not in stopwords and len(t) > 3]
            if not keywords:
                return True
            haystack = text.lower()
            hits = sum(1 for k in keywords[:20] if k in haystack)
            return hits >= 2

        def includes_required_phrases(text: str, source: str) -> bool:
            phrases = extract_required_phrases(source)
            if not phrases:
                return True
            haystack = text.lower()
            return all(p.lower() in haystack for p in phrases[:2])

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
        if raw_summary and has_format(raw_summary) and mentions_source(raw_summary, source_text) and includes_required_phrases(raw_summary, source_text):
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

async def generate_recap(source_text: str) -> str:
    prompt = (
        "Provide a longer recap for the user-visible transcript.\n"
        "Include what was done, key outputs, and what remains to do.\n"
        "Use short paragraphs. Do not invent details.\n\n"
        f"---\n{source_text}\n---"
    )
    try:
        return await llm_client.chat(
            [
                {"role": "system", "content": "You are a precise technical summarizer."},
                {"role": "user", "content": prompt},
            ],
            model_override=_summary_model(),
        )
    except Exception as e:
        return f"Recap failed: {e}"

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

def is_affirmative(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {
        "yes", "y", "yep", "yeah", "ok", "okay", "sure", "please do",
        "go ahead", "proceed", "do it", "start", "start now", "sounds good",
        "looks good", "confirm",
    }

async def orchestrator_plan(user_text: str) -> Optional[dict]:
    if not CONTROLLER_ENABLED:
        return None
    prompt = (
        "You are the orchestrator for a voice-first software development assistant.\n"
        "Your job is to turn the user's request into an actionable plan or ask clarifying questions.\n"
        "Avoid tool execution yourself. Keep answers concise for speech.\n\n"
        "Rules:\n"
        "- If the request is clear enough, return a task plan with sensible defaults.\n"
        "- Only ask questions when missing info blocks a first pass.\n"
        "- Ask no more than FIVE short questions.\n"
        "- Do not propose implementation details beyond a task list.\n\n"
        "Return JSON only, no extra text:\n"
        "- For clarification:\n"
        "  {\"action\":\"clarify\",\"questions\":[\"...\"]}\n"
        "- For a plan:\n"
        "  {\"action\":\"plan\",\"normalized_request\":\"...\",\"tasks\":[\"...\"]}\n\n"
        f"User request:\n{user_text}\n"
    )
    try:
        raw = await llm_client.chat(
            [
                {"role": "system", "content": "You are a concise planning assistant."},
                {"role": "user", "content": prompt},
            ],
            model_override=CONTROLLER_MODEL,
        )
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

    async def send_phase_summary(text: str) -> None:
        summary_event = make_event(
            event_type="summary",
            role="system",
            content=text,
            source="summary",
        )
        manager.record_event(session_id, summary_event)
        await websocket.send_text(json.dumps(summary_event))

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
    async def handle_agent_run(user_text: str):
        assistant_chunks: list[str] = []
        tool_chunks: list[str] = []
        summary_chunks: list[str] = []
        async for event in agent_runner.run(session, user_text):
            event_type = event.get("type", "assistant")
            role = event.get("role", "assistant")
            content = event.get("content", "")
            source = event.get("source", role)
            metadata = event.get("metadata", {})
            outgoing = make_event(
                event_type=event_type,
                role=role,
                content=content,
                metadata=metadata,
                source=source,
            )
            manager.record_event(session_id, outgoing)
            await websocket.send_text(json.dumps(outgoing))
            if event_type == "assistant" and content:
                assistant_chunks.append(content)
            if event_type == "tool" and content:
                tool_chunks.append(content)
            if content and event_type in {"assistant", "tool", "system"}:
                summary_chunks.append(content)
        combined = "".join(assistant_chunks).strip()
        summary_source = "\n".join(summary_chunks).strip()
        if not summary_source:
            summary_source = "No agent output was captured for this phase."
        try:
            summary = await generate_summary(summary_source)
            await send_phase_summary(summary)
            recap = await generate_recap(summary_source)
            recap_event = make_event(event_type="recap", role="system", content=recap, source="recap")
            manager.record_event(session_id, recap_event)
            await websocket.send_text(json.dumps(recap_event))
        except Exception as e:
            error_event = make_event(
                event_type="system",
                role="system",
                content=f"Summary failed: {e}",
                source="system",
            )
            manager.record_event(session_id, error_event)
            await websocket.send_text(json.dumps(error_event))

    try:
        while True:
            data = await websocket.receive_text()
            print(f"[{session_id}] Received: {data}")
            event = make_event(event_type="user", role="user", content=data, source="user")
            manager.record_event(session_id, event)

            detail_path = is_detail_request(data)
            if detail_path:
                await send_detail_response(detail_path)
                continue

            meta = manager.get_session_metadata(session_id) or {}
            pending = meta.get("pending_plan")
            if pending:
                if is_affirmative(data) and pending.get("tasks"):
                    meta["pending_plan"] = None
                    plan_tasks = pending.get("tasks", [])
                    normalized = pending.get("normalized_request", pending.get("original_request", ""))
                    task_block = "\n".join(f"- [ ] {task}" for task in plan_tasks)
                    agent_prompt = (
                        "Execute the plan below. Validate the work with tests if possible.\n\n"
                        f"Working directory: {meta.get('cwd')}\n"
                        f"User request:\n{normalized}\n\n"
                        f"Plan:\n```tasks\n{task_block}\n```\n"
                    )
                    await handle_agent_run(agent_prompt)
                elif is_affirmative(data) and not pending.get("tasks"):
                    plan_input = pending.get("original_request", "") + "\nAssume sensible defaults."
                    decision = await orchestrator_plan(plan_input)
                    if decision and isinstance(decision, dict) and decision.get("action") == "plan":
                        pending["normalized_request"] = decision.get("normalized_request", pending.get("original_request", ""))
                        pending["tasks"] = decision.get("tasks", [])
                        task_block = "\n".join(f"- [ ] {task}" for task in pending.get("tasks", []))
                        controller_event = make_event(
                            event_type="assistant",
                            role="controller",
                            content=f"Proposed plan:\n```tasks\n{task_block}\n```\nProceed?",
                            metadata={"controller_action": "plan"},
                            source="controller",
                        )
                        manager.record_event(session_id, controller_event)
                        await websocket.send_text(json.dumps(controller_event))
                        await send_phase_summary(
                            "I did propose the plan above.\n"
                            "I learned we should wait for your confirmation.\n"
                            "Next, should I proceed?"
                        )
                        meta["pending_plan"] = pending
                else:
                    answers = pending.get("answers", [])
                    answers.append(data)
                    pending["answers"] = answers
                    plan_input = pending.get("original_request", "") + "\nUser clarifications:\n" + "\n".join(answers)
                    decision = await orchestrator_plan(plan_input)
                    if decision and isinstance(decision, dict):
                        action = decision.get("action")
                        if action == "clarify" and decision.get("questions"):
                            questions = "\n".join(f"- {q}" for q in decision.get("questions", []))
                            controller_event = make_event(
                                event_type="assistant",
                                role="controller",
                                content=f"I need a few details plan-ready:\n{questions}",
                                metadata={"controller_action": "clarify"},
                                source="controller",
                            )
                            manager.record_event(session_id, controller_event)
                            await websocket.send_text(json.dumps(controller_event))
                            await send_phase_summary(
                                "I did ask a few clarifying questions above.\n"
                                "I learned we need those details to produce a plan.\n"
                                "Next, could you answer them?"
                            )
                            pending["questions"] = decision.get("questions", [])
                            meta["pending_plan"] = pending
                            continue
                        if action == "plan" and decision.get("tasks"):
                            pending["normalized_request"] = decision.get("normalized_request", pending.get("original_request", ""))
                            pending["tasks"] = decision.get("tasks", [])
                            task_block = "\n".join(f"- [ ] {task}" for task in pending.get("tasks", []))
                            controller_event = make_event(
                                event_type="assistant",
                                role="controller",
                                content=f"Proposed plan:\n\n```tasks\n{task_block}\n```\n\nProceed?",
                                metadata={"controller_action": "plan"},
                                source="controller",
                            )
                            manager.record_event(session_id, controller_event)
                            await websocket.send_text(json.dumps(controller_event))
                            await send_phase_summary(
                                "I did propose the plan above.\n"
                                "I learned we should wait for your confirmation.\n"
                                "Next, should I proceed?"
                            )
                            meta["pending_plan"] = pending
                            continue
                continue

            decision = await orchestrator_plan(data)
            if decision and isinstance(decision, dict):
                action = decision.get("action")
                if action == "clarify" and decision.get("questions"):
                    questions = "\n".join(f"- {q}" for q in decision.get("questions", []))
                    controller_event = make_event(
                        event_type="assistant",
                        role="controller",
                        content=f"I need a few details plan-ready:\n{questions}",
                        metadata={"controller_action": "clarify"},
                        source="controller",
                    )
                    manager.record_event(session_id, controller_event)
                    await websocket.send_text(json.dumps(controller_event))
                    await send_phase_summary(
                        "I did ask a few clarifying questions above.\n"
                        "I learned we need those details to produce a plan.\n"
                        "Next, could you answer them?"
                    )
                    meta["pending_plan"] = {
                        "original_request": data,
                        "questions": decision.get("questions", []),
                        "answers": [],
                    }
                    continue
                if action == "plan" and decision.get("tasks"):
                    task_block = "\n".join(f"- [ ] {task}" for task in decision.get("tasks", []))
                    controller_event = make_event(
                        event_type="assistant",
                        role="controller",
                        content=f"Proposed plan:\n\n```tasks\n{task_block}\n```\n\nProceed?",
                        metadata={"controller_action": "plan"},
                        source="controller",
                    )
                    manager.record_event(session_id, controller_event)
                    await websocket.send_text(json.dumps(controller_event))
                    await send_phase_summary(
                        "I did propose the plan above.\n"
                        "I learned we should wait for your confirmation.\n"
                        "Next, should I proceed?"
                    )
                    meta["pending_plan"] = {
                        "original_request": data,
                        "normalized_request": decision.get("normalized_request", data),
                        "tasks": decision.get("tasks", []),
                        "answers": [],
                    }
                    continue

            agent_prompt = (
                "Build and validate the user's request.\n"
                "If critical information is missing, ask up to three focused questions.\n"
                "When you finish, provide a concise completion statement.\n\n"
                f"Working directory: {meta.get('cwd')}\n"
                f"User request:\n{data}\n"
            )
            await handle_agent_run(agent_prompt)
    except WebSocketDisconnect:
        print(f"Client disconnected from {session_id}")
    except Exception as e:
        print(f"Error in session {session_id}: {e}")
