"""Middleware pipeline — before/after/on_error hooks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


@dataclass(frozen=True, slots=True)
class MiddlewareContext:
    """Immutable context passed to middleware.

    Attributes:
        provider_name: Provider being called.
        model_id: Model being used.
        request_id: Unique request identifier.
        metadata: Arbitrary metadata dict.

    """

    provider_name: str = ""
    model_id: str = ""
    request_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class RuntimeMiddleware[TRequest, TResponse](ABC):
    """Abstract middleware for execution pipeline.

    Implementations must be stateless or thread-safe.

    Usage:
        class LoggingMiddleware(RuntimeMiddleware):
            async def before(self, request, ctx):
                print(f"Calling {ctx.provider_name}")
                return request

            async def after(self, request, response, ctx):
                print(f"Got response from {ctx.provider_name}")
                return response

            async def on_error(self, request, error, ctx):
                print(f"Error from {ctx.provider_name}: {error}")
                raise error

    """

    @abstractmethod
    async def before(
        self,
        request: TRequest,
        ctx: MiddlewareContext,
    ) -> TRequest:
        """Pre-execution hook.

        Args:
            request: The request object.
            ctx: Middleware context.

        Returns:
            Potentially modified request.

        """

    @abstractmethod
    async def after(
        self,
        request: TRequest,
        response: TResponse,
        ctx: MiddlewareContext,
    ) -> TResponse:
        """Post-execution hook.

        Args:
            request: Original request.
            response: Execution response.
            ctx: Middleware context.

        Returns:
            Potentially modified response.

        """

    @abstractmethod
    async def on_error(
        self,
        request: TRequest,
        error: Exception,
        ctx: MiddlewareContext,
    ) -> Exception:
        """Error hook.

        Args:
            request: Original request.
            error: The exception.
            ctx: Middleware context.

        Returns:
            Potentially modified exception.

        """


class NoOpMiddleware(RuntimeMiddleware[Any, Any]):
    """No-op middleware that passes through unchanged."""

    async def before(
        self,
        request: Any,  # noqa: ANN401
        ctx: MiddlewareContext,  # noqa: ARG002
    ) -> Any:  # noqa: ANN401
        """Pass through request unchanged."""
        return request

    async def after(
        self,
        request: Any,  # noqa: ANN401, ARG002
        response: Any,  # noqa: ANN401
        ctx: MiddlewareContext,  # noqa: ARG002
    ) -> Any:  # noqa: ANN401
        """Pass through response unchanged."""
        return response

    async def on_error(
        self,
        request: Any,  # noqa: ANN401, ARG002
        error: Exception,
        ctx: MiddlewareContext,  # noqa: ARG002
    ) -> Exception:
        """Pass through error unchanged."""
        return error


@dataclass
class MiddlewarePipeline[TRequest, TResponse]:
    """Ordered pipeline of middleware.

    Usage:
        pipeline = MiddlewarePipeline()
        pipeline.add(LoggingMiddleware())
        pipeline.add(AuthMiddleware())

        result = await pipeline.execute(
            request, handler, ctx
        )

    """

    _middlewares: list[RuntimeMiddleware[TRequest, TResponse]] = field(
        default_factory=list,
    )

    def add(self, middleware: RuntimeMiddleware[TRequest, TResponse]) -> None:
        """Add middleware to pipeline."""
        self._middlewares.append(middleware)

    @property
    def count(self) -> int:
        """Return number of middleware."""
        return len(self._middlewares)

    async def execute(
        self,
        request: TRequest,
        handler: Callable[[TRequest], Awaitable[TResponse]],
        ctx: MiddlewareContext,
    ) -> TResponse:
        """Execute request through middleware pipeline.

        Args:
            request: The request to process.
            handler: The actual execution handler.
            ctx: Middleware context.

        Returns:
            The response after all middleware.

        """
        processed_request = request
        for mw in self._middlewares:
            processed_request = await mw.before(processed_request, ctx)

        try:
            response = await handler(processed_request)
        except Exception as exc:  # noqa: BLE001
            current_error = exc
            for mw in reversed(self._middlewares):
                current_error = await mw.on_error(processed_request, current_error, ctx)
            raise current_error from None

        final_response = response
        for mw in reversed(self._middlewares):
            final_response = await mw.after(processed_request, final_response, ctx)

        return final_response
