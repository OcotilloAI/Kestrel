# Kestrel Development Plan

**Goal:** Create a modern, web-based voice interface for the Goose agent that runs on various backends (Linux, Mac, Windows) and supports client-side audio processing (iOS, Android, Browser).

## Current Status
- [x] Project Initialization (License, Contributing, Git)
- [ ] Backend Refactor (FastAPI)
- [ ] Frontend Implementation (Web Speech API)
- [ ] Session & Context Management

## Roadmap

### Phase 1: Foundation & Backend
- **Objective:** Remove audio dependencies from the Python backend and expose Goose via a WebSocket API.
- **Tasks:**
    - [ ] Create `src/server.py` using FastAPI.
    - [ ] Implement WebSocket endpoint `/ws` for bi-directional text streaming.
    - [ ] Update `GooseWrapper` to be robust and async-friendly if needed.
    - [ ] Update dependency management (remove `pydub`, `sounddevice`, add `fastapi`, `uvicorn`, `websockets`).

### Phase 2: Web Frontend (MVP)
- **Objective:** A functional web interface for chatting with Goose using voice.
- **Tasks:**
    - [ ] Create `static/index.html` (and JS/CSS).
    - [ ] Implement STT using `window.SpeechRecognition`.
    - [ ] Implement TTS using `window.speechSynthesis`.
    - [ ] Build Chat UI:
        - [ ] Message history (scrolling).
        - [ ] Real-time input preview (non-scrolling).
        - [ ] System status indicator (Connecting, Thinking, etc.).

### Phase 3: Session Management & Advanced Features
- **Objective:** Manage multiple independent sessions and contexts.
- **Tasks:**
    - [ ] Add session ID handling in Backend.
    - [ ] Add UI sidebar for session switching.
    - [ ] Support switching "working directories" or git contexts via UI.

## Issue Tracking
Major tasks are tracked as GitHub Issues.
