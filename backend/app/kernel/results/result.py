from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from app.kernel.exceptions.errors import BaseError

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E", bound=BaseError)
F = TypeVar("F", bound=BaseError)


@dataclass(frozen=True)
class Success(Generic[T]):
    value: T


@dataclass(frozen=True)
class Failure(Generic[E]):
    error: E


Result = Success[T] | Failure[E]


def success(value: T) -> Success[T]:
    return Success(value=value)


def failure(error: E) -> Failure[E]:
    return Failure(error=error)


def is_success(result: Result[T, E]) -> bool:
    return isinstance(result, Success)


def is_failure(result: Result[T, E]) -> bool:
    return isinstance(result, Failure)


def unwrap(result: Result[T, E]) -> T:
    match result:
        case Success(value):
            return value
        case Failure(error):
            raise error


def unwrap_or(result: Result[T, E], default: T) -> T:
    match result:
        case Success(value):
            return value
        case Failure():
            return default


def map(result: Result[T, E], fn: Callable[[T], U]) -> Result[U, E]:
    match result:
        case Success(value):
            return success(fn(value))
        case Failure():
            return result


def bind(result: Result[T, E], fn: Callable[[T], Result[U, F]]) -> Result[U, E | F]:
    match result:
        case Success(value):
            return fn(value)
        case Failure():
            return result
