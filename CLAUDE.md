# Claude Notes

## Testing Quickstart

UI end-to-end tests (Playwright, headless):
- `scripts/run_ui_e2e.sh`
- Optional target override: `BASE_URL=https://oscar.wampus-duck.ts.net scripts/run_ui_e2e.sh`
- Or pass as an argument: `scripts/run_ui_e2e.sh https://oscar.wampus-duck.ts.net`

Manual UI check:
- `http://localhost:8000` (local)
- `https://oscar.wampus-duck.ts.net` (remote)

## Test Development Rules

### No Timeout-Based Assertions

Tests must NOT use arbitrary timeouts as success/failure criteria:

**Prohibited patterns:**
- `time.sleep(N)` followed by assertions
- `while time.time() < deadline` polling loops that return False on timeout
- `waitForTimeout()` in Playwright tests as a synchronization mechanism

**Why:** Timeout-based tests are flaky and provide no diagnostic information when they fail.

### State-Based Waiting

Tests MUST wait for explicit terminal events:

**Acceptable patterns:**
- Wait for WebSocket message with `type: "summary"` or `type: "error"`
- Wait for HTTP response (success or error status)
- Wait for connection close event
- Use `threading.Event` or `queue.Queue` with timeout that fails with context

**Example - Bad:**
```python
time.sleep(30)
assert len(messages) > 0  # No idea if server is slow or broken
```

**Example - Good:**
```python
result = event_collector.wait_for_completion()
assert result.completed, f"Task did not complete: {result.events}"
```

### Error Context Required

When a test fails, it must provide actionable context:
- What events were received before failure
- What event was expected
- Connection state at failure time

### Test Independence

Each test must:
- Create its own session/resources
- Clean up after itself
- Not depend on timing of other tests
