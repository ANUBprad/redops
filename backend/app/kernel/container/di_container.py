from __future__ import annotations

import contextlib
from collections.abc import Callable
from enum import Enum, auto
from threading import Lock
from typing import Any, Generic, TypeVar

from app.kernel.exceptions.errors import DependencyError

T = TypeVar("T")

Factory = Callable[..., T]


class Lifetime(Enum):
    SINGLETON = auto()
    SCOPED = auto()
    TRANSIENT = auto()


class Registration(Generic[T]):
    def __init__(self, factory: Factory[T], lifetime: Lifetime) -> None:
        self.factory = factory
        self.lifetime = lifetime
        self._instance: T | None = None

    def resolve(self, container: DIContainer) -> T:
        if self.lifetime is Lifetime.SINGLETON:
            if self._instance is None:
                self._instance = self.factory(container)
            return self._instance

        if self.lifetime is Lifetime.SCOPED:
            return self.factory(container)

        return self.factory(container)

    def dispose(self) -> None:
        if self._instance is not None and hasattr(self._instance, "dispose"):
            self._instance.dispose()
        self._instance = None


class Scope:
    def __init__(self) -> None:
        self._instances: dict[type[Any], Any] = {}
        self._lock = Lock()

    def get_or_create(self, key: type[T], factory: Callable[[], T]) -> T:
        with self._lock:
            if key not in self._instances:
                self._instances[key] = factory()
            result: T = self._instances[key]
            return result

    @contextlib.contextmanager
    def __call__(self) -> Any:
        try:
            yield self
        finally:
            self._instances.clear()


class DIContainer:
    def __init__(self) -> None:
        self._registrations: dict[type[Any], Registration[Any]] = {}
        self._resolution_stack: list[type[Any]] = []
        self._lock = Lock()

    def register(
        self,
        type_: type[T],
        factory: Factory[T],
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> None:
        with self._lock:
            self._registrations[type_] = Registration(factory, lifetime)

    def register_singleton(self, type_: type[T], factory: Factory[T]) -> None:
        self.register(type_, factory, Lifetime.SINGLETON)

    def register_factory(self, type_: type[T], factory: Factory[T]) -> None:
        self.register(type_, factory, Lifetime.TRANSIENT)

    def resolve(self, type_: type[T], scope: Scope | None = None) -> T:
        if type_ in self._resolution_stack:
            raise DependencyError(
                f"Circular dependency detected for {type_.__name__}",
                dependency_name=type_.__name__,
                details={"resolution_stack": [t.__name__ for t in self._resolution_stack]},
            )

        registration = self._registrations.get(type_)
        if registration is None:
            raise DependencyError(
                f"No registration found for {type_.__name__}",
                dependency_name=type_.__name__,
            )

        if registration.lifetime is Lifetime.SCOPED:
            if scope is None:
                raise DependencyError(
                    f"Cannot resolve scoped service {type_.__name__} without a Scope",
                    dependency_name=type_.__name__,
                )
            self._resolution_stack.append(type_)
            try:
                return scope.get_or_create(type_, lambda: registration.factory(self))
            finally:
                self._resolution_stack.pop()

        self._resolution_stack.append(type_)
        try:
            result: T = registration.resolve(self)
            return result
        finally:
            self._resolution_stack.pop()

    def is_registered(self, type_: type[Any]) -> bool:
        return type_ in self._registrations

    def clear(self) -> None:
        with self._lock:
            for reg in self._registrations.values():
                reg.dispose()
            self._registrations.clear()

    def dispose(self) -> None:
        with self._lock:
            for reg in self._registrations.values():
                reg.dispose()
            self._registrations.clear()
