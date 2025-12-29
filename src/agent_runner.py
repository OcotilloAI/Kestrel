import json
from typing import AsyncGenerator, Dict, Any, List

from agent_session import AgentSession
from agent_tools import list_dir, read_file, write_file, append_file, run_shell
from llm_client import LLMClient


SYSTEM_PROMPT = (
    "You are a coding agent that must use tools to perform work.\n"
    "Return exactly one JSON object per response, no extra text.\n\n"
    "Valid response forms:\n"
    "1) Tool call:\n"
    "   {\"type\":\"tool\",\"name\":\"shell\",\"arguments\":{\"command\":\"...\"}}\n"
    "   {\"type\":\"tool\",\"name\":\"list_dir\",\"arguments\":{\"path\":\".\"}}\n"
    "   {\"type\":\"tool\",\"name\":\"read_file\",\"arguments\":{\"path\":\"relative/path\"}}\n"
    "   {\"type\":\"tool\",\"name\":\"write_file\",\"arguments\":{\"path\":\"relative/path\",\"content\":\"...\"}}\n"
    "   {\"type\":\"tool\",\"name\":\"append_file\",\"arguments\":{\"path\":\"relative/path\",\"content\":\"...\"}}\n"
    "2) Final response:\n"
    "   {\"type\":\"final\",\"content\":\"...\"}\n\n"
    "Rules:\n"
    "- Use only relative paths within the working directory.\n"
    "- Do not scan the filesystem unless it helps accomplish the user request.\n"
    "- After using tools, continue until the task is complete, then return a final response.\n"
)


class AgentRunner:
    def __init__(self, client: LLMClient, max_steps: int = 12) -> None:
        self.client = client
        self.max_steps = max_steps

    async def run(
        self,
        session: AgentSession,
        user_text: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        messages.extend(session.history)
        messages.append({"role": "user", "content": user_text})

        for _ in range(self.max_steps):
            response = await self.client.chat(messages)
            parsed = self._safe_parse(response)
            if not parsed:
                yield {
                    "type": "system",
                    "role": "system",
                    "content": "Agent returned invalid JSON. Stopping.",
                    "source": "system",
                }
                return

            if parsed.get("type") == "final":
                content = str(parsed.get("content", "")).strip()
                if content:
                    session.history.append({"role": "assistant", "content": content})
                    yield {
                        "type": "assistant",
                        "role": "coder",
                        "content": content,
                        "source": "agent",
                    }
                return

            if parsed.get("type") != "tool":
                yield {
                    "type": "system",
                    "role": "system",
                    "content": "Agent response missing tool or final type. Stopping.",
                    "source": "system",
                }
                return

            tool_name = parsed.get("name")
            args = parsed.get("arguments", {}) or {}
            tool_request_content = json.dumps({"name": tool_name, "arguments": args}, ensure_ascii=True, indent=2)
            tool_request = {
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
            yield tool_request

            try:
                result = self._run_tool(session.cwd, tool_name, args)
                tool_result_text = json.dumps(result, ensure_ascii=True, indent=2)
                tool_response = {
                    "type": "tool",
                    "role": "system",
                    "content": (
                        f"Tool response: {tool_name}\n"
                        f"Working directory: {session.cwd}\n"
                        f"```json\n{tool_result_text}\n```"
                    ),
                    "source": "tool",
                    "metadata": {"tool_name": tool_name, "cwd": session.cwd},
                }
                yield tool_response
                messages.append(
                    {
                        "role": "system",
                        "content": f"Tool result ({tool_name}): {tool_result_text}",
                    }
                )
            except Exception as exc:
                error_text = f"Tool error ({tool_name}): {exc}"
                yield {
                    "type": "system",
                    "role": "system",
                    "content": error_text,
                    "source": "system",
                }
                messages.append({"role": "system", "content": error_text})
        yield {
            "type": "system",
            "role": "system",
            "content": "Agent stopped after too many steps.",
            "source": "system",
        }

    def _safe_parse(self, response: str) -> Dict[str, Any]:
        if not response:
            return {}
        response = response.strip()
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def _run_tool(self, cwd: str, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
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
        raise ValueError(f"Unknown tool: {name}")
