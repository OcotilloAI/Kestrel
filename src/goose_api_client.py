import json
import time
from typing import AsyncGenerator, Optional

import httpx


class GooseApiClient:
    def __init__(self, base_url: str, secret_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret_key = secret_key

    def _headers(self) -> dict:
        return {"X-Secret-Key": self.secret_key}

    def start_session(self, working_dir: str) -> str:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/agent/start",
                headers=self._headers(),
                json={"working_dir": working_dir},
            )
            response.raise_for_status()
            payload = response.json()
            return payload["id"]

    def resume_session(self, session_id: str) -> str:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/agent/resume",
                headers=self._headers(),
                json={"session_id": session_id, "load_model_and_extensions": True},
            )
            response.raise_for_status()
            payload = response.json()
            return payload["id"]

    def _build_user_message(self, text: str) -> dict:
        return {
            "role": "user",
            "created": int(time.time()),
            "content": [{"type": "text", "text": text}],
            "metadata": {"userVisible": True, "agentVisible": True},
        }

    async def stream_reply(self, session_id: str, text: str) -> AsyncGenerator[dict, None]:
        payload = {
            "session_id": session_id,
            "user_message": self._build_user_message(text),
        }
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/reply",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[len("data:"):].strip()
                    if not line or line == "[DONE]":
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield event


class GooseApiSession:
    def __init__(self, client: GooseApiClient, session_id: str, working_dir: str) -> None:
        self.client = client
        self.session_id = session_id
        self.working_dir = working_dir

    async def stream_reply(self, text: str) -> AsyncGenerator[dict, None]:
        async for event in self.client.stream_reply(self.session_id, text):
            yield event

    def is_alive(self) -> bool:
        return True
