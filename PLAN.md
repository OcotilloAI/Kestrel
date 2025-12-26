# Kestrel Plan

## Goals
- Improve session lifecycle stability (create/clone/delete, active session switching).
- Stabilize UI behavior across iOS phone, iOS tablet, and Mac Safari/Chrome.
- Reduce crash risk with better error handling and logging.

## Current Focus (Stability)
- Fix clone fallback crash when source is not a git repo. (Issue #51)
- Stop WebSocket reconnect loops after a session is deleted. (Issue #54)
- Track and surface session creation/delete failures without crashing the server.

## Session Lifecycle and Git Hygiene
- Implement branch/project deletion with on-disk cleanup and confirmations. (Issue #52)
- Decide and implement merge/delete semantics for branch repos (backlog; see Issue #41).
- Guard against name collisions when creating branch folders and projects.

## Device UX (iOS phone, iOS tablet, MacOS host)
- Implement dynamic viewport handling and safe-area insets. (Issue #53)
- Verify keyboard behavior and input visibility on iOS Safari.
- Validate sidebar behavior and content density on iPad and Mac. (Issues #44, #45, #50)

## Observability and Tests
- Add structured logs around session create/clone/delete and WS lifecycle.
- Add a simple regression test to reproduce session create/delete crash.

## Issue Map
- Existing: #2, #3, #37, #39, #40, #41, #42, #43, #44, #45, #46, #47, #48, #49, #50
- New: #51 (clone fallback crash), #52 (branch/project deletion), #53 (iOS/iPadOS viewport), #54 (WS reconnect loop), #55 (summarizer end-of-task recap)
