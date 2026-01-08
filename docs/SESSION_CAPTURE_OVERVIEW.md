# Session Capture - Overview

> A voice-friendly summary of what we're building and why.

## The Problem

You're on the go. You're talking to Kestrel through voice. Work happens. But later, you have no way to review what was said, what was decided, or what changed. The current transcripts exist, but they're incomplete - you get fragments, not the full picture.

## The Solution

We're adding full session capture to Kestrel. Everything gets logged: what you said, what I understood, what the coding agent actually did under the hood, and the summary I gave you back.

Two output formats:

1. **Structured logs** in JSON Lines format - one event per line, easy to parse, easy to search. This feeds the machines.

2. **Markdown notes** that humans can actually read. Daily files, Obsidian-compatible, so you can use mindmap tooling later. This feeds your eyes.

The JSON becomes the source of truth. The markdown becomes the readable history. And later, both can feed a vector database for RAG - so you can ask "what did we decide about authentication last week?" and actually get an answer.

## The Four Phases

### Phase 1: Schema Work
Update the event format to capture richer metadata. Things like: was this raw speech-to-text, or my interpretation? What tool did I call? What files changed? Quick foundational stuff.

### Phase 2: Agent Stream Capture
When a coding agent runs in the background, capture its full output - not just the summary, but everything it printed. That's the audit trail when things go sideways.

### Phase 3: Markdown Generation
After each task completes, auto-generate a human-readable note. What you asked for, what I planned, what I changed, what files I touched. One note per day, per branch.

### Phase 4: Audio Pipeline
Server-side Whisper integration. Send voice, get transcription, execute task. This is "Option B" - capture audio, pass to the assistant, extract transcript, do the work.

## What This Enables

- **Review sessions** after the fact, even if you were driving when the work happened
- **Search past decisions** - find that thing you talked about three weeks ago
- **Debug failures** - see exactly what the agent tried when something broke
- **Build context** - RAG retrieval of relevant past work when starting new tasks
- **Share progress** - hand someone a markdown file and they know what happened

---

*Document created: 2026-01-08*
*Status: Phase 1 in progress*
