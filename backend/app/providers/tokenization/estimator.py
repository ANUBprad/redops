"""Token estimator.

Provides fast, heuristic-based token estimation without
a real tokenizer. Useful for cost estimation and context
window checks when no tokenizer is available.
"""

from __future__ import annotations

from app.providers.tokenization.counter import TokenCounter


class TokenEstimator(TokenCounter):
    """Heuristic-based token estimator.

    Uses a simple characters-per-token ratio to estimate
    token counts. Not accurate for production use, but
    sufficient for cost estimation and context checks.

    The default ratio is ~4 characters per token, which
    approximates English text in most models.
    """

    DEFAULT_CHARS_PER_TOKEN: float = 4.0

    def __init__(self, chars_per_token: float = DEFAULT_CHARS_PER_TOKEN) -> None:
        """Initialize with configurable ratio.

        Args:
            chars_per_token: Average characters per token.

        """
        self._chars_per_token = chars_per_token

    def count_tokens(self, text: str, model: str | None = None) -> int:
        """Estimate token count using character ratio.

        Args:
            text: The text to estimate.
            model: Ignored (estimator is model-agnostic).

        Returns:
            Estimated token count.

        """
        return max(1, int(len(text) / self._chars_per_token))

    def count_messages(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> int:
        """Estimate token count across messages.

        Adds overhead per message (~4 tokens for role/formatting).

        Args:
            messages: Messages to estimate.
            model: Ignored.

        Returns:
            Estimated total token count.

        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += self.count_tokens(content, model)
            total += 4  # Overhead for role and formatting
        return total
