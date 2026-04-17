from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from apps.api.config import settings
from apps.api.models.llm import LLMResponse

# JSON schema used by vLLM guided_json to force valid structured output
LLM_RESPONSE_SCHEMA: dict = LLMResponse.model_json_schema()

_HEADERS = {"Authorization": f"Bearer {settings.runpod_api_key}"}


async def call_llm(messages: list[dict]) -> LLMResponse:
    """
    Non-streaming call with guided_json.
    Used inside the tool-calling loop where we need complete JSON to parse.
    """
    payload = {
        "model": settings.llm_model_name,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
        "extra_body": {
            "guided_json": LLM_RESPONSE_SCHEMA,
            "guided_decoding_backend": "outlines",
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.runpod_api_base}/chat/completions",
            json=payload,
            headers=_HEADERS,
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]
    return LLMResponse.model_validate_json(raw)


async def stream_text(messages: list[dict]) -> AsyncIterator[str]:
    """
    Streaming call WITHOUT guided_json — used only for the final reply_ar
    to produce a natural token-by-token feel.
    Yields raw text delta strings.
    """
    payload = {
        "model": settings.llm_model_name,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.runpod_api_base}/chat/completions",
            json=payload,
            headers=_HEADERS,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk.strip() == "[DONE]":
                    break
                data = json.loads(chunk)
                delta = data["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta
