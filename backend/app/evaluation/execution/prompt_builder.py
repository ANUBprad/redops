"""Prompt building for evaluation item execution.

Converts a dataset item into the exact messages sent to a
provider. Supports a system prompt plus a prompt template
with ``{variable}`` placeholders rendered from item fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from app.evaluation.data.dataset import DatasetItem
    from app.providers.models.messages import Message

__all__ = [
    "PromptBuildError",
    "PromptTemplate",
    "render_prompt",
]

_PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_prompt(template: str, variables: Mapping[str, str]) -> str:
    """Render a prompt template with the given variables.

    Unknown placeholders raise PromptBuildError so typos are
    caught at build time rather than silently reaching providers.

    Args:
        template: The template string containing ``{name}`` placeholders.
        variables: Mapping of variable name to value.

    Returns:
        The rendered prompt.

    Raises:
        PromptBuildError: If the template references an unknown variable.

    """

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        try:
            return variables[key]
        except KeyError:
            msg = f"Unknown template variable '{{{key}}}'"
            raise PromptBuildError(msg) from None

    return _PLACEHOLDER_PATTERN.sub(_replace, template)


class PromptBuildError(ValueError):
    """Raised when a prompt cannot be built for an item."""


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """A system prompt plus item template used to build messages.

    Attributes:
        template: The item template with ``{variable}`` placeholders.
        system_prompt: Optional system message content.

    """

    template: str
    system_prompt: str | None = None

    def render(self, item: DatasetItem) -> str:
        """Render the template for a dataset item.

        Args:
            item: The dataset item providing variables.

        Returns:
            The rendered user prompt.

        """
        return render_prompt(self.template, item.to_variables())

    def render_variables(self, variables: Mapping[str, str]) -> str:
        """Render the template with an explicit variable mapping.

        Args:
            variables: Mapping of variable name to value.

        Returns:
            The rendered user prompt.

        """
        return render_prompt(self.template, variables)

    def build_messages(self, item: DatasetItem) -> list[Message]:
        """Build the message list sent to a provider.

        Args:
            item: The dataset item to build messages for.

        Returns:
            A system message (if configured) followed by the user
            message containing the rendered prompt.

        """
        from app.providers.models.messages import Message

        messages: list[Message] = []
        if self.system_prompt:
            messages.append(Message.system(self.system_prompt))
        messages.append(Message.user(self.render(item)))
        return messages
