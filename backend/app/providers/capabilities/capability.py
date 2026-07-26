"""Capability enumeration.

Defines all supported provider capabilities as a comprehensive
enum. Capabilities represent atomic features that providers may
or may not support. The enum is designed to be forward-compatible
with emerging AI capabilities.
"""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class Capability(StrEnum):
    """Supported provider capabilities.

    Each capability represents a discrete feature that a provider
    may support. Providers declare their capabilities, and the
    Evaluation Engine queries them to determine compatibility.

    Chat and Text:
        CHAT: Basic chat completion.
        TEXT_COMPLETION: Raw text completion (non-chat).
        SYSTEM_PROMPT: System message support.
        MULTI_TURN: Multi-turn conversation support.

    Streaming:
        STREAMING: Server-sent events / streaming responses.

    Vision:
        VISION: Image input understanding.
        IMAGE_URL: Image input via URL.
        IMAGE_BASE64: Image input via base64 encoding.
        MULTI_IMAGE: Multiple image inputs per message.

    Audio:
        AUDIO_INPUT: Audio input processing.
        AUDIO_OUTPUT: Audio/speech generation.

    Video:
        VIDEO_INPUT: Video input processing.

    Structured Output:
        JSON_MODE: JSON-only response format.
        STRUCTURED_OUTPUT: Schema-constrained output.
        FUNCTION_CALLING: Legacy function calling.
        TOOL_CALLING: Tool/function calling.
        PARALLEL_TOOL_CALLS: Multiple tool calls per turn.

    Reasoning:
        REASONING: Chain-of-thought / reasoning traces.
        EXTENDED_THINKING: Deep reasoning with visible thought.
        STEP_BY_STEP: Step-by-step output.

    Context:
        LONG_CONTEXT: Extended context window (>100K tokens).
        VISION_CONTEXT: Images count toward context window.

    Generation Control:
        SEED: Deterministic generation via seed.
        LOGPROBS: Token log probabilities.
        TOP_LOGPROBS: Top-K log probabilities.
        PRESENCE_PENALTY: Presence penalty control.
        FREQUENCY_PENALTY: Frequency penalty control.
        STOP_SEQUENCES: Custom stop sequences.
        TEMPERATURE: Temperature control.
        TOP_P: Top-p (nucleus) sampling.

    Embedding:
        EMBEDDING: Text embedding generation.
        EMBEDDING_DIMENSIONS: Configurable embedding dimensions.

    Multimodal:
        MULTIMODAL: Multiple modality inputs in single request.

    Batch:
        BATCH_PROCESSING: Batch/async request support.

    Caching:
        PROMPT_CACHING: Provider-side prompt cache support.
    """

    # Chat and Text
    CHAT = "chat"
    TEXT_COMPLETION = "text_completion"
    SYSTEM_PROMPT = "system_prompt"
    MULTI_TURN = "multi_turn"

    # Streaming
    STREAMING = "streaming"

    # Vision
    VISION = "vision"
    IMAGE_URL = "image_url"
    IMAGE_BASE64 = "image_base64"
    MULTI_IMAGE = "multi_image"

    # Audio
    AUDIO_INPUT = "audio_input"
    AUDIO_OUTPUT = "audio_output"

    # Video
    VIDEO_INPUT = "video_input"

    # Structured Output
    JSON_MODE = "json_mode"
    STRUCTURED_OUTPUT = "structured_output"
    FUNCTION_CALLING = "function_calling"
    TOOL_CALLING = "tool_calling"
    PARALLEL_TOOL_CALLS = "parallel_tool_calls"

    # Reasoning
    REASONING = "reasoning"
    EXTENDED_THINKING = "extended_thinking"
    STEP_BY_STEP = "step_by_step"

    # Context
    LONG_CONTEXT = "long_context"
    VISION_CONTEXT = "vision_context"

    # Generation Control
    SEED = "seed"
    LOGPROBS = "logprobs"
    TOP_LOGPROBS = "top_logprobs"
    PRESENCE_PENALTY = "presence_penalty"
    FREQUENCY_PENALTY = "frequency_penalty"
    STOP_SEQUENCES = "stop_sequences"
    TEMPERATURE = "temperature"
    TOP_P = "top_p"

    # Embedding
    EMBEDDING = "embedding"
    EMBEDDING_DIMENSIONS = "embedding_dimensions"

    # Multimodal
    MULTIMODAL = "multimodal"

    # Batch
    BATCH_PROCESSING = "batch_processing"

    # Caching
    PROMPT_CACHING = "prompt_caching"
