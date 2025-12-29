import json
import os
import threading
import time
from urllib.parse import urlparse

import pytest
import requests
import websocket


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _ws_url() -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.netloc or parsed.path
    return f"{scheme}://{host}"


def _await(predicate, timeout: float, interval: float = 0.1) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _run_task(prompt: str) -> None:
    res = requests.post(f"{BASE_URL}/session/create", json={"cwd": "."})
    res.raise_for_status()
    session_id = res.json()["session_id"]

    ws = websocket.WebSocket()
    ws.connect(f"{_ws_url()}/ws/{session_id}")

    summaries: list[str] = []
    saw_plan = {"value": False}
    listener_running = threading.Event()
    listener_running.set()

    def listen() -> None:
        while listener_running.is_set():
            try:
                msg = ws.recv()
                if isinstance(msg, bytes):
                    msg = msg.decode("utf-8", errors="ignore")
                if not isinstance(msg, str) or not msg.startswith("{"):
                    continue
                payload = json.loads(msg)
                if payload.get("type") == "assistant" and "Proposed plan" in payload.get("content", ""):
                    saw_plan["value"] = True
                if payload.get("type") == "summary":
                    summaries.append(payload.get("content", ""))
            except websocket.WebSocketConnectionClosedException:
                break
            except Exception:
                break

    listener_thread = threading.Thread(target=listen, daemon=True)
    listener_thread.start()

    ws.send(prompt)
    _await(lambda: saw_plan["value"], timeout=30)
    got_plan_summary = _await(lambda: bool(summaries), timeout=60)
    ws.send("yes")

    got_final_summary = _await(lambda: len(summaries) >= 2, timeout=180)
    listener_running.clear()
    ws.close()
    listener_thread.join(timeout=2)

    requests.delete(f"{BASE_URL}/session/{session_id}")

    assert got_plan_summary, "Expected a summary after the plan phase"
    assert got_final_summary, "Expected a summary after execution"
    plan_summary = summaries[0].lower()
    final_summary = summaries[-1].lower()
    assert "i did" in plan_summary and "i learned" in plan_summary and "next" in plan_summary
    assert "proceed" in plan_summary or "answer" in plan_summary
    assert "i did" in final_summary and "i learned" in final_summary and "next" in final_summary
    assert "proceed" in final_summary or "continue" in final_summary


@pytest.mark.parametrize(
    "prompt",
    [
        "Create a simple web app that displays Hello World in a browser. "
        "Use tools already installed and include a quick local test.",
        "Create a reactive web app with a counter that updates on button click. "
        "Keep it minimal and include a quick test.",
        "Create an app that stores items in a sqlite database and lists them. "
        "Include a quick test.",
        "Create an app that fetches a stock price history for a given date using Yahoo Finance. "
        "Include a quick test.",
    ],
)
def test_golden_task(prompt: str) -> None:
    _run_task(prompt)
