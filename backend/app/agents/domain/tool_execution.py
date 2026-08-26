"""Tool execution boundary for agent trajectories.

Provides a safe, deterministic interface for registering and executing
tools during agent execution. Tools are pure functions that accept
JSON arguments and return string results. The registry enforces
structural correctness before execution.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


class ToolFunction(Protocol):
    """Protocol for a registered tool function."""

    def __call__(self, **kwargs: Any) -> str: ...


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Declarative definition of an agent tool.

    Follows the OpenAI function-calling schema format for
    interoperability with provider APIs.
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30
    is_deterministic: bool = True

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Result of executing a tool."""

    tool_name: str
    result: str
    is_error: bool = False
    latency_ms: int = 0
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return not self.is_error and self.error is None


class ToolRegistry:
    """Registry of available agent tools.

    Maintains a mapping of tool names to their definitions and
    callable implementations. Provides validation and schema
    generation for provider API integration.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._functions: dict[str, Callable[..., str]] = {}

    def register(
        self,
        definition: ToolDefinition,
        func: Callable[..., str],
    ) -> None:
        """Register a tool with its definition and implementation."""
        if definition.name in self._tools:
            msg = f"Tool '{definition.name}' is already registered"
            raise ToolRegistrationError(msg, tool_name=definition.name)
        if not callable(func):
            msg = f"Tool function for '{definition.name}' must be callable"
            raise ToolRegistrationError(msg, tool_name=definition.name)
        self._tools[definition.name] = definition
        self._functions[definition.name] = func

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)
        self._functions.pop(name, None)

    def get_definition(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_function(self, name: str) -> Callable[..., str] | None:
        return self._functions.get(name)

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())

    def list_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools.keys()))

    def get_openai_schemas(self) -> tuple[dict[str, Any], ...]:
        """Return OpenAI function-calling schemas for all registered tools."""
        return tuple(t.to_openai_schema() for t in self._tools.values())

    def validate_tool_args(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str | None:
        """Validate tool arguments against the definition's schema.

        Returns None if valid, or an error message if invalid.
        """
        definition = self._tools.get(tool_name)
        if definition is None:
            return f"Unknown tool: {tool_name}"

        required = definition.parameters.get("required", [])
        properties = definition.parameters.get("properties", {})

        for field_name in required:
            if field_name not in arguments:
                return f"Missing required argument: {field_name}"

        for key in arguments:
            if key not in properties and key != "additionalProperties":
                pass  # Allow extra arguments per OpenAI convention

        return None

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


class SafeToolExecutor:
    """Executes tools safely with argument validation and timeout tracking.

    Wraps tool function calls to ensure deterministic behavior:
    validates arguments, measures latency, catches exceptions, and
    returns structured results.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a tool with validation and error handling."""
        validation_error = self._registry.validate_tool_args(tool_name, arguments)
        if validation_error is not None:
            return ToolExecutionResult(
                tool_name=tool_name,
                result="",
                is_error=True,
                error=validation_error,
            )

        func = self._registry.get_function(tool_name)
        if func is None:
            return ToolExecutionResult(
                tool_name=tool_name,
                result="",
                is_error=True,
                error=f"Tool function not found: {tool_name}",
            )

        start = time.monotonic()
        try:
            result = func(**arguments)
            elapsed = int((time.monotonic() - start) * 1000)
            return ToolExecutionResult(
                tool_name=tool_name,
                result=str(result),
                latency_ms=elapsed,
            )
        except ToolExecutionTimeoutError as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return ToolExecutionResult(
                tool_name=tool_name,
                result="",
                is_error=True,
                latency_ms=elapsed,
                error=f"Tool execution timed out: {exc}",
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return ToolExecutionResult(
                tool_name=tool_name,
                result="",
                is_error=True,
                latency_ms=elapsed,
                error=f"Tool execution failed: {exc}",
            )

    async def execute_async(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Async wrapper for tool execution."""
        return self.execute(tool_name, arguments)


class ToolRegistrationError(Exception):
    """Raised when tool registration fails."""

    def __init__(self, message: str = "", *, tool_name: str = "") -> None:
        self.tool_name = tool_name
        super().__init__(message)


class ToolExecutionTimeoutError(Exception):
    """Raised when a tool execution exceeds its timeout."""
