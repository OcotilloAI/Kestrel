# Session Capture Architecture

> Capture everything, surface what matters, enable future RAG.

## Overview

Kestrel sessions produce multiple data streams that need capture for:
1. **Review** - Human inspection of what happened
2. **Replay** - Resume sessions with context
3. **RAG** - Semantic retrieval of past decisions, code, and conversations
4. **Debugging** - Full execution traces when things go wrong

## Storage Strategy

### Primary: JSONL Transcripts
Location: `{project_root}/.kestrel/{branch}.jsonl`

JSONL provides:
- Append-only (crash-safe)
- Streamable (tail -f)
- Greppable
- Easy to parse/transform

### Secondary: Markdown Session Notes
Location: `{project_root}/.kestrel/notes/{branch}/{date}.md`

Markdown provides:
- Human-readable summaries
- Obsidian-compatible (backlinks, mindmaps)
- Natural chunking for RAG
- Skimmable decision log

## Event Schema (JSONL)

```jsonc
{
  // Required fields
  "ts": "2026-01-08T00:46:00.000Z",   // ISO 8601 timestamp
  "type": "stt_raw | user_intent | agent_stream | tool_call | tool_result | summary | system",
  "source": "whisper | browser_stt | controller | coder | summarizer | system",
  
  // Content (base64 for binary-safe storage)
  "body_b64": "<base64-encoded content>",
  
  // Type-specific metadata
  "meta": { /* varies by type */ }
}
```

### Event Types

#### `stt_raw` - Raw Speech-to-Text Output
Captures exactly what the STT engine produced.

```jsonc
{
  "type": "stt_raw",
  "source": "whisper",        // or "browser_stt"
  "body_b64": "<transcript>",
  "meta": {
    "audio_duration_ms": 4200,
    "model": "whisper-large-v3",
    "language": "en",
    "confidence": 0.94,
    "word_timestamps": [       // Optional, if available
      {"word": "create", "start": 0.0, "end": 0.3},
      {"word": "a", "start": 0.3, "end": 0.4}
    ]
  }
}
```

#### `user_intent` - Interpreted User Request
What we understood the user to mean (may differ from raw transcript).

```jsonc
{
  "type": "user_intent",
  "source": "controller",
  "body_b64": "<normalized request>",
  "meta": {
    "original_stt_ts": "2026-01-08T00:46:00.000Z",  // Links to stt_raw
    "clarification_needed": false,
    "inferred_context": ["project:kestrel", "branch:main"]
  }
}
```

#### `agent_stream` - Code Agent Execution Stream
Full stdout/stderr from the backend coding agent.

```jsonc
{
  "type": "agent_stream",
  "source": "claude-code",    // or "codex", "gemini", etc.
  "body_b64": "<raw output chunk>",
  "meta": {
    "stream": "stdout",       // or "stderr"
    "task_id": "task_abc123",
    "chunk_seq": 42,          // For ordering
    "tokens_used": 150        // If available
  }
}
```

#### `tool_call` - Tool Invocation Request
```jsonc
{
  "type": "tool_call",
  "source": "coder",
  "body_b64": "<tool arguments JSON>",
  "meta": {
    "tool_name": "write_file",
    "call_id": "call_xyz789",
    "task_id": "task_abc123"
  }
}
```

#### `tool_result` - Tool Execution Result
```jsonc
{
  "type": "tool_result",
  "source": "tool_runner",
  "body_b64": "<tool output>",
  "meta": {
    "tool_name": "write_file",
    "call_id": "call_xyz789",
    "success": true,
    "duration_ms": 45
  }
}
```

#### `summary` - End-of-Task Summary
What gets spoken to the user.

```jsonc
{
  "type": "summary",
  "source": "summarizer",
  "body_b64": "<spoken summary text>",
  "meta": {
    "format": "i_did_i_learned_next",
    "task_id": "task_abc123",
    "files_changed": ["src/server.py", "tests/test_server.py"],
    "tts_voice": "nova"       // If TTS was used
  }
}
```

#### `system` - System Events
Session lifecycle, errors, configuration changes.

```jsonc
{
  "type": "system",
  "source": "session_manager",
  "body_b64": "<message>",
  "meta": {
    "event": "session_created | session_resumed | error | config_change",
    "severity": "info | warn | error"
  }
}
```

## Markdown Session Notes

Generated alongside JSONL for human consumption. One file per day per branch.

### Format

```markdown
# Session: feature-branch
## 2026-01-08

### 10:30 - "Add user authentication"

**User said:** "Add login with Google OAuth"

**Plan:**
1. Install oauth library
2. Create auth routes
3. Add session middleware
4. Update user model

**What I did:**
- Created `src/auth/google.py` with OAuth flow
- Added `/auth/google` and `/auth/callback` routes
- Updated User model with `google_id` field

**Files changed:**
- `src/auth/google.py` (new)
- `src/routes/auth.py` (modified)
- `src/models/user.py` (modified)

**Next:** Add session persistence

---

### 11:15 - "The callback is failing"

**User said:** "It's giving me a 500 error on callback"

**What I found:**
- Missing `GOOGLE_CLIENT_SECRET` env var
- Exception in token exchange

**Fixed:** Added env var check with helpful error message

---
```

### Generation Rules

1. New H3 section for each user interaction
2. Include: raw request, plan (if any), changes, outcome
3. Link files using Obsidian `[[filename]]` syntax when useful
4. Keep summaries concise but complete
5. Append, never overwrite (crash-safe)

## File Organization

```
project/
├── .kestrel/
│   ├── main.jsonl                    # JSONL transcript for main branch
│   ├── feature-auth.jsonl            # JSONL transcript for feature branch
│   └── notes/
│       ├── main/
│       │   ├── 2026-01-07.md
│       │   └── 2026-01-08.md
│       └── feature-auth/
│           └── 2026-01-08.md
├── src/
└── ...
```

## Implementation Notes

### Append Safety
- All writes are append-only with `\n` terminators
- Use file locking or atomic append where available
- On crash recovery, last incomplete line can be discarded

### Streaming Agent Output
For long-running agent tasks:
1. Buffer agent_stream events (e.g., every 1KB or 500ms)
2. Flush on task completion
3. Mark chunks with sequence numbers for reconstruction

### Markdown Generation
Options:
1. **Real-time:** Generate markdown as events occur (more complex)
2. **Post-hoc:** Generate from JSONL after each interaction (simpler, recommended)
3. **On-demand:** Generate when user requests session export

Recommend: Post-hoc generation triggered on `summary` event.

### RAG Preparation

The JSONL format is designed for future vector DB migration:

```python
# Chunking strategy for RAG
def chunk_for_rag(events):
    chunks = []
    for event in events:
        if event["type"] == "summary":
            # Summaries are natural chunks
            chunks.append({
                "text": decode(event["body_b64"]),
                "metadata": {
                    "type": "summary",
                    "ts": event["ts"],
                    "files": event["meta"].get("files_changed", [])
                }
            })
        elif event["type"] == "user_intent":
            # User intents for retrieval
            chunks.append({
                "text": decode(event["body_b64"]),
                "metadata": {
                    "type": "user_request",
                    "ts": event["ts"]
                }
            })
    return chunks
```

## Migration from Current Format

Current format uses:
- `role`, `source`, `type`, `body_b64`, `timestamp`

New format adds:
- Consistent `ts` field (ISO 8601)
- Richer `meta` object
- New event types (`stt_raw`, `user_intent`, `agent_stream`)

Migration path:
1. Add new event types alongside existing
2. Backfill `ts` from `timestamp` if present
3. Existing events continue to work (backward compatible)

## Open Questions

1. **Audio archival:** Store raw audio files alongside transcripts?
   - Pro: Can re-transcribe with better models later
   - Con: Storage cost, privacy concerns
   
2. **Retention policy:** How long to keep detailed streams?
   - Proposal: Keep summaries forever, prune agent_stream after 30 days

3. **Cross-project context:** Should RAG span multiple projects?
   - Proposal: Default to project-scoped, opt-in to global
