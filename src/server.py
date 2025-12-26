import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from pydantic import BaseModel
from session_manager import SessionManager
import os

app = FastAPI()

# Global Session Manager
manager = SessionManager()

class SessionConfig(BaseModel):
    cwd: Optional[str] = None
    copy_from_path: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    print("Starting Kestrel Session Manager...")

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down all Goose sessions...")
    manager.shutdown_all()

# Serve Frontend
# Ensure the ui/web/dist directory exists (it should be built)
dist_dir = os.path.join(os.path.dirname(__file__), "..", "ui", "web", "dist")

if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

@app.get("/")
async def get():
    if os.path.exists(os.path.join(dist_dir, "index.html")):
        return FileResponse(os.path.join(dist_dir, "index.html"))
    return FileResponse('static/index.html') # Fallback if build missing

@app.get("/sessions")
async def list_sessions():
    return manager.list_sessions()

@app.post("/session/create")
async def create_session(config: SessionConfig):
    # If explicit path provided, validate it
    cwd_param = config.cwd
    if cwd_param == ".":
        cwd_param = None
        
    if cwd_param:
        if not os.path.exists(cwd_param):
             raise HTTPException(status_code=400, detail=f"Directory {cwd_param} does not exist")

    try:
        session_id = manager.create_session(cwd=cwd_param, copy_from_path=config.copy_from_path)
        metadata = manager.get_session_metadata(session_id)
        return {"session_id": session_id, "cwd": metadata["cwd"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RenameConfig(BaseModel):
    name: str

@app.post("/session/{session_id}/rename")
async def rename_session(session_id: str, config: RenameConfig):
    if manager.rename_session(session_id, config.name):
        return {"status": "renamed", "session_id": session_id, "new_name": config.name}
    raise HTTPException(status_code=404, detail="Session not found")

@app.delete("/session/{session_id}")
async def kill_session(session_id: str):
    if manager.kill_session(session_id):
        return {"status": "terminated", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    session = manager.get_session(session_id)
    if not session:
        await websocket.close(code=1000, reason="Session not found")
        return

    await websocket.accept()
    print(f"Client connected to session {session_id}")
    
    try:
        # Background task to stream Goose output to client
        async def sender():
            while True:
                # Poll Goose output
                chunks = list(session.get_output())
                for chunk in chunks:
                    if chunk:
                        await websocket.send_text(f"G: {chunk}")
                
                # Check if process died
                if not session.is_alive():
                    code = session.return_code()
                    error_msg = f"ERROR: Backend process exited unexpectedly with code {code}"
                    print(error_msg)
                    await websocket.send_text(error_msg)
                    await websocket.close()
                    break

                await asyncio.sleep(0.1)

        sender_task = asyncio.create_task(sender())

        # Main loop: Listen for client input
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