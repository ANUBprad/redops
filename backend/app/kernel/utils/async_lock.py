from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager


class AsyncLock(ABC):
    @abstractmethod
    async def acquire(self) -> None: ...

    @abstractmethod
    def release(self) -> None: ...

    @abstractmethod
    def locked(self) -> AbstractAsyncContextManager[None]: ...


class AsyncioLock(AsyncLock):
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        await self._lock.acquire()

    def release(self) -> None:
        self._lock.release()

    @asynccontextmanager
    async def locked(self) -> AsyncGenerator[None, None]:
        async with self._lock:
            yield
