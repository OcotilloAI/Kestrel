# Gemini Interaction Guidelines

## Core Principles
1. **Context Awareness**: Always verify the current state of the system (files, running processes, configuration) before acting.
2. **Safety First**: Explain critical commands before execution, especially those modifying the system outside the project scope.
3. **Iterative Improvement**: Fix immediate blockers, then plan for architectural improvements.
4. **Documentation**: Use GitHub Issues to track progress and `GEMINI.md` (this file) to capture operational rules.

## Issue Tracking Workflow
1. **Identify**: Clearly state the problem or feature request.
2. **Log**: Create a new issue in the GitHub repository using `gh issue create`.
3. **Resolve**: Implement the fix.
4. **Close**: Close the GitHub issue using `gh issue close`.

## Testing Strategy
1.  **Backend Verification:** Core backend functionality (API endpoints, session management, agent capabilities) will be verified by a growing suite of Python test scripts located in the `tests/` directory.
2.  **Test-Driven Development:** New features or bug fixes must be accompanied by a corresponding test case that validates the change and protects against future regressions.
3.  **Frontend Verification:** UI features will be manually verified in the browser after each deployment. The goal is to incorporate automated end-to-end testing frameworks (e.g., Playwright, Selenium) in the future.
4.  **Execution:** The test suite can be run using a simple, standardized command.

## Technical Context
- **Project**: Kestrel (FastAPI + Goose integration)
- **Environment**: Linux (Container/Dev Environment)
- **Goose Configuration**: Located at `~/.config/goose/config.yaml`. Requires `developer` extension for system access.
