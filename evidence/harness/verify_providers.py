"""Capture sanitized metadata for one real minimal request per provider adapter.

Issues a single tiny real chat request to each configured provider (OpenAI,
Anthropic, Groq), records the outcome, and writes a sanitized JSON artifact.

It never writes a credential and redacts anything resembling an API key. A
missing key, a quota/auth rejection, or any transport error is recorded as a
non-success outcome; nothing is mocked or retried into a fake success.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from app.providers.anthropic.provider import AnthropicProvider
from app.providers.groq.provider import GroqProvider
from app.providers.models.messages import Message
from app.providers.models.options import ChatOptions
from app.providers.openai.provider import OpenAIProvider

OUT = Path(__file__).resolve().parent / "provider-evidence"
OUT.mkdir(exist_ok=True)

PROMPT = "Reply with the exact token REDOPS_LIVE_SMOKE_OK."

_KEY_PATTERN = re.compile(r"(sk-[A-Za-z0-9_\-]{6,}|[A-Za-z0-9_\-]{32,})")


def _sanitize(text: str) -> str:
    return _KEY_PATTERN.sub("<redacted>", text)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _probe(name: str, provider: object, model: str, key_present: bool) -> dict:
    record: dict = {
        "provider": name,
        "model": model,
        "credential_present": key_present,
        "request_attempted": False,
        "started_at_utc": _now(),
    }
    if not key_present:
        record["outcome"] = "blocked"
        record["reason"] = "no credential configured in environment"
        return record

    record["request_attempted"] = True
    start = time.perf_counter()
    try:
        await provider.initialize()  # type: ignore[attr-defined]
        response = await provider.chat(  # type: ignore[attr-defined]
            [Message.user(PROMPT)],
            model=model,
            options=ChatOptions(temperature=0.0, max_tokens=24, timeout_seconds=30.0),
        )
        record["outcome"] = "success"
        record["finish_reason"] = getattr(response.finish_reason, "value", str(response.finish_reason))
        record["response_nonempty"] = bool(getattr(response, "content", "").strip())
        record["request_id"] = getattr(response, "request_id", None)
        usage = getattr(response, "usage", None)
        if usage is not None:
            record["tokens"] = {
                "input": usage.input_tokens,
                "output": usage.output_tokens,
                "cached": usage.cached_tokens,
                "total": usage.total_tokens,
            }
    except Exception as exc:  # noqa: BLE001
        record["outcome"] = "error"
        record["error_type"] = type(exc).__name__
        record["error_class"] = f"{type(exc).__module__}.{type(exc).__qualname__}"
        record["error_message"] = _sanitize(str(exc))[:500]
    finally:
        record["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        record["finished_at_utc"] = _now()
        try:
            await provider.dispose()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    return record


def _env_key(name: str) -> tuple[str, bool]:
    import os

    value = os.getenv(name, "").strip()
    placeholders = ("your-", "your_", "placeholder", "changeme", "xxx", "example")
    looks_fake = any(marker in value.lower() for marker in placeholders)
    return value, bool(value) and not looks_fake


async def main() -> int:
    openai_key, openai_ok = _env_key("OPENAI_API_KEY")
    anthropic_key, anthropic_ok = _env_key("ANTHROPIC_API_KEY")
    groq_key, groq_ok = _env_key("GROQ_API_KEY")

    records = []
    records.append(
        await _probe(
            "openai",
            OpenAIProvider(api_key=openai_key) if openai_key else None,  # type: ignore[arg-type]
            "gpt-4o-mini",
            openai_ok,
        )
    )
    records.append(
        await _probe(
            "anthropic",
            AnthropicProvider(api_key=anthropic_key) if anthropic_key else None,  # type: ignore[arg-type]
            "claude-sonnet-4-20250514",
            anthropic_ok,
        )
    )
    records.append(
        await _probe(
            "groq",
            GroqProvider(api_key=groq_key) if groq_key else None,  # type: ignore[arg-type]
            "llama-3.3-70b-versatile",
            groq_ok,
        )
    )

    payload = {
        "generated_at_utc": _now(),
        "note": "One real minimal chat request per adapter; credentials never recorded.",
        "prompt": PROMPT,
        "providers": records,
    }
    (OUT / "provider-metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


raise SystemExit(asyncio.run(main()))
