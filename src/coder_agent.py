"""Enhanced Coder Agent with planning, validation, and retry capabilities.

Wraps the base AgentRunner with:
- Internal planning step before execution
- Error detection from tool output
- Retry logic with alternative approaches
- Structured TaskResult reporting via XML
"""

import json
import re
from typing import AsyncGenerator, Dict, Any, List, Optional

from agent_session import AgentSession
from agent_tools import (
    list_dir, read_file, write_file, append_file, run_shell,
    TOOL_DEFINITIONS,
)
from llm_client import LLMClient
from task_types import TaskResult, TaskStatus, parse_result_xml


CODER_SYSTEM_PROMPT = """You are a Coder agent. You must:
1. PLAN: Outline tool calls needed before acting
2. EXECUTE: Use tools to accomplish the task
3. VERIFY: Check tool output for errors (non-zero exit codes, exceptions)
4. VALIDATE: Run tests when creating testable code
5. REPORT: Provide clear success/failure status

Output using XML tags:

<think>
Steps needed:
1. [tool: list_dir] Check current directory structure
2. [tool: write_file] Create the file
3. [tool: shell] Run tests to verify
</think>

After task completion, always report:
<result>
  <status>success|partial|failed</status>
  <summary>What was accomplished</summary>
  <files>path1.py, path2.py</files>
  <tested>true|false</tested>
  <errors>Error message if any, or empty</errors>
</result>

Rules:
- Use only relative paths within the working directory.
- Check tool output for errors (exit_code != 0 means failure).
- CRITICAL: For ALL Python execution (pytest, scripts, pip install, etc.), use the builder container:
  `docker compose exec builder bash -lc "cd /workspace/PROJECT/main && <command>"`
  The main container does NOT have pip packages like pytest, requests, yfinance, etc.
- Port 8000 is reserved by Kestrel. Use ports 8080, 3000, or 5000 for test servers.
- For servers/daemons, run them in the background with '&' and test quickly.
- If a step fails, try ONE alternative approach before giving up.
- Always emit a <result> block at the end, even if the task failed.
"""


class CoderAgent:
    """Enhanced coder agent with planning, validation, and retry capabilities."""

    def __init__(
        self,
        client: LLMClient,
        max_steps: int = 30,
        max_retries: int = 2,
    ) -> None:
        self.client = client
        self.max_steps = max_steps
        self.max_retries = max_retries

    async def run(
        self,
        session: AgentSession,
        user_text: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute a task with internal planning and validation.

        This is compatible with the AgentRunner.run() interface but adds:
        - Think block parsing for planning visibility
        - Result block parsing for structured output
        - Better error detection
        """
        session.history.append({"role": "user", "content": user_text})
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": CODER_SYSTEM_PROMPT},
            *session.history,
        ]

        steps_remaining = self.max_steps
        accumulated_content: List[str] = []

        while steps_remaining is None or steps_remaining > 0:
            response = await self.client.chat_with_tools(messages, TOOL_DEFINITIONS)
            content = str(response.get("content", "")).strip()
            tool_calls = self._normalize_tool_calls(response.get("tool_calls") or [])

            # Parse XML-style tool calls if not in structured format
            if not tool_calls and ("<tool_call>" in content or "<function=" in content):
                tool_calls = self._parse_tool_tags(content)
                content = self._strip_tool_tags(content)

            # Extract and emit think block for planning visibility
            think_match = re.search(r"<think>([\s\S]*?)</think>", content)
            if think_match:
                yield {
                    "type": "planning",
                    "role": "coder",
                    "content": think_match.group(1).strip(),
                    "source": "coder",
                }
                # Remove think block from content
                content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()

            if content or tool_calls:
                assistant_message: Dict[str, Any] = {"role": "assistant", "content": content}
                if tool_calls and getattr(self.client, "supports_tool_call_messages", True):
                    assistant_message["tool_calls"] = tool_calls
                messages.append(assistant_message)

            if content:
                accumulated_content.append(content)
                session.history.append({"role": "assistant", "content": content})
                yield {
                    "type": "assistant",
                    "role": "coder",
                    "content": content,
                    "source": "coder",
                }
                if not tool_calls:
                    # Final response - check for result block
                    result = parse_result_xml(content)
                    if result:
                        yield {
                            "type": "result",
                            "role": "coder",
                            "content": result.summary,
                            "source": "coder",
                            "metadata": {
                                "status": result.status.value,
                                "files_changed": result.files_changed,
                                "tested": result.tested,
                                "errors": result.errors,
                            },
                        }
                    return

            if not tool_calls:
                yield {
                    "type": "system",
                    "role": "system",
                    "content": "Coder returned no tool calls or final response. Stopping.",
                    "source": "system",
                }
                return

            # Execute tool calls
            for call in tool_calls:
                function = call.get("function", {})
                tool_name = function.get("name")
                args_raw = function.get("arguments") or "{}"
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except json.JSONDecodeError:
                    args = {}

                # Emit tool request
                tool_request_content = json.dumps(
                    {"name": tool_name, "arguments": args},
                    ensure_ascii=True,
                    indent=2,
                )
                yield {
                    "type": "tool",
                    "role": "system",
                    "content": (
                        f"Tool request: {tool_name}\n"
                        f"Working directory: {session.cwd}\n"
                        f"```json\n{tool_request_content}\n```"
                    ),
                    "source": "tool",
                    "metadata": {"tool_name": tool_name, "cwd": session.cwd},
                }

                # Execute tool
                try:
                    result = self._run_tool(session.cwd, tool_name, args)
                    tool_result_text = json.dumps(result, ensure_ascii=True, indent=2)

                    # Check for errors in result
                    has_error = False
                    if isinstance(result, dict):
                        exit_code = result.get("exit_code")
                        if exit_code is not None and exit_code != 0:
                            has_error = True

                    yield {
                        "type": "tool",
                        "role": "system",
                        "content": (
                            f"Tool response: {tool_name}\n"
                            f"Working directory: {session.cwd}\n"
                            f"```json\n{tool_result_text}\n```"
                        ),
                        "source": "tool",
                        "metadata": {
                            "tool_name": tool_name,
                            "cwd": session.cwd,
                            "has_error": has_error,
                        },
                    }

                    # Add to message history
                    if getattr(self.client, "supports_tool_call_messages", True):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.get("id"),
                            "content": tool_result_text,
                        })
                    else:
                        messages.append({
                            "role": "system",
                            "content": f"Tool result ({tool_name}): {tool_result_text}",
                        })

                    session.history.append({
                        "role": "system",
                        "content": f"Tool result ({tool_name}): {tool_result_text}",
                    })

                except Exception as exc:
                    error_text = f"Tool error ({tool_name}): {exc}"
                    yield {
                        "type": "system",
                        "role": "system",
                        "content": error_text,
                        "source": "system",
                    }
                    messages.append({"role": "system", "content": error_text})

            if steps_remaining is not None:
                steps_remaining -= 1

        if steps_remaining == 0:
            yield {
                "type": "error",
                "role": "system",
                "content": "Coder stopped after too many steps without completing the task.",
                "source": "system",
            }

    def _strip_tool_tags(self, content: str) -> str:
        """Remove tool call XML tags from content."""
        cleaned = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", content)
        cleaned = re.sub(r"</?function[^>]*>", "", cleaned)
        cleaned = re.sub(r"</?parameter[^>]*>", "", cleaned)
        return cleaned.strip()

    def _parse_tool_tags(self, content: str) -> List[Dict[str, Any]]:
        """Parse XML-style tool call tags from content."""
        tool_blocks = re.findall(r"<tool_call>([\s\S]*?)</tool_call>", content)
        func_blocks = re.findall(r"<function=[^>]+>[\s\S]*?</function>", content)
        blocks: List[Dict[str, str]] = []

        if tool_blocks:
            blocks.extend({"kind": "tool_call", "text": block} for block in tool_blocks)
        elif func_blocks:
            blocks.extend({"kind": "function", "text": block} for block in func_blocks)

        calls: List[Dict[str, Any]] = []
        for block in blocks:
            kind = block["kind"]
            text = block["text"].strip()

            if kind == "tool_call":
                if not text:
                    continue
                if text.startswith("{") and text.endswith("}"):
                    try:
                        payload = json.loads(text)
                        call = self._tool_call_from_payload(payload, len(calls))
                        if call:
                            calls.append(call)
                            continue
                    except json.JSONDecodeError:
                        pass

                if "<function=" in text:
                    call = self._parse_function_block(text, len(calls))
                    if call:
                        calls.append(call)
                    continue

                # Treat as shell command
                calls.append({
                    "id": f"tag_{len(calls)}",
                    "type": "function",
                    "function": {
                        "name": "shell",
                        "arguments": json.dumps({"command": text}),
                    },
                })
                continue

            # Parse function block
            func_match = re.search(r"<function=([^>]+)>", text)
            if func_match:
                name = func_match.group(1).strip()
                args: Dict[str, Any] = {}
                for param, value in re.findall(
                    r"<parameter=([^>]+)>([\s\S]*?)</parameter>", text
                ):
                    args[param.strip()] = value.strip()
                if not args:
                    block_text = re.sub(r"</?function[^>]*>", "", text)
                    block_text = re.sub(r"</?parameter[^>]*>", "", block_text).strip()
                    if name == "shell" and block_text:
                        args["command"] = block_text
                    elif name == "list_dir":
                        args["path"] = block_text or "."
                calls.append({
                    "id": f"tag_{len(calls)}",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args),
                    },
                })

        return calls

    def _tool_call_from_payload(
        self, payload: Dict[str, Any], index: int
    ) -> Optional[Dict[str, Any]]:
        """Convert a JSON payload to a tool call structure."""
        function = payload.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            args = function.get("arguments", {})
        else:
            name = payload.get("name")
            args = payload.get("arguments", {})

        if not name:
            return None

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"command": args} if name == "shell" else {"value": args}

        if not isinstance(args, dict):
            args = {}

        return {
            "id": f"tag_{index}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(args),
            },
        }

    def _parse_function_block(
        self, text: str, index: int
    ) -> Optional[Dict[str, Any]]:
        """Parse a <function=...> block."""
        func_match = re.search(r"<function=([^>]+)>", text)
        if not func_match:
            return None

        name = func_match.group(1).strip()
        args: Dict[str, Any] = {}

        for param, value in re.findall(
            r"<parameter=([^>]+)>([\s\S]*?)</parameter>", text
        ):
            args[param.strip()] = value.strip()

        if not args:
            block_text = re.sub(r"</?function[^>]*>", "", text)
            block_text = re.sub(r"</?parameter[^>]*>", "", block_text).strip()
            if name == "shell" and block_text:
                args["command"] = block_text
            elif name == "list_dir":
                args["path"] = block_text or "."

        return {
            "id": f"tag_{index}",
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(args),
            },
        }

    def _normalize_tool_calls(
        self, tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Normalize tool calls to consistent format."""
        normalized: List[Dict[str, Any]] = []
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            if "type" not in call:
                call = {**call, "type": "function"}
            normalized.append(call)
        return normalized

    def _run_tool(
        self, cwd: str, name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool by name."""
        if name == "shell":
            return run_shell(cwd, args.get("command", ""))
        if name == "list_dir":
            return list_dir(cwd, args.get("path", "."))
        if name == "read_file":
            return read_file(cwd, args.get("path", ""))
        if name == "write_file":
            return write_file(cwd, args.get("path", ""), args.get("content", ""))
        if name == "append_file":
            return append_file(cwd, args.get("path", ""), args.get("content", ""))

        # Try validation tools if available
        try:
            from agent_tools_validation import run_validation_tool
            result = run_validation_tool(cwd, name, args)
            if result is not None:
                return result
        except ImportError:
            pass

        raise ValueError(f"Unknown tool: {name}")


# Backward compatibility: alias AgentRunner to CoderAgent
AgentRunner = CoderAgent
