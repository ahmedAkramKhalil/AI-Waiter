from __future__ import annotations

import json
import re
from typing import AsyncIterator

import httpx

from apps.api.config import settings
from apps.api.models.llm import LLMResponse


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json(raw: str) -> str | None:
    """
    Find the first valid JSON object in `raw`.
    Tries: (1) fenced ```json ...``` block, (2) first balanced {...} span.
    Returns the JSON substring, or None if nothing parseable was found.
    """
    # 1. Fenced code block
    m = _FENCED_JSON_RE.search(raw)
    if m:
        candidate = m.group(1)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 2. Walk the string looking for the first balanced {...} that parses
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(raw):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = raw[start : i + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    start = -1  # keep scanning
    return None

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
        "max_tokens": 200,   # single-pass JSON reply is short (~80 tokens)
        "stream": stream,
    }

    return payload


async def call_llm(messages: list[dict]) -> LLMResponse:
    """Non-streaming call — used inside the tool-calling loop."""
    payload = _build_payload(messages, stream=False)

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{settings.llm_api_base}/chat/completions",
            json=payload,
            headers=_HEADERS,
        )
        resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"]

    # The LLM sometimes wraps JSON in prose or markdown fences. Extract it.
    extracted = _extract_json(raw)
    if extracted is not None:
        try:
            return LLMResponse.model_validate_json(extracted)
        except Exception:
            pass

    # Last resort — couldn't find any JSON. Use the raw text as a plain reply,
    # but strip obvious code fences so the user doesn't see ```json```.
    cleaned = re.sub(r"```(?:json)?.*?```", "", raw, flags=re.DOTALL).strip()
    return LLMResponse(reply_ar=cleaned or "عذراً، لم أفهم طلبك. هل يمكنك إعادة الصياغة؟")


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
