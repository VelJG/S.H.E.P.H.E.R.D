from __future__ import annotations

import os
from typing import Protocol


class AgentModelClient(Protocol):
    provider: str
    model: str

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        ...


class OpenAIModelClient:
    provider = "openai"

    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self.model = model
        self._client = OpenAI(api_key=api_key)

    @classmethod
    def from_env(cls) -> "OpenAIModelClient | None":
        provider = os.getenv("AGENT_PROVIDER", "openai").strip().lower()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if provider not in {"openai", "auto"} or not api_key:
            return None
        return cls(api_key=api_key, model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=420,
        )
        content = response.choices[0].message.content if response.choices else ""
        return (content or "").strip()
