# Kestrel Backlog Plan

## RAG & Vector DB

### Phase 5: RAG Chunking Utility
**Goal:** Transform JSONL transcripts into embeddable chunks for semantic search.

**Tasks:**
1. Create `src/rag_chunker.py` with chunking strategies:
   - **Summary chunks:** Each summary event = 1 chunk (natural boundaries)
   - **User intent chunks:** Each user request = 1 chunk
   - **Tool result chunks:** Significant tool outputs (file contents, shell output)
   
2. Chunk format:
   ```python
   {
       "text": "chunk content for embedding",
       "metadata": {
           "session_id": "...",
           "task_id": "...",
           "type": "summary|user_intent|tool_result",
           "ts": "2026-01-08T...",
           "files": ["file1.py", ...],  # if applicable
           "project": "project_name",
           "branch": "branch_name",
       }
   }
   ```

3. Add CLI: `python -m rag_chunker process {session_id}` → outputs JSONL chunks

### Phase 6: Vector DB Export
**Goal:** Export chunks to vector database for retrieval.

**Options (in priority order):**
1. **ChromaDB (local)** - Zero config, embedded, good for dev
2. **Qdrant (local/cloud)** - More features, still simple
3. **Pinecone (cloud)** - Managed, but requires account

**Tasks:**
1. Create `src/vector_store.py` with pluggable backends
2. Embedding via OpenAI `text-embedding-3-small` or local alternative
3. Add endpoints:
   - `POST /session/{id}/index` - Index session chunks
   - `GET /rag/search?q=...` - Semantic search across sessions
4. Integration with controller agent for context retrieval

---

## Retention & Archival

### Phase 7: Retention Policy
**Goal:** Manage storage growth while preserving important context.

**Policy tiers:**
| Data Type | Hot (full) | Warm (summary) | Cold (delete) |
|-----------|------------|----------------|---------------|
| Summaries | Forever | Forever | Never |
| User intents | 90 days | Forever | Never |
| Tool calls | 30 days | 90 days | 1 year |
| Tool results | 7 days | 30 days | 90 days |
| Agent stream | 7 days | 30 days | 90 days |
| STT raw | 3 days | 30 days | 90 days |

**Tasks:**
1. Add `src/retention.py` with pruning logic
2. CLI: `python -m retention prune --dry-run`
3. Cron job for automated pruning
4. Archive to compressed JSONL before delete

---

## Streaming Audio

### Phase 8: WebSocket Audio Streaming
**Goal:** Real-time voice interaction without file uploads.

**Architecture:**
```
Browser/Client
     │
     │ WebSocket: binary audio chunks (16kHz PCM)
     ▼
Kestrel Server
     │
     │ Buffer + VAD (Voice Activity Detection)
     ▼
Whisper STT
     │
     │ Transcript
     ▼
Task Execution
     │
     │ Response
     ▼
TTS (optional)
     │
     │ Audio chunks back
     ▼
Client playback
```

**Tasks:**
1. Add WebSocket endpoint: `ws://host/session/{id}/audio-stream`
2. Implement chunked audio buffering
3. VAD for utterance detection (when user stops speaking)
4. Streaming transcription (as words are recognized)
5. Optional TTS response streaming

**Complexity:** High - defer unless real-time is critical

---

## Timeline Estimate

| Phase | Effort | Priority |
|-------|--------|----------|
| 5: RAG Chunking | 2-3 hours | High |
| 6: Vector DB | 4-6 hours | High |
| 7: Retention | 2-3 hours | Medium |
| 8: Streaming | 8-12 hours | Low (defer) |

Recommend: Do 5 & 6 together, then 7. Save 8 for when file-upload audio feels limiting.
