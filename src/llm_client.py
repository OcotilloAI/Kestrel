import os
from typing import List, Dict, Optional

import httpx


class LLMClient:
    def __init__(self) -> None:
        self.provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
        self.model = os.environ.get("LLM_MODEL", os.environ.get("GOOSE_MODEL", "qwen3-coder:30b-a3b-q4_K_M"))
        self.base_url = os.environ.get("LLM_API_URL")
        self.api_key = os.environ.get("LLM_API_KEY")

        if not self.base_url:
            if self.provider == "ollama":
                self.base_url = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
            else:
                self.base_url = "http://localhost:8080"

        self.base_url = self.base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(self, messages: List[Dict[str, str]], model_override: Optional[str] = None) -> str:
        model = model_override or self.model
        if self.provider == "ollama":
            return await self._chat_ollama(messages, model)
        return await self._chat_openai(messages, model)

    async def _chat_ollama(self, messages: List[Dict[str, str]], model: str) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            return str(message.get("content", "")).strip()

    async def _chat_openai(self, messages: List[Dict[str, str]], model: str) -> str:
        payload = {
            "model": model,
            "messages": messages,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            return str(message.get("content", "")).strip()
