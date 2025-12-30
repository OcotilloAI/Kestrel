# Castro Speech Interface Notes

## Goal
Provide a speech-first interface for coding LLMs that prioritizes clarity, minimal cognitive load, and accurate task progress.

## Core Principles
- **Input:** capture the user's spoken prompt with minimal transformation. Minor cleanup for readability is okay, but avoid rewriting intent.
- **Output:** speak only the most relevant end-of-turn summary (final answer or explicit summary section), not the full intermediate output.
- **Tool use:** when the model requests tools, execute them faithfully and feed results back to the model; do not replace or infer tool actions.
- **Flow control:** ensure the agent follows required steps (e.g., run tests it created). Enforce post-task checks before finishing.

## Interaction Pattern
- User speaks a request.
- System forwards the request to the coding model.
- Model may ask clarifying questions or propose a plan.
- System executes tool calls and returns results.
- System surfaces a **short spoken summary** at the end of each phase:
  - What happened
  - What is needed from the user (if anything)
  - Whether to proceed

## Why This Matters
- Users driving or hands-busy need high-signal summaries, not verbose logs.
- Intermediate tool output is valuable for *reading*, but should be summarized for *speech*.
- Plan/clarify loops must be handled without overwhelming the user.

## Open Concerns
- How to reliably detect and extract the final summary section from model output.
- How to enforce “tests must run if created” without stalling the user flow.
- How to keep the conversation coherent while avoiding large spoken dumps.

