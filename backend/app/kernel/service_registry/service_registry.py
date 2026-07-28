from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.kernel.lifecycle.lifecycle import LifecycleService


@dataclass
class ServiceEntry:
    name: str
    instance: LifecycleService
    depends_on: list[str] = field(default_factory=list)
    healthy: bool = False


class ServiceRegistry:
    def __init__(self) -> None:
        self._services: dict[str, ServiceEntry] = {}

    def register(
        self,
        name: str,
        instance: LifecycleService,
        *,
        depends_on: list[str] | None = None,
    ) -> None:
        if name in self._services:
            raise ValueError(f"Service '{name}' is already registered")
        self._services[name] = ServiceEntry(
            name=name,
            instance=instance,
            depends_on=depends_on or [],
        )

    def unregister(self, name: str) -> None:
        self._services.pop(name, None)

    async def start_all(self) -> None:
        order = self._resolve_start_order()
        for name in order:
            entry = self._services[name]
            try:
                await entry.instance.start()
                entry.healthy = True
            except Exception:
                entry.healthy = False

    async def stop_all(self) -> None:
        order = self._resolve_start_order()
        for name in reversed(order):
            entry = self._services.get(name)
            if entry is None:
                continue
            try:
                await entry.instance.stop()
                entry.healthy = False
            except Exception:
                pass

    async def check_health(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for name, entry in self._services.items():
            try:
                result[name] = await entry.instance.health()
            except Exception:
                result[name] = False
        return result

    async def health_report(self) -> dict[str, Any]:
        report: dict[str, Any] = {}
        for name, entry in self._services.items():
            try:
                healthy = await entry.instance.health()
                report[name] = {"healthy": healthy, "status": "healthy" if healthy else "degraded"}
            except Exception:
                report[name] = {"healthy": False, "status": "unhealthy"}
        return report

    def get_service(self, name: str) -> LifecycleService | None:
        entry = self._services.get(name)
        return entry.instance if entry is not None else None

    def is_healthy(self, name: str) -> bool:
        entry = self._services.get(name)
        return entry.healthy if entry is not None else False

    def _resolve_start_order(self) -> list[str]:
        graph: dict[str, set[str]] = {}
        for name, entry in self._services.items():
            graph[name] = set(entry.depends_on)

        in_degree: dict[str, int] = dict.fromkeys(graph, 0)
        for name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] = in_degree.get(name, 0) + 1

        queue: list[str] = [name for name, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            name = queue.pop(0)
            order.append(name)
            for other, deps in graph.items():
                if name in deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        if len(order) != len(self._services):
            raise ValueError("Circular dependency detected in service graph")

        return order
