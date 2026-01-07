"""Golden task tests - verify end-to-end task execution with real LLM.

These tests use the EventCollector for state-based waiting instead of
arbitrary timeouts. They wait for terminal events (summary, error) rather
than polling with deadlines.
"""
import os

import pytest
import requests
import websocket

from conftest import BASE_URL, ws_base_url, EventCollector


def _project_from_cwd(cwd: str | None) -> str | None:
    """Extract project name from working directory path."""
    if not cwd:
        return None
    normalized = cwd.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    if "workspace" in parts:
        idx = parts.index("workspace")
        if len(parts) > idx + 1:
            return parts[idx + 1]
    if len(parts) >= 2:
        return parts[-2]
    return None


def _run_task(prompt: str) -> None:
    """Execute a golden task and verify completion.

    Uses EventCollector for state-based waiting. The test succeeds if:
    1. A terminal event (summary) is received
    2. The summary indicates task completion

    The test fails with diagnostic context if:
    - No terminal event is received (with list of events that were received)
    - An error event is received
    - Connection closes unexpectedly
    """
    # Create session
    res = requests.post(f"{BASE_URL}/session/create", json={"cwd": "."})
    res.raise_for_status()
    payload = res.json()
    session_id = payload["session_id"]
    project_name = _project_from_cwd(payload.get("cwd"))

    # Connect WebSocket
    ws = websocket.WebSocket()
    ws.connect(f"{ws_base_url()}/ws/{session_id}")

    # Create event collector - waits for "summary" or "error" events
    collector = EventCollector(ws)

    try:
        # Send the task prompt
        ws.send(prompt)

        # Wait for task completion (terminal event)
        # Golden tasks with real LLM can take several minutes per task
        result = collector.wait_for_completion(timeout=600)

        # Assertion with full diagnostic context
        assert result.completed, (
            f"Task did not complete. {result.error}\n"
            f"Events received: {[e.get('type') for e in result.events]}"
        )

        # Verify we got a summary (success indicator)
        assert result.has_event_type("summary"), (
            f"No summary event received.\n"
            f"Events: {[e.get('type') for e in result.events]}"
        )

        # Check summary content format
        summaries = result.events_by_type("summary")
        if summaries:
            final_summary = summaries[-1].get("content", "").lower()
            # New format: "Completed X/Y tasks for: <intent>"
            # Or legacy format with "I did", "I learned", "Next"
            has_new_format = "completed" in final_summary and "task" in final_summary
            has_legacy_format = "i did" in final_summary or "i learned" in final_summary
            assert has_new_format or has_legacy_format, (
                f"Summary format unexpected: {final_summary}"
            )

    finally:
        # Cleanup
        collector.close()
        requests.delete(f"{BASE_URL}/session/{session_id}")
        if project_name:
            requests.delete(f"{BASE_URL}/project/{project_name}")


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
    """Test that golden tasks complete successfully with the real LLM."""
    _run_task(prompt)
