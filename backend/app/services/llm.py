"""Optional offline LLM wrapper, only used by routers/chat.py for local
text-based testing of the journey engine without a real Vapi call.
"""
from __future__ import annotations

import httpx

from ..config import get_settings


async def complete(system_prompt: str, messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": settings.groq_model,
                    "messages": [{"role": "system", "content": system_prompt}, *messages],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": 512,
                    "system": system_prompt,
                    "messages": messages,
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]

    raise RuntimeError("No LLM_PROVIDER configured (set 'groq' or 'anthropic' in .env for offline chat testing).")
