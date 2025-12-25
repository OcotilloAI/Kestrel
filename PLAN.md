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
    - [x] Create `static/index.html` (and JS/CSS).
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

## Issue Tracking
Major tasks are tracked as GitHub Issues.
