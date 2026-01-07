# Overview of Kestrel Goals

The overall goal of the project is to provide a voice/speech interface to support software development (I tend to drive long stretches and want to avoid typing). This service can drive various coding agents—Claude Code, Codex, Gemini CLI, or local LLMs via ollama/llama.cpp—providing a consistent voice interface regardless of the backend.

As a part of this goal, we need to (and have started to) rethink the "Developer Interface". The first code tools were developed and designed as extensions to the code editors that were the tool of choice for every developer alive, the IDE, with its snippets and code expansion, integration with dev-ops lifecycle tools, and all sorts of plugins to make it easier to understand and develop/test/release software. That shifted with the CLI revolution, where the actual code review was less critical, and the functionality, test, and code definition took center stage. Still snippets of code fly by, and often the developer is asked to step in and test something or review something. The shift to this audio based interface means that the information density drops yet another order of magnitude, and instead we are more in the domain of the product manager rather than even the engineering lead. We're now discussing what the software should do, and how we should interface with it, rather than how it should do it, or what tools, what libraries, even what languages are used are not important in this interface.

So we're looking to provide a mechanism to help manage the CLI style code manager, redirecting requests to "try this" or "test that" to use tools to build tests to check this, or test that. And in the end, I expect we'll also have a video based output, where the test development and output becomes part of the response stream, but with an audio walkthrough, so that the product manager can see and discuss areas where the product meets or fails to meet the project requirements.

I'm not trying to dictate the tools or the models, or the backend functionality. We should just be using the latest possible best practice approaches to software development, supported by the latest practical LLM, whether coding, thinking, or MoE style services, supported by a code centric tool using MCP wielding middle layer (that hopefully has an API for integration, or that can follow the MCP protocol for such integrations and tool using functions), and can be paired up with a next order LLM engine (likely the same backend LLM just with a different system prompt) that can understand the coder agent's requests and queries and either surface them to the user/product manager, or solve them locally following the rules and guidance of always using best practices to implement services and functions.

We have a solid base for development, and there will be many changes coming, but we now need the "engine" to do the heavy lifting work here.

## Agent Backend Options

Kestrel is designed to work with multiple coding agent backends:

- **Local LLMs**: ollama, llama.cpp with models like Qwen, DeepSeek, or CodeLlama
- **Cloud APIs**: OpenAI, Anthropic (Claude), Google (Gemini)
- **CLI Agents**: Claude Code, Codex CLI, Gemini CLI, Pi Coding Agent

The core architecture uses an OpenAI-compatible API interface, making it easy to swap backends based on availability, cost, or capability requirements.
