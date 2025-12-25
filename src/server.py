import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from goose_wrapper import GooseWrapper
import os

app = FastAPI()

# Global Goose Instance
goose = GooseWrapper()
current_config = {
    "cwd": os.getcwd()
}

class SessionConfig(BaseModel):
    cwd: str

@app.on_event("startup")
async def startup_event():
    print("Starting Goose backend...")
    goose.start(current_config["cwd"])
    # Wait a moment for initialization
    await asyncio.sleep(2)
    # Drain initial logs
    for line in goose.get_output():
        print(f"[Goose Init]: {line.strip()}")

@app.on_event("shutdown")
async def shutdown_event():
    print("Stopping Goose backend...")
    goose.stop()

# Serve Frontend
# Ensure static directory exists
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get():
    return FileResponse('static/index.html')

@app.get("/session/status")
async def get_session_status():
    return current_config

@app.post("/session/config")
async def update_session_config(config: SessionConfig):
    if not os.path.exists(config.cwd):
        raise HTTPException(status_code=400, detail="Directory does not exist")
    
    if not os.path.isdir(config.cwd):
        raise HTTPException(status_code=400, detail="Path is not a directory")

    print(f"Switching session to: {config.cwd}")
    try:
        goose.restart(cwd=config.cwd)
        current_config["cwd"] = config.cwd
        return {"status": "restarted", "cwd": config.cwd}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")
    
    try:
        # Background task to stream Goose output to client
        async def sender():
            while True:
                # Poll Goose output
                lines = list(goose.get_output())
                for line in lines:
                    if line.strip():
                        await websocket.send_text(f"G: {line.strip()}")
                await asyncio.sleep(0.1)

        sender_task = asyncio.create_task(sender())

        # Main loop: Listen for client input
        while True:
            data = await websocket.receive_text()
            print(f"Received: {data}")
            # Send to Goose
            goose.send_input(data)

    except WebSocketDisconnect:
        print("Client disconnected")
        sender_task.cancel()
    except Exception as e:
        print(f"Error: {e}")
        sender_task.cancel()
