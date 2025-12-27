# Testing Guide

## UI End-to-End (Playwright)

From repo root:
- `scripts/run_ui_e2e.sh`

Target a different base URL:
- `BASE_URL=https://oscar.wampus-duck.ts.net scripts/run_ui_e2e.sh`
- `scripts/run_ui_e2e.sh https://oscar.wampus-duck.ts.net`

Notes:
- The server must be running and reachable at `BASE_URL`.
- The tests live in `ui/web/tests/e2e`.

## Manual UI Smoke Check

- Local: `http://localhost:8000`
- Remote: `https://oscar.wampus-duck.ts.net`
