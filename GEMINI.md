# Gemini Interaction Guidelines

## Core Principles
1. **Context Awareness**: Always verify the current state of the system (files, running processes, configuration) before acting.
2. **Safety First**: Explain critical commands before execution, especially those modifying the system outside the project scope.
3. **Iterative Improvement**: Fix immediate blockers, then plan for architectural improvements.
4. **Documentation**: Use GitHub Issues to track progress and `GEMINI.md` (this file) to capture operational rules.

## Verification Mandates
1.  **End-to-End Validation**: Before claiming success, thoroughly test both the UI and API endpoints to ensure full functionality.
2.  **Semantic Correctness**: Crucially, verify that all responses (especially summarized content) are meaningful, coherent, and free from corruption.
3.  **Automated Testing**: Use the Playwright UI e2e harness for regressions and expand API tests alongside fixes.

## Issue Tracking Workflow
1. **Identify**: Clearly state the problem or feature request.
2. **Log**: Create a new issue in the GitHub repository using `gh issue create`.
3. **Resolve**: Implement the fix.
4. **Close**: Close the GitHub issue using `gh issue close`.

## Testing Strategy
1.  **Backend Verification:** Core backend functionality (API endpoints, session management, agent capabilities) will be verified by a growing suite of Python test scripts located in the `tests/` directory.
2.  **Test-Driven Development:** New features or bug fixes must be accompanied by a corresponding test case that validates the change and protects against future regressions.
3.  **Frontend Verification:** UI features should be validated with the Playwright e2e suite, plus a quick manual smoke test.
4.  **Execution:** Use `scripts/run_ui_e2e.sh` (optionally with `BASE_URL=...` or a positional URL) for UI e2e tests.

## Technical Context
- **Project**: Kestrel (FastAPI + Goose integration)
- **Environment**: Linux (Container/Dev Environment)
- **Goose Configuration**: Located at `~/.config/goose/config.yaml`. Requires `developer` extension for system access.
