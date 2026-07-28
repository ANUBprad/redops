"""Token counter abstraction.

Defines the interface for tokenization implementations.
Concrete tokenizers (tiktoken, sentencepiece, etc.) are
injected at runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TokenCounter(ABC):
    """Abstract token counter.

    Implementations provide model-specific token counting.
    The framework never depends on a specific tokenizer;
    implementations are injected via the DI container.
    """

    @abstractmethod
    def count_tokens(self, text: str, model: str | None = None) -> int:
        """Count tokens in the given text.

        Args:
            text: The text to tokenize.
            model: Optional model hint for model-specific tokenization.

        Returns:
            The number of tokens.

        """

    @abstractmethod
    def count_messages(self, messages: list[dict[str, str]], model: str | None = None) -> int:
        """Count tokens in a list of messages.

        Args:
            messages: Messages in dict format with 'role' and 'content'.
            model: Optional model hint.

        Returns:
            The total token count across all messages.

        """
