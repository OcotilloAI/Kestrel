# Kestrel

Kestrel is a voice-first software development interface. It provides hands-free, conversational interaction with coding agents via STT/TTS orchestration.

## Vision

Kestrel wraps coding agents (Claude Code, Codex, Gemini CLI, local LLMs via ollama/llama.cpp) in a real-time speech-processing layer:
1.  **Speak** your instructions and intent naturally.
2.  **Hear** the agent's responses, plans, and summaries.
3.  **Interrupt** or guide the agent mid-task (future goal).

## Architecture

- **Core**: LLM + tool loop with OpenAI-compatible API
- **Orchestrator**: Session state, transcripts, tool context
- **STT/TTS**: Browser/OS speech recognition and synthesis (client-side by default)
- **Backend**: Configurable - local models (ollama) or cloud APIs (OpenAI, Anthropic, etc.)

See `ARCHITECTURE.md` for full details.

## Status

**Current Phase:** Stability & UX improvements.
See `PLAN.md` for active work.

## Prerequisites

*   **Python 3.10+**: For the server.
*   **Node.js 18+**: For the web UI.
*   **LLM Backend**: Either:
    - Local: ollama with a coding model (e.g., `qwen2.5-coder`)
    - Cloud: OpenAI API key or compatible endpoint

## Quick Start

```bash
# Setup
./setup.sh

# Start (with local LLM)
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=qwen2.5-coder:7b
./start.sh
```

## Development

See `WORKFLOW.md` in the development vault for the full coding workflow.
See `CONTRIBUTING.md` for contribution guidelines.
