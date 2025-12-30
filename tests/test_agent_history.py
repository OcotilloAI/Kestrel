import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from agent_runner import AgentRunner
from agent_session import AgentSession


class DummyClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    async def chat(self, messages, model_override=None):
        return self._responses.pop(0)


def test_agent_history_persists_user_and_tool(tmp_path):
    session = AgentSession(cwd=str(tmp_path))
    client = DummyClient(
        [
            '{"type":"tool","name":"list_dir","arguments":{"path":"."}}',
            '{"type":"final","content":"Done."}',
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
