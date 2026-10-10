"""
Backend/ai.py

One place for every model call, so model names, API keys, retries, timeouts,
fallback and error handling live here instead of being copied into each router.

Two providers:
  "gemini"  - Google Gemini
  "openai"  - any OpenAI-compatible API (Groq by default, or real OpenAI)

If the chosen provider keeps failing and the other one has a key configured,
the call is retried there (turn off with AI_FALLBACK=0).
"""

import json
import logging
import os
import re
import time

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

log = logging.getLogger("grindos.ai")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# OpenAI-compatible side. Uses OPENAI_* if set, otherwise falls back to the
# GROQ_* variables the resume feature already used.
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # empty = default for the key used

PROVIDERS = {"gemini", "openai"}

_gemini_client = None
_openai_client = None


class AIError(Exception):
    """The model call failed or returned something we couldn't use."""


def _configured(provider: str) -> bool:
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY"))
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY"))


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        from google.genai import types

        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise AIError("GEMINI_API_KEY is not set")
        _gemini_client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=60_000),  # milliseconds
        )
    return _gemini_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        if os.getenv("OPENAI_API_KEY"):
            key = os.getenv("OPENAI_API_KEY")
            base_url = OPENAI_BASE_URL or None  # None = api.openai.com
        else:
            key = os.getenv("GROQ_API_KEY")
            base_url = OPENAI_BASE_URL or "https://api.groq.com/openai/v1"
        if not key:
            raise AIError("Neither OPENAI_API_KEY nor GROQ_API_KEY is set")
        _openai_client = OpenAI(api_key=key, base_url=base_url, timeout=60)  # seconds
    return _openai_client


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S | re.I)
    return match.group(1) if match else text


def _is_transient(exc: Exception) -> bool:
    """Overload, rate limit or network trouble: worth waiting and trying again."""
    msg = str(exc).lower()
    return any(
        s in msg
        for s in ("503", "unavailable", "429", "rate limit", "resource_exhausted",
                  "overloaded", "high demand", "timed out", "timeout", "connection")
    )


def _providers(provider: str) -> list[str]:
    if provider not in PROVIDERS:
        raise AIError(f"Unknown AI provider: {provider}")
    order = [provider]
    other = "openai" if provider == "gemini" else "gemini"
    if os.getenv("AI_FALLBACK", "1") != "0" and _configured(other):
        order.append(other)
    return order


def _complete(prompt: str, provider: str, as_json: bool) -> str:
    """One raw model call. Returns the reply text."""
    if provider == "gemini":
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json" if as_json else None,
            # we never use tools; this also silences the AFC warning
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        response = _get_gemini().models.generate_content(
            model=GEMINI_MODEL, contents=prompt, config=config
        )
        return response.text or ""

    kwargs = {"response_format": {"type": "json_object"}} if as_json else {}
    response = _get_openai().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return response.choices[0].message.content or ""


def _run(prompt: str, provider: str, as_json: bool, validate, retries: int):
    """Try the provider (with waits on transient errors), then the fallback."""
    last_error = None
    for prov in _providers(provider):
        for attempt in range(retries + 1):
            try:
                text = _complete(prompt, prov, as_json)
                if not as_json:
                    return text.strip()
                data = json.loads(_strip_fences(text))
                return validate(data) if validate else data
            except Exception as exc:  # noqa: BLE001 - re-raised as AIError below
                last_error = exc
                log.warning("%s call failed (attempt %s): %s", prov, attempt + 1, exc)
                if attempt < retries and _is_transient(exc):
                    time.sleep(min(1.5 * 2 ** attempt, 6))
        if prov != provider:
            break
        log.warning("Switching from %s to the fallback provider", prov)
    raise AIError(str(last_error)) from last_error


def generate_json(prompt: str, *, validate=None, retries: int = 1, provider: str = "gemini"):
    """
    Ask for JSON, parse it, and (optionally) validate/normalise it with
    `validate(data) -> data`. Transient failures wait and retry, then fall
    back to the other provider before AIError is raised.
    """
    return _run(prompt, provider, True, validate, retries)


def generate_text(prompt: str, *, provider: str = "gemini") -> str:
    return _run(prompt, provider, False, None, 1)


def ai_unavailable(what: str) -> HTTPException:
    """
    What the client sees when an AI call fails. The real error is in the server
    log; it can contain keys, prompts or provider internals, so it isn't sent.
    """
    return HTTPException(
        status_code=502,
        detail=f"{what} didn't work this time. Try again in a moment.",
    )