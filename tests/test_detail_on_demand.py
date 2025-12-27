import json
import time
from pathlib import Path
import requests
import websocket

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


def test_detail_on_demand_read_file(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    project_name = f"test-detail-{int(time.time())}"
    host_cwd = repo_root / "workspace" / project_name / "main"
    host_cwd.mkdir(parents=True, exist_ok=True)

    cwd = f"/workspace/{project_name}/main"
    res = requests.post(f"{API_URL}/session/create", json={"cwd": cwd})
    res.raise_for_status()
    session_data = res.json()
    session_id = session_data["session_id"]

    filename = "detail_test.txt"
    file_path = host_cwd / filename
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
            if isinstance(msg, bytes):
                msg = msg.decode("utf-8", errors="ignore")
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
