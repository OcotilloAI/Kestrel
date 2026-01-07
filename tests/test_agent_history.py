import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from coder_agent import CoderAgent as AgentRunner
from agent_session import AgentSession


class DummyClient:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)

    async def chat_with_tools(self, messages, tools, model_override=None, response_format=None):
        return self._responses.pop(0)


def test_agent_history_persists_user_and_tool(tmp_path):
    session = AgentSession(cwd=str(tmp_path))
    client = DummyClient(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "list_dir",
                            "arguments": json.dumps({"path": "."}),
                        },
                    }
                ],
            },
            {
                "content": "Done.",
                "tool_calls": [],
            },
        ]
    )
    runner = AgentRunner(client=client, max_steps=4)

    async def run_once():
        async for _ in runner.run(session, "List the files."):
            pass

    asyncio.run(run_once())

    roles = [entry["role"] for entry in session.history]
    contents = " ".join(entry["content"] for entry in session.history)
    assert "user" in roles
    assert "system" in roles
    assert "assistant" in roles
    assert "Tool result (list_dir)" in contents
