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

## Builder Container (Local Builds/Integration Tests)

Start the builder service:
- `docker compose up -d builder`

Open a shell inside the builder:
- `docker compose exec builder bash`

Notes:
- The builder shares `/workspace` and the host Docker socket.
- Use it to run project builds/tests or spin up databases with `docker run`/`docker compose`.

## Scenario Test: Web App + Postgres + Vector Embeddings

Example flow to validate DB + vector stack:
- Start services (example Postgres + pgvector):
  - `docker compose exec builder bash -lc "docker run --name kestrel-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d ankane/pgvector"`
- Build a sample app in a workspace project folder.
- Run integration tests from the builder container.
- Stop the service when done:
  - `docker compose exec builder bash -lc "docker rm -f kestrel-pg"`

Automated pgvector smoke test:
- `scripts/test_builder_pgvector.sh`
