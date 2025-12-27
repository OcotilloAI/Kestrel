import requests
import websocket
import threading
import time
import pytest
import json

# Configuration
API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

@pytest.fixture(scope="module")
def session():
    """Create a single session for the entire test module."""
    print("Setting up session...")
    res = requests.post(f"{API_URL}/session/create", json={"cwd": "."})
    res.raise_for_status()
    session_data = res.json()
    yield session_data
    print(f"Tearing down session {session_data['session_id']}...")
    requests.delete(f"{API_URL}/session/{session_data['session_id']}")

def test_text_message_is_received(session):
    """Verify that a simple text message sent over WebSocket is received and processed."""
    session_id = session['session_id']
    ws_url = f"{WS_URL}/ws/{session_id}"
    
    ws = websocket.WebSocket()
    ws.connect(ws_url)
    
    # Use a list to collect messages from the listener thread
    received_messages = []
    is_listening = threading.Event()
    is_listening.set()

    def on_message():
        while is_listening.is_set():
            try:
                msg = ws.recv()
                if isinstance(msg, bytes):
                    msg = msg.decode("utf-8", errors="ignore")
                if msg.startswith("{"):
                    try:
                        payload = json.loads(msg)
                        if payload.get("type") in {"assistant", "system", "detail"}:
                            received_messages.append(payload.get("content", ""))
                    except Exception:
                        pass
                elif msg.startswith("G: "):
                    received_messages.append(msg[3:])
            except websocket.WebSocketConnectionClosedException:
                break
            except Exception:
                break
    
    listener_thread = threading.Thread(target=on_message, daemon=True)
    listener_thread.start()
    
    # Send a simple command that should elicit a direct text response
    test_message = "Hello, can you hear me?"
    ws.send(test_message)
    
    # Wait for a response - models can be slow to start up
    time.sleep(30) 
    
    # Stop listening and clean up
    is_listening.clear()
    ws.close()
    listener_thread.join(timeout=2)

    # Assertions
    full_response = "".join(received_messages).lower()
    # Verify we received a meaningful response (models vary in greeting style)
    assert len(full_response.strip()) > 20
    assert "assist" in full_response or "help" in full_response or "today" in full_response
