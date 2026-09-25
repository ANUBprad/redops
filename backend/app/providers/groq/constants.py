"""Groq provider constants.

Groq exposes an OpenAI-compatible API. The client, request/response mappers,
streaming, and tool-calling logic used by the OpenAI provider work unchanged
against Groq's endpoint; only the base URL, provider identity, capabilities,
and model catalog differ.
"""

from __future__ import annotations

PROVIDER_NAME = "groq"

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"

# Representative Groq models. Groq hosts Llama, Mixtral, GEMMA, and OpenAI
# Codex models. The list is informational (the API accepts any model id the
# account has access to); cost entries in `providers.cost.defaults` cover the
# default set evaluated by the platform.
GROQ_MODELS: tuple[str, ...] = (
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-3.2-3b-preview",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "openai/gpt-oss-120b",
)
