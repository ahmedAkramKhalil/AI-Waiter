from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from apps.api.config import settings
from apps.api.models.llm import LLMResponse

LLM_RESPONSE_SCHEMA: dict = LLMResponse.model_json_schema()

_HEADERS = {"Authorization": f"Bearer {settings.llm_api_key}"}


def _build_payload(messages: list[dict], stream: bool = False) -> dict:
    """
    Build the request payload.
    - vllm:  uses extra_body.guided_json for strict JSON output
    - ollama: uses response_format (JSON mode, less strict but works for dev)
    """
    payload: dict = {
        "model": settings.llm_model_name,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,   # tool-loop calls need short JSON only
        "stream": stream,
    }

    # Use JSON mode for all backends — widely supported
    payload["response_format"] = {"type": "json_object"}

    return payload


async def call_llm(messages: list[dict]) -> LLMResponse:
    """Non-streaming call — used inside the tool-calling loop."""
    payload = _build_payload(messages, stream=False)

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.llm_api_base}/chat/completions",
            json=payload,
            headers=_HEADERS,
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]

    # Strip markdown code block wrapper if present (happens without guided_json)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last line (```)
        cleaned = "\n".join(lines[1:-1]).strip()

    # Attempt to parse structured response
    try:
        return LLMResponse.model_validate_json(cleaned)
    except Exception:
        # If JSON is malformed, return the raw text as a plain reply
        return LLMResponse(reply_ar=cleaned)


async def stream_text(messages: list[dict]) -> AsyncIterator[str]:
    """Streaming call — used for final reply to give typing feel."""
    payload = _build_payload(messages, stream=True)
    # Remove JSON mode for streaming (we just want natural text)
    payload.pop("response_format", None)
    if "extra_body" in payload:
        payload.pop("extra_body")

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.llm_api_base}/chat/completions",
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
