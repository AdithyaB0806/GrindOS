"""
Backend/ai.py

One place for every model call, so model names, API keys, retries, timeouts,
fallback and error handling live here instead of being copied into each router.

Two providers:
  "gemini"  - Google Gemini
  "openai"  - any OpenAI-compatible API (Groq by default, or real OpenAI)

Failover: if a call to one provider fails for ANY reason (overload, rate limit,
timeout, bad key, empty or unusable reply), the same prompt goes straight to the
other provider, as long as that one has a key. Only when both have failed does it
wait (if the error looked temporary) and start another round.
Turn failover off with AI_FALLBACK=0. Per-call timeout: AI_TIMEOUT (seconds).
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

AI_TIMEOUT = float(os.getenv("AI_TIMEOUT", "45"))  # seconds, per model call

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
            http_options=types.HttpOptions(timeout=int(AI_TIMEOUT * 1000)),  # milliseconds
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
        _openai_client = OpenAI(api_key=key, base_url=base_url, timeout=AI_TIMEOUT)  # seconds
    return _openai_client


def _strip_fences(text: str) -> str:
    text = (text or "").strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S | re.I)
    return match.group(1) if match else text


def _is_transient(exc: Exception) -> bool:
    """Overload, rate limit or network trouble: worth waiting before the next round."""
    msg = str(exc).lower()
    return any(
        s in msg
        for s in ("503", "unavailable", "429", "rate limit", "resource_exhausted",
                  "overloaded", "high demand", "timed out", "timeout", "connection")
    )


def _providers(provider: str) -> list[str]:
    """
    Providers to try, in order: the requested one first, then the other one if
    failover is on. A provider with no API key is left out, so a missing key on
    the primary goes straight to the other instead of failing.
    """
    if provider not in PROVIDERS:
        raise AIError(f"Unknown AI provider: {provider}")
    other = "openai" if provider == "gemini" else "gemini"
    order = [provider]
    if os.getenv("AI_FALLBACK", "1") != "0":
        order.append(other)
    order = [p for p in order if _configured(p)]
    if not order:
        raise AIError(f"No API key is configured for '{provider}' (or its fallback)")
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
    """
    Round 1: try each provider once, the next one immediately after a failure.
    If every provider failed and the error looked temporary, wait and run another
    round (up to `retries` more). With only one provider configured this is a
    plain retry loop.
    """
    order = _providers(provider)
    last_error = None

    for round_ in range(retries + 1):
        for prov in order:
            try:
                text = _complete(prompt, prov, as_json)
                if as_json:
                    data = json.loads(_strip_fences(text))
                    result = validate(data) if validate else data
                else:
                    result = text.strip()
                    if not result:
                        raise ValueError("empty reply")
                if prov != provider:
                    log.info("Answered by fallback provider %s", prov)
                return result
            except Exception as exc:  # noqa: BLE001 - re-raised as AIError below
                last_error = exc
                log.warning("%s call failed (round %s): %s", prov, round_ + 1, exc)
                # loop continues: the next provider gets the prompt right away

        if round_ < retries and _is_transient(last_error):
            time.sleep(min(1.5 * 2 ** round_, 6))

    raise AIError(str(last_error)) from last_error


def generate_json(prompt: str, *, validate=None, retries: int = 1, provider: str = "gemini"):
    """
    Ask for JSON, parse it, and (optionally) validate/normalise it with
    `validate(data) -> data`. If the provider fails or its reply is unusable, the
    other provider is tried straight away; AIError is raised only when both fail.
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