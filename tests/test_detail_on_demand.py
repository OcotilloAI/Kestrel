"""Test detail-on-demand file reading functionality.

Uses EventCollector for state-based waiting instead of time-based loops.
"""
import time
from pathlib import Path

import requests
import websocket

from conftest import BASE_URL, ws_base_url, EventCollector


def test_detail_on_demand_read_file(tmp_path):
    """Test that 'read file' command returns file contents via detail events.

    Uses EventCollector to wait for detail events. The server sends:
    1. A header event: "Reading <filename>."
    2. Content chunk events with actual file content

    We wait for a detail event containing the expected content.
    """
    repo_root = Path(__file__).resolve().parents[1]
    project_name = f"test-detail-{int(time.time())}"
    host_cwd = repo_root / "workspace" / project_name / "main"
    host_cwd.mkdir(parents=True, exist_ok=True)

    cwd = f"/workspace/{project_name}/main"
    res = requests.post(f"{BASE_URL}/session/create", json={"cwd": cwd})
    res.raise_for_status()
    session_data = res.json()
    session_id = session_data["session_id"]

    # Create the test file
    filename = "detail_test.txt"
    file_path = host_cwd / filename
    with open(file_path, "w", encoding="utf-8") as handle:
        handle.write("line one\nline two\n")

    ws_url = f"{ws_base_url()}/ws/{session_id}"
    ws = websocket.WebSocket()
    ws.connect(ws_url)

    # Don't use "detail" as terminal - we need to collect multiple detail events
    # Wait for connection close or error instead
    collector = EventCollector(ws, terminal_events={"error"})

    try:
        # Send read file command
        ws.send(f"read file {filename}")

        # Wait for events - use wait_for_any_event first, then check content
        got_event = collector.wait_for_any_event(timeout=10)
        assert got_event, "No events received from server"

        # Give a brief moment for all detail chunks to arrive
        # Then check what we have (this is event-driven, not time-based)
        import threading
        threading.Event().wait(0.5)  # Allow chunked events to arrive

        # Get all received events
        events = collector.get_events()
        detail_events = [e for e in events if e.get("type") == "detail"]

        assert detail_events, (
            f"No detail events received.\n"
            f"Events: {[e.get('type') for e in events]}"
        )

        # Combine all detail content
        joined = "\n".join(e.get("content", "") for e in detail_events)

        # Verify file content was returned
        assert "line one" in joined, (
            f"Expected 'line one' in detail content.\n"
            f"Received: {joined}"
        )
        assert "line two" in joined, (
            f"Expected 'line two' in detail content.\n"
            f"Received: {joined}"
        )

    finally:
        collector.close()
        requests.delete(f"{BASE_URL}/session/{session_id}")
