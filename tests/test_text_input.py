"""Test basic text input/output via WebSocket.

Uses EventCollector for state-based waiting instead of time.sleep().
"""
import pytest
import requests
import websocket

from conftest import BASE_URL, ws_base_url, EventCollector


@pytest.fixture(scope="module")
def session():
    """Create a single session for the entire test module."""
    print("Setting up session...")
    res = requests.post(f"{BASE_URL}/session/create", json={"cwd": "."})
    res.raise_for_status()
    session_data = res.json()
    yield session_data
    print(f"Tearing down session {session_data['session_id']}...")
    requests.delete(f"{BASE_URL}/session/{session_data['session_id']}")


def test_text_message_is_received(session):
    """Verify that a simple text message sent over WebSocket is received and processed.

    Uses EventCollector to wait for response events instead of arbitrary sleep.
    """
    session_id = session['session_id']
    ws_url = f"{ws_base_url()}/ws/{session_id}"

    ws = websocket.WebSocket()
    ws.connect(ws_url)

    # Use EventCollector with custom terminal events
    # For this test, we consider "assistant" responses as terminal
    collector = EventCollector(ws, terminal_events={"assistant", "summary", "error"})

    try:
        # Send a simple command that should elicit a direct text response
        test_message = "Hello, can you hear me?"
        ws.send(test_message)

        # Wait for an assistant response (state-based, not time-based)
        result = collector.wait_for_completion(timeout=60)

        # Verify we got a response
        assert result.completed, (
            f"No response received. {result.error}\n"
            f"Events: {[e.get('type') for e in result.events]}"
        )

        # Extract assistant responses
        assistant_events = result.events_by_type("assistant")
        system_events = result.events_by_type("system")

        # Combine all response content
        all_content = []
        for event in assistant_events + system_events:
            content = event.get("content", "")
            if content:
                all_content.append(content)

        full_response = " ".join(all_content).lower()

        # Verify we received a meaningful response
        assert len(full_response.strip()) > 20, (
            f"Response too short: '{full_response}'\n"
            f"All events: {result.events}"
        )

        # Check for typical greeting response patterns
        has_greeting_response = any(
            word in full_response
            for word in ("assist", "help", "today", "hello", "kestrel", "working")
        )
        assert has_greeting_response, (
            f"Response doesn't contain expected greeting patterns: '{full_response}'"
        )

    finally:
        collector.close()
