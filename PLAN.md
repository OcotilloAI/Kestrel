# Kestrel Plan

## Goals
- Improve session lifecycle stability (create/clone/delete, active session switching).
- Stabilize UI behavior across iOS phone, iOS tablet, and Mac Safari/Chrome.
- Reduce crash risk with better error handling and logging.
- **Enable full session capture for RAG and review** (new)

## Current Focus (Session Capture) ✓ COMPLETE

> See [docs/SESSION_CAPTURE.md](docs/SESSION_CAPTURE.md) for architecture.

### Phase 1: Enhanced Event Schema ✓
- [x] Add new event types: `stt_raw`, `user_intent`, `agent_stream`
- [x] Migrate `timestamp` → `ts` (ISO 8601)
- [x] Add `meta` object to all events
- [x] Update `record_event()` in session_manager.py
- [x] 7 typed recording methods: `record_stt_raw`, `record_user_intent`, `record_agent_stream`, `record_tool_call`, `record_tool_result`, `record_summary`, `record_system_event`

### Phase 2: Agent Stream Capture ✓
- [x] Capture tool calls with `tool_call` events
- [x] Capture tool results with `tool_result` events
- [x] Add task_id and call_id correlation across related events
- [x] Track execution time (duration_ms) for tool calls
- [x] Success/failure tracking

### Phase 3: Markdown Note Generation ✓
- [x] Generate daily markdown from JSONL post-hoc
- [x] Trigger on `summary` event
- [x] Include: user request, plan, changes, files, outcome
- [x] Obsidian-compatible format (`[[links]]` for code files)
- [x] Daily files at `{project}/.kestrel/notes/{branch}/{date}.md`

### Phase 4: Audio Input Pipeline ✓
- [x] Server-side Whisper integration (FasterWhisper)
- [x] Audio upload endpoint: `POST /session/{session_id}/audio`
- [x] Transcribe-and-execute endpoint: `POST /session/{session_id}/audio/execute`
- [x] STT → event capture flow (records `stt_raw` events)
- [x] Supports: wav, mp3, webm, ogg, flac, m4a

### Backlog
- [ ] RAG chunking utility
- [ ] Vector DB export
- [ ] Retention/pruning policy
- [ ] Audio archival (optional)
- [ ] Streaming audio via WebSocket

---

## Previous Focus (Stability)
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
