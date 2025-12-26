# Kestrel Development Plan

**Goal:** Create a modern, web-based voice interface for the Goose agent that runs on various backends (Linux, Mac, Windows) and supports client-side audio processing (iOS, Android, Browser).

## Current Status
- [x] Project Initialization (License, Contributing, Git)
- [x] Backend Refactor (FastAPI)
- [x] Frontend Implementation (Web Speech API)
- [x] Session & Context Management

## Roadmap

### Phase 1: Foundation & Backend
- **Objective:** Remove audio dependencies from the Python backend and expose Goose via a WebSocket API.
- **Tasks:**
    - [x] Create `src/server.py` using FastAPI.
    - [x] Implement WebSocket endpoint `/ws` for bi-directional text streaming.
    - [x] Update `GooseWrapper` to be robust and async-friendly if needed.
    - [x] Update dependency management (remove `pydub`, `sounddevice`, add `fastapi`, `uvicorn`, `websockets`).

### Phase 2: Web Frontend (MVP)
- **Objective:** A functional web interface for chatting with Goose using voice.
- **Tasks:**
    - [x] Create `static/index.html` (Legacy).
    - [x] Refactor Frontend to React + TypeScript + Vite.
    - [x] Implement STT using `window.SpeechRecognition`.
    - [x] Implement TTS using `window.speechSynthesis`.
    - [x] Build Chat UI:
        - [x] Message history (scrolling).
        - [x] Real-time input preview (non-scrolling).
        - [x] System status indicator (Connecting, Thinking, etc.).

### Phase 3: Session Management & Advanced Features
- **Objective:** Manage multiple independent sessions and contexts.
- **Tasks:**
    - [x] Add session ID handling in Backend.
    - [x] Add UI sidebar for session switching.
    - [x] Support switching "working directories" or git contexts via UI.

## Active Issues & Backlog
- **[Issue #1](https://github.com/OcotilloAI/Kestrel/issues/1): Integration Test Timeout**
    - *Problem:* `test_basic.py` times out because the local `qwen3-coder:30b` model is too slow.
    - *Status:* Closed.

- **[Issue #2](https://github.com/OcotilloAI/Kestrel/issues/2): Concurrent Session Support**
    - *Problem:* Backend currently uses a single global `GooseWrapper`. All users share the same session/CWD.
    - *Goal:* Refactor `server.py` to map clients to independent Goose instances.

## Issue Tracking
All tasks and bugs are tracked in [GitHub Issues](https://github.com/OcotilloAI/Kestrel/issues).
