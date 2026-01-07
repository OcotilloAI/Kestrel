# Agent Instructions

## Workflow

- Do not push commits upstream unless the issue is complete or the user explicitly asks.
- Run tests after each change; ensure test suites clean up any projects they create.
- Limit clarifying questions to 3 per turn unless requirements are ambiguous enough to block execution.
- Use the builder container for builds/tests or services: `docker compose exec builder bash -lc "<command>"`.

## Kestrel Speech Interface

- See `KESTREL_INTERFACE_NOTES.md` for input/output filtering goals and tool enforcement.

## Testing Quickstart

UI end-to-end tests (Playwright, headless):
- `scripts/run_ui_e2e.sh`
- Optional target override: `BASE_URL=https://oscar.wampus-duck.ts.net scripts/run_ui_e2e.sh`
- Or pass as an argument: `scripts/run_ui_e2e.sh https://oscar.wampus-duck.ts.net`

Manual UI check:
- `http://localhost:8000` (local)
- `https://oscar.wampus-duck.ts.net` (remote)
