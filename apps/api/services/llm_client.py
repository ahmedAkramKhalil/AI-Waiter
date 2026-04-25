from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any, AsyncIterator

import httpx

# Flip DEBUG_TIMING=1 in env to enable per-chunk timing. Default on in dev.
_DEBUG = os.getenv("DEBUG_TIMING", "1") == "1"

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


def _effective_model_name(model_name: str | None = None) -> str:
    return model_name or settings.llm_model_name


def _build_payload(
    messages: list[dict],
    stream: bool = False,
    *,
    model_name: str | None = None,
    max_tokens: int | None = None,
) -> dict:
    """
    Build the request payload.
    - vllm:  uses extra_body.guided_json for strict JSON output
    - ollama: uses response_format (JSON mode, less strict but works for dev)
    """
    payload: dict = {
        "model": _effective_model_name(model_name),
        "messages": messages,
        "temperature": settings.llm_temperature,
        "top_p": settings.llm_top_p,
        "max_tokens": max_tokens or settings.llm_max_tokens,
        "stream": stream,
    }

    # Ollama-only: pass per-request runtime options through OpenAI-compat shim.
    # Forces full-CPU usage and keeps the model resident.
    if settings.llm_backend == "ollama":
        payload["options"] = {
            "num_thread": settings.llm_num_thread,
            "num_ctx": settings.llm_num_ctx,
            "num_predict": max_tokens or settings.llm_max_tokens,
            "keep_alive": settings.llm_keep_alive,
        }

    return payload


async def call_llm(
    messages: list[dict],
    *,
    model_name: str | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Non-streaming call — used inside the tool-calling loop."""
    payload = _build_payload(
        messages,
        stream=False,
        model_name=model_name,
        max_tokens=max_tokens,
    )

    timeout = httpx.Timeout(connect=settings.llm_connect_timeout_s, read=None, write=None, pool=None)
    attempts = max(1, settings.llm_request_retries + 1)
    last_error: Exception | None = None
    resp = None
    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{settings.llm_api_base}/chat/completions",
                    json=payload,
                    headers=_HEADERS,
                )
                resp.raise_for_status()
                break
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt >= attempts:
                raise
            await asyncio.sleep((settings.llm_retry_backoff_ms * attempt) / 1000)
    if resp is None:
        raise RuntimeError(f"LLM request failed: {last_error!r}")

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
    return LLMResponse(reply_ar=cleaned or "آسف، ما فهمت طلبك. ممكن تعيد صياغته شوي؟")


async def stream_text(
    messages: list[dict],
    *,
    model_name: str | None = None,
    max_tokens: int | None = None,
    metrics: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Streaming call — used for final reply to give typing feel."""
    payload = _build_payload(
        messages,
        stream=True,
        model_name=model_name,
        max_tokens=max_tokens,
    )
    # Remove JSON mode for streaming (we just want natural text)
    payload.pop("response_format", None)
    if "extra_body" in payload:
        payload.pop("extra_body")

    # connect: fail fast if Ollama isn't up. read/write/pool: None = no timeout,
    # because first-token latency on cold CPU loads can exceed any sane bound.
    timeout = httpx.Timeout(connect=settings.llm_connect_timeout_s, read=None, write=None, pool=None)
    attempts = max(1, settings.llm_request_retries + 1)
    last_error: Exception | None = None

    if _DEBUG:
        payload_size = len(json.dumps(payload))
        print(
            f"[LLM]   POST {settings.llm_api_base}/chat/completions "
            f"(payload={payload_size}B, model={payload['model']})",
            flush=True,
        )

    for attempt in range(1, attempts + 1):
        t_req = time.perf_counter()
        t_first_byte: float | None = None
        t_first_token: float | None = None
        t_last_token = t_req
        n_tokens = 0
        max_gap_ms = 0.0
        total_chars = 0

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{settings.llm_api_base}/chat/completions",
                    json=payload,
                    headers=_HEADERS,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if t_first_byte is None:
                            t_first_byte = time.perf_counter()
                            if _DEBUG:
                                print(
                                    f"[LLM]   first byte (headers+SSE open) = "
                                    f"{(t_first_byte - t_req)*1000:7.1f} ms",
                                    flush=True,
                                )
                        if not line.startswith("data: "):
                            continue
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        data = json.loads(chunk)
                        delta = data["choices"][0]["delta"].get("content", "")
                        if delta:
                            now = time.perf_counter()
                            if t_first_token is None:
                                t_first_token = now
                                if metrics is not None:
                                    metrics["llm_ttft_ms"] = round((now - t_req) * 1000, 1)
                                if _DEBUG:
                                    print(
                                        f"[LLM]   TTFT (prefill + 1 token)     = "
                                        f"{(now - t_req)*1000:7.1f} ms",
                                        flush=True,
                                    )
                            gap_ms = (now - t_last_token) * 1000
                            if gap_ms > max_gap_ms:
                                max_gap_ms = gap_ms
                            t_last_token = now
                            n_tokens += 1
                            total_chars += len(delta)
                            yield delta

            t_end = time.perf_counter()
            total_ms = (t_end - t_req) * 1000
            decode_ms = (t_end - (t_first_token or t_req)) * 1000
            if _DEBUG:
                tok_per_s = n_tokens / (decode_ms / 1000) if decode_ms > 0 else 0
                print(
                    f"[LLM]   decode: {n_tokens} chunks, {total_chars} chars, "
                    f"{decode_ms:7.1f} ms  → {tok_per_s:5.1f} chunk/s  "
                    f"(worst gap {max_gap_ms:.0f} ms)",
                    flush=True,
                )
                print(f"[LLM]   TOTAL stream_text            = {total_ms:7.1f} ms", flush=True)
            if metrics is not None:
                metrics.setdefault("llm_ttft_ms", round(((t_first_token or time.perf_counter()) - t_req) * 1000, 1))
                metrics["llm_decode_ms"] = round(decode_ms, 1)
                metrics["llm_total_ms"] = round(total_ms, 1)
                metrics["llm_chunks"] = n_tokens
                metrics["llm_chars"] = total_chars
                metrics["llm_retry_count"] = attempt - 1
                metrics["model"] = payload["model"]
            return
        except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError) as exc:
            last_error = exc
            if t_first_token is not None or attempt >= attempts:
                raise
            if _DEBUG:
                print(f"[LLM]   retrying stream after early failure: {exc!r}", flush=True)
            await asyncio.sleep((settings.llm_retry_backoff_ms * attempt) / 1000)

    raise RuntimeError(f"LLM streaming failed: {last_error!r}")


async def warmup_llm() -> None:
    """Best-effort warmup to reduce first real-request TTFT after startup."""
    payload = _build_payload(
        [{"role": "user", "content": "مرحبا"}],
        stream=False,
        max_tokens=8,
    )
    timeout = httpx.Timeout(connect=10.0, read=20.0, write=20.0, pool=None)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{settings.llm_api_base}/chat/completions",
            json=payload,
            headers=_HEADERS,
        )
        resp.raise_for_status()
