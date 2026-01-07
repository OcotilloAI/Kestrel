import os
from typing import List, Dict, Optional, Any

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
        tool_call_pref = os.environ.get("LLM_TOOL_CALL_MESSAGES")
        if tool_call_pref is None:
            self.supports_tool_call_messages = "llama-cpp" not in self.base_url
        else:
            self.supports_tool_call_messages = tool_call_pref.strip().lower() not in {"0", "false", "no"}

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model_override: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        model = model_override or self.model
        if self.provider == "ollama":
            return await self._chat_ollama(messages, model)
        return await self._chat_openai(messages, model, response_format=response_format)

    async def _chat_ollama(self, messages: List[Dict[str, str]], model: str) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            message = data.get("message", {})
            return str(message.get("content", "")).strip()

    async def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        model: str,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if response_format:
            payload["response_format"] = response_format
        async with httpx.AsyncClient(timeout=300.0) as client:
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

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model_override: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        model = model_override or self.model
        if self.provider == "ollama":
            raise ValueError("Tool calling is not supported for the Ollama provider.")
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": tools,
        }
        if response_format:
            payload["response_format"] = response_format
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return {"content": "", "tool_calls": []}
            message = choices[0].get("message", {})
            return {
                "content": str(message.get("content", "")).strip(),
                "tool_calls": message.get("tool_calls") or [],
            }
