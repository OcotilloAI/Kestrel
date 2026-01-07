import json
import os
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Set
from urllib.parse import urlparse

import websocket


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def ws_base_url() -> str:
    parsed = urlparse(BASE_URL)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.netloc or parsed.path
    return f"{scheme}://{host}"


@dataclass
class TestResult:
    """Result from waiting for task completion."""
    completed: bool
    success: bool
    events: List[dict] = field(default_factory=list)
    error: Optional[str] = None

    def events_by_type(self, event_type: str) -> List[dict]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.get("type") == event_type]

    def has_event_type(self, event_type: str) -> bool:
        """Check if any event of the given type was received."""
        return any(e.get("type") == event_type for e in self.events)


class EventCollector:
    """Collects WebSocket events with state-based completion detection.

    Instead of polling with timeouts, this class waits for terminal events
    (summary, error, or connection close) and provides diagnostic context
    when tests fail.

    Usage:
        ws = websocket.WebSocket()
        ws.connect(url)
        collector = EventCollector(ws)

        ws.send("some prompt")
        result = collector.wait_for_completion()

        assert result.completed, f"Task did not complete: {result.error}"
        assert result.success, f"Task failed: {result.events}"

        collector.close()
    """

    # Default terminal event types that signal task completion
    DEFAULT_TERMINAL_EVENTS: Set[str] = {"summary", "error"}

    def __init__(
        self,
        ws: websocket.WebSocket,
        terminal_events: Optional[Set[str]] = None,
    ):
        self.ws = ws
        self.terminal_events = terminal_events or self.DEFAULT_TERMINAL_EVENTS
        self.events: List[dict] = []
        self._terminal_received = threading.Event()
        self._any_event_received = threading.Event()
        self._error: Optional[str] = None
        self._running = True
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        """Background thread that receives WebSocket messages."""
        while self._running:
            try:
                msg = self.ws.recv()
                if isinstance(msg, bytes):
                    msg = msg.decode("utf-8", errors="ignore")
                if not msg or not msg.startswith("{"):
                    continue

                event = json.loads(msg)
                with self._lock:
                    self.events.append(event)
                    self._any_event_received.set()

                    # Check for terminal events
                    event_type = event.get("type", "")
                    if event_type in self.terminal_events:
                        self._terminal_received.set()

            except websocket.WebSocketConnectionClosedException:
                # Connection closed - this is a terminal condition
                self._terminal_received.set()
                break
            except json.JSONDecodeError:
                # Skip malformed JSON
                continue
            except Exception as e:
                with self._lock:
                    self._error = f"Listener error: {e}"
                self._terminal_received.set()
                break

    def wait_for_completion(self, timeout: float = 300) -> TestResult:
        """Wait for task completion with diagnostic context on failure.

        Args:
            timeout: Maximum seconds to wait for a terminal event.
                    This is a safety limit, not the expected wait time.

        Returns:
            TestResult with completion status and all received events.
        """
        completed = self._terminal_received.wait(timeout=timeout)
        self._running = False

        with self._lock:
            events_copy = list(self.events)
            error = self._error

        if not completed:
            event_types = [e.get("type") for e in events_copy]
            return TestResult(
                completed=False,
                success=False,
                events=events_copy,
                error=(
                    f"No terminal event received within {timeout}s. "
                    f"Received {len(events_copy)} events with types: {event_types}. "
                    f"Expected one of: {self.terminal_events}"
                ),
            )

        # Determine success based on events received
        has_summary = any(e.get("type") == "summary" for e in events_copy)
        has_error = any(e.get("type") == "error" for e in events_copy)

        return TestResult(
            completed=True,
            success=has_summary and not has_error,
            events=events_copy,
            error=error,
        )

    def wait_for_event(
        self,
        event_type: str,
        timeout: float = 60,
    ) -> Optional[dict]:
        """Wait for a specific event type.

        Args:
            event_type: The event type to wait for (e.g., "plan", "assistant")
            timeout: Maximum seconds to wait

        Returns:
            The first matching event, or None if timeout reached.
        """
        deadline = threading.Event()

        def check_events():
            while not deadline.is_set():
                with self._lock:
                    for event in self.events:
                        if event.get("type") == event_type:
                            return event
                # Small sleep to avoid busy waiting
                deadline.wait(0.1)
            return None

        # Use a thread to check with timeout
        result = [None]

        def checker():
            result[0] = check_events()

        checker_thread = threading.Thread(target=checker, daemon=True)
        checker_thread.start()
        checker_thread.join(timeout=timeout)
        deadline.set()

        return result[0]

    def wait_for_any_event(self, timeout: float = 30) -> bool:
        """Wait for any event to be received.

        Useful for verifying the server is responding at all.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if at least one event was received, False otherwise.
        """
        return self._any_event_received.wait(timeout=timeout)

    def get_events(self) -> List[dict]:
        """Get a copy of all received events."""
        with self._lock:
            return list(self.events)

    def close(self):
        """Stop listening and close the WebSocket."""
        self._running = False
        try:
            self.ws.close()
        except Exception:
            pass
        self._thread.join(timeout=2)
