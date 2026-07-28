from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto


class LifecycleState(Enum):
    INITIALIZED = auto()
    STARTED = auto()
    STOPPED = auto()
    DISPOSED = auto()
    FAILED = auto()


class LifecycleService(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def dispose(self) -> None: ...

    @abstractmethod
    async def health(self) -> bool: ...


class LifecycleManager:
    def __init__(self) -> None:
        self._services: dict[str, LifecycleService] = {}
        self._states: dict[str, LifecycleState] = {}

    def register(self, name: str, service: LifecycleService) -> None:
        self._services[name] = service
        self._states[name] = LifecycleState.INITIALIZED

    def unregister(self, name: str) -> None:
        self._services.pop(name, None)
        self._states.pop(name, None)

    def get_state(self, name: str) -> LifecycleState | None:
        return self._states.get(name)

    async def initialize_all(self) -> list[tuple[str, bool]]:
        results: list[tuple[str, bool]] = []
        for name, service in self._services.items():
            try:
                await service.initialize()
                self._states[name] = LifecycleState.INITIALIZED
                results.append((name, True))
            except Exception:
                self._states[name] = LifecycleState.FAILED
                results.append((name, False))
        return results

    async def start_all(self) -> list[tuple[str, bool]]:
        results: list[tuple[str, bool]] = []
        for name, service in self._services.items():
            try:
                await service.start()
                self._states[name] = LifecycleState.STARTED
                results.append((name, True))
            except Exception:
                self._states[name] = LifecycleState.FAILED
                results.append((name, False))
        return results

    async def stop_all(self) -> list[tuple[str, bool]]:
        results: list[tuple[str, bool]] = []
        for name, service in reversed(list(self._services.items())):
            try:
                await service.stop()
                self._states[name] = LifecycleState.STOPPED
                results.append((name, True))
            except Exception:
                results.append((name, False))
        return results

    async def dispose_all(self) -> list[tuple[str, bool]]:
        results: list[tuple[str, bool]] = []
        for name, service in reversed(list(self._services.items())):
            try:
                await service.dispose()
                self._states[name] = LifecycleState.DISPOSED
                results.append((name, True))
            except Exception:
                results.append((name, False))
        return results

    async def health_report(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for name, service in self._services.items():
            try:
                result[name] = await service.health()
            except Exception:
                result[name] = False
        return result

    def get_service(self, name: str) -> LifecycleService | None:
        return self._services.get(name)
