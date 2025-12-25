# Kestrel

This project aims to provide a seamless voice interface for the [Block Goose](https://github.com/block/goose) coding agent, enabling hands-free, conversational interaction with your AI developer.

## Vision

The goal is to extend the capabilities of `goose` by wrapping it in a real-time speech-processing layer. This allows users to:
1.  **Speak** their instructions and intent naturally.
2.  **Hear** the agent's responses, plans, and summaries.
3.  **Interrupt** or guide the agent mid-task (future goal).

## Status

**Current Phase:** Architecture & Planning.
Previous prototype code has been removed to focus on this new direction.

## Prerequisites

*   **Goose**: You must have `goose` installed and configured on your system.
*   **Python 3.10+**: For the bridge logic.
*   **Piper TTS**: High-quality, local neural text-to-speech.
*   **Whisper**: Robust speech-to-text.

## Roadmap

1.  **Proof of Concept**: A simple Python script that pipes STT -> Goose -> TTS.
2.  **Streamed Audio**: Lower latency processing.
3.  **VAD Integration**: Smartly detect when the user has finished speaking.