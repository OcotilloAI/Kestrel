import requests
import websocket
import threading
import time
import os
import json

# Configuration
API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

def verify_goose_app_creation():
    print("1. Creating Session...")
    try:
        res = requests.post(f"{API_URL}/session/create", json={"cwd": None})
        if res.status_code != 200:
            print(f"Failed to create session: {res.text}")
            return
        
        data = res.json()
        session_id = data["session_id"]
        cwd = data["cwd"]
        print(f"Session Created: {session_id} in {cwd}")
    except Exception as e:
        print(f"Error connecting to API: {e}")
        return

    # Connect WebSocket
    ws_url = f"{WS_URL}/ws/{session_id}"
    print(f"2. Connecting to WebSocket: {ws_url}")
    
    ws = websocket.WebSocket()
    try:
        ws.connect(ws_url)
    except Exception as e:
        print(f"WebSocket connection failed: {e}")
        return

    def on_message():
        while True:
            try:
                msg = ws.recv()
                if msg.startswith("G: "):
                    print(f"{msg[3:]}", end="", flush=True)
                else:
                    print(f"{msg}", end="", flush=True)
            except:
                break

    # Start listener
    t = threading.Thread(target=on_message)
    t.daemon = True
    t.start()

    # Send command
    command = (
        "Build a simple python web service (using http.server or flask if available, "
        "but prefer standard library) that responds with 'Hello World'. "
        "Write the code to a file named 'app.py'. "
        "Then, run this app in the background and use 'curl' to test it locally on port 8080. "
        "You are running in a container so you can't easily spawn another container. "
        "Just run it, test it, and show me the output."
    )
    print(f"\n3. Sending command: {command}")
    ws.send(command)

    # Wait for execution (give it plenty of time to write code, run it, and test it)
    print("\nWaiting for execution (120s)...")
    time.sleep(120)

    ws.close()

if __name__ == "__main__":
    verify_goose_app_creation()
