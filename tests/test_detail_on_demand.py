import json
import time
import requests
import websocket

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


def test_detail_on_demand_read_file(tmp_path):
    res = requests.post(f"{API_URL}/session/create", json={"cwd": "."})
    res.raise_for_status()
    session_data = res.json()
    session_id = session_data["session_id"]
    cwd = session_data["cwd"]

    filename = "detail_test.txt"
    file_path = f"{cwd}/{filename}"
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write("line one\nline two\n")

    ws_url = f"{WS_URL}/ws/{session_id}"
    ws = websocket.WebSocket()
    ws.connect(ws_url)

    received = []
    start = time.time()
    ws.send(f"read file {filename}")

    while time.time() - start < 10:
        try:
            msg = ws.recv()
            if msg.startswith("{"):
                payload = json.loads(msg)
                if payload.get("type") == "detail":
                    received.append(payload.get("content", ""))
                    if "line two" in payload.get("content", ""):
                        break
        except Exception:
            break

    ws.close()
    requests.delete(f"{API_URL}/session/{session_id}")

    joined = "\n".join(received)
    assert "line one" in joined
    assert "line two" in joined
