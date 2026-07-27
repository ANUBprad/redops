"""Tests for middleware pipeline."""

import pytest

from app.providers.runtime.middleware.middleware_pipeline import (
    MiddlewareContext,
    MiddlewarePipeline,
    NoOpMiddleware,
    RuntimeMiddleware,
)


class RecordingMiddleware(RuntimeMiddleware[str, str]):
    """Middleware that records calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[str] = []

    async def before(self, request: str, ctx: MiddlewareContext) -> str:
        self.calls.append(f"before:{self.name}")
        return f"{request}+{self.name}"

    async def after(self, request: str, response: str, ctx: MiddlewareContext) -> str:
        self.calls.append(f"after:{self.name}")
        return f"{response}+{self.name}"

    async def on_error(self, request: str, error: Exception, ctx: MiddlewareContext) -> Exception:
        self.calls.append(f"error:{self.name}")
        return error


class FailingMiddleware(RuntimeMiddleware[str, str]):
    """Middleware that raises in before."""

    async def before(self, request: str, ctx: MiddlewareContext) -> str:
        raise RuntimeError("middleware failure")

    async def after(self, request: str, response: str, ctx: MiddlewareContext) -> str:
        return response

    async def on_error(self, request: str, error: Exception, ctx: MiddlewareContext) -> Exception:
        return error


class TestMiddlewarePipeline:
    """Tests for MiddlewarePipeline."""

    @pytest.mark.asyncio
    async def test_noop_middleware(self) -> None:
        mw = NoOpMiddleware()
        ctx = MiddlewareContext()
        result = await mw.before("req", ctx)
        assert result == "req"
        result = await mw.after("req", "res", ctx)
        assert result == "res"

    @pytest.mark.asyncio
    async def test_empty_pipeline(self) -> None:
        pipeline = MiddlewarePipeline[str, str]()
        ctx = MiddlewareContext(request_id="1")

        async def handler(r: str) -> str:
            return r + ":done"

        result = await pipeline.execute("req", handler, ctx)
        assert result == "req:done"

    @pytest.mark.asyncio
    async def test_before_hooks_applied(self) -> None:
        pipeline = MiddlewarePipeline[str, str]()
        pipeline.add(RecordingMiddleware("A"))
        pipeline.add(RecordingMiddleware("B"))
        ctx = MiddlewareContext()

        async def handler(r: str) -> str:
            return f"response({r})"

        result = await pipeline.execute("start", handler, ctx)
        assert "response(start+A+B)" in result

    @pytest.mark.asyncio
    async def test_after_hooks_applied(self) -> None:
        mw_a = RecordingMiddleware("A")
        mw_b = RecordingMiddleware("B")
        pipeline = MiddlewarePipeline[str, str]()
        pipeline.add(mw_a)
        pipeline.add(mw_b)
        ctx = MiddlewareContext()

        async def handler(r: str) -> str:
            return "resp"

        await pipeline.execute("req", handler, ctx)
        assert "after:A" in mw_a.calls
        assert "after:B" in mw_b.calls

    @pytest.mark.asyncio
    async def test_error_hooks_called(self) -> None:
        mw = RecordingMiddleware("X")
        pipeline = MiddlewarePipeline[str, str]()
        pipeline.add(mw)

        async def handler(r: str) -> str:
            raise ValueError("test error")

        ctx = MiddlewareContext()
        with pytest.raises(ValueError, match="test error"):
            await pipeline.execute("req", handler, ctx)
        assert "error:X" in mw.calls

    @pytest.mark.asyncio
    async def test_error_in_before(self) -> None:
        pipeline = MiddlewarePipeline[str, str]()
        pipeline.add(FailingMiddleware())
        ctx = MiddlewareContext()

        async def handler(r: str) -> str:
            return "ok"

        with pytest.raises(RuntimeError, match="middleware failure"):
            await pipeline.execute("req", handler, ctx)

    @pytest.mark.asyncio
    async def test_count(self) -> None:
        pipeline = MiddlewarePipeline[str, str]()
        assert pipeline.count == 0
        pipeline.add(NoOpMiddleware())
        assert pipeline.count == 1
