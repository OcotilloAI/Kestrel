# Kestrel

A voice-first interface for software development. Robert drives long distances and wants to code by talking.

The FastAPI server (`src/server.py`, :8000, WebSocket `/ws/<session>`) runs a manager/coder LLM + tool loop (`src/manager_agent.py`, `coder_agent.py`, `agent_tools.py`). It talks to any OpenAI-compatible backend: `LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_URL`, by default the `llama-cpp` compose service on :8080. Goose has been removed.

Input:
- browser STT, or
- server-side Whisper via `POST /session/{id}/audio` and `/audio/execute` (FasterWhisper; `WHISPER_MODEL`, default `base.en`), or
- WebRTC streaming through `src/voice_bridge/`.

Output: the UI (`ui/web`, React + Vite) shows everything, and speech carries only the final summary and clarifying questions. Sessions are captured as structured events and Markdown notes (`docs/SESSION_CAPTURE.md`).

**Status:** last worked on in January 2026. `https://oscar.wampus-duck.ts.net` currently serves OpenClaw, not Kestrel, so run Kestrel locally when testing. Canonical docs: `ARCHITECTURE.md` (target state), `OVERVIEW_OF_KESTREL_GOALS.md`, `KESTREL_INTERFACE_NOTES.md` (speech filtering), `PLAN.md` (phases and backlog), `TESTING.md`. Tasks are GitHub Issues (OcotilloAI/Kestrel).

## Rules
- **Builds, tests and services run in containers.** Use `docker compose up -d --build kestrel`, adding `--no-deps` to leave llama-cpp alone. Use the `builder` service (`scripts/run_in_builder.sh <cmd>`) for integration tests that need sidecars.
- **Tests exercise the live service** at `BASE_URL` (local `http://localhost:8000`) against the real local model, not mocks. `scripts/run_ui_e2e.sh [BASE_URL]` runs the Playwright suite in `ui/web/tests/e2e`; pytest runs via `./.venv/bin/pytest`. Tests clean up the sessions and projects they create.
- **No timeout-based assertions.** No `time.sleep` followed by an assert, no deadline polling loops, no `waitForTimeout`. Wait for terminal events (WS `summary` or `error`, an HTTP response, a close) using `threading.Event` or `queue.Queue`. A failure should report the events received and the one expected. Long LLM work reports progress rather than timing out.
- **LLM work goes through the LLM.** Summaries and extraction are done by a model, not heuristics. Follow the model card's native tool-call format rather than forcing JSON.
- **Keep features you weren't asked to remove.** Typing and speaking both stay available.
- **Git:** commit locally and squash per issue. Push only when the issue is done or Robert asks. Close issues only after verification.

## Concepts
Projects get adjective-noun names (no UUIDs). A branch is a session (`workspace/<project>/<branch>`), and main is merge-only. The UI is paged (one prompt per page, back and forward) and uses an iOS-style sidebar (overlay on phones). Barge-in (typing or speaking) stops TTS. Speech is buffered into whole sentences.
