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
# ---------------------

# Global Session Manager
manager = SessionManager()

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
    prompt = f"Please provide a concise, one-sentence summary of the following text. Only return the summary itself, with no preamble or conversational text:\n\n---\n\n{request.text}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ollama_host}/api/generate",
                json={"model": summarizer_model, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            data = response.json()
            return {"summary": data.get("response", "").strip()}
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Ollama: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {e}")

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

@app.delete("/project/{project_name}/branch/{branch_name}")
async def delete_branch(project_name: str, branch_name: str):
    if manager.delete_branch(project_name, branch_name):
        return {"status": "deleted", "project": project_name, "branch": branch_name}
    raise HTTPException(status_code=404, detail="Branch not found")

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
    await websocket.send_text("G: Welcome to Kestrel, Goose is ready to help you code from Kestrel's translations.")
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
                        await websocket.send_text(f"G: {chunk}")
                if not session.is_alive():
                    code = session.return_code()
                    error_msg = f"ERROR: Backend process exited unexpectedly with code {code}"
                    print(error_msg)
                    await websocket.send_text(error_msg)
                    await websocket.close()
                    break
                await asyncio.sleep(0.1)
        sender_task = asyncio.create_task(sender())
        while True:
            data = await websocket.receive_text()
            print(f"[{session_id}] Received: {data}")
            session.send_input(data)
    except WebSocketDisconnect:
        print(f"Client disconnected from {session_id}")
        sender_task.cancel()
    except Exception as e:
        print(f"Error in session {session_id}: {e}")
        sender_task.cancel()
