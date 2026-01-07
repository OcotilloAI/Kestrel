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


def test_agent_runner_handles_tool_calls(tmp_path):
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
    runner = AgentRunner(client=client, max_steps=3)

    async def run_once():
        events = []
        async for event in runner.run(session, "List files."):
            events.append(event)
        return events

    events = asyncio.run(run_once())
    tool_events = [e for e in events if e.get("type") == "tool"]
    assistant_events = [e for e in events if e.get("type") == "assistant"]
    assert tool_events
    assert assistant_events
    assert assistant_events[-1]["content"] == "Done."


def test_agent_runner_parses_tool_tags(tmp_path):
    session = AgentSession(cwd=str(tmp_path))
    client = DummyClient(
        [
            {
                "content": "<tool_call> <function=list_dir> <parameter=path>.</parameter> </function> </tool_call>",
                "tool_calls": [],
            },
            {
                "content": "Done.",
                "tool_calls": [],
            },
        ]
    )
    runner = AgentRunner(client=client, max_steps=3)

    async def run_once():
        events = []
        async for event in runner.run(session, "List files."):
            events.append(event)
        return events

    events = asyncio.run(run_once())
    tool_events = [e for e in events if e.get("type") == "tool"]
    assistant_events = [e for e in events if e.get("type") == "assistant"]
    assert tool_events
    assert assistant_events
    assert assistant_events[-1]["content"] == "Done."


def test_agent_runner_parses_shell_tool_tag(tmp_path):
    session = AgentSession(cwd=str(tmp_path))
    client = DummyClient(
        [
            {
                "content": "<tool_call> ls -la </tool_call>",
                "tool_calls": [],
            },
            {
                "content": "Done.",
                "tool_calls": [],
            },
        ]
    )
    runner = AgentRunner(client=client, max_steps=3)

    async def run_once():
        events = []
        async for event in runner.run(session, "List files."):
            events.append(event)
        return events

    events = asyncio.run(run_once())
    tool_events = [e for e in events if e.get("type") == "tool"]
    assert tool_events


def test_agent_runner_parses_shell_tool_tag_with_parameter(tmp_path):
    session = AgentSession(cwd=str(tmp_path))
    client = DummyClient(
        [
            {
                "content": "<tool_call><function=shell><parameter=command>ls -la</parameter></function></tool_call>",
                "tool_calls": [],
            },
            {
                "content": "Done.",
                "tool_calls": [],
            },
        ]
    )
    runner = AgentRunner(client=client, max_steps=3)

    async def run_once():
        events = []
        async for event in runner.run(session, "List files."):
            events.append(event)
        return events

    events = asyncio.run(run_once())
    tool_events = [e for e in events if e.get("type") == "tool"]
    assert tool_events


def test_agent_runner_parses_json_tool_tag(tmp_path):
    session = AgentSession(cwd=str(tmp_path))
    payload = json.dumps({"name": "shell", "arguments": {"command": "ls -la"}})
    client = DummyClient(
        [
            {
                "content": f"<tool_call>{payload}</tool_call>",
                "tool_calls": [],
            },
            {
                "content": "Done.",
                "tool_calls": [],
            },
        ]
    )
    runner = AgentRunner(client=client, max_steps=3)

    async def run_once():
        events = []
        async for event in runner.run(session, "List files."):
            events.append(event)
        return events

    events = asyncio.run(run_once())
    tool_events = [e for e in events if e.get("type") == "tool"]
    assert tool_events
