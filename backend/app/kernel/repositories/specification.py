"""Specification pattern for composable query building.

Specifications encapsulate query criteria into reusable objects
that can be combined with AND/OR/NOT logic. Use cases:

    class ActiveUsers(Specification[User]):
        def satisfied_by(self, user: User) -> bool:
            return user.is_active

    class AdminUsers(Specification[User]):
        def satisfied_by(self, user: User) -> bool:
            return user.role == Role.ADMIN

    combined = ActiveUsers() & AdminUsers()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Specification(ABC, Generic[T]):
    """Encapsulates a business rule that can be evaluated against an entity."""

    @abstractmethod
    def satisfied_by(self, candidate: T) -> bool:
        """Check whether the given candidate satisfies this specification.

        Args:
            candidate: The entity to evaluate.

        Returns:
            True if the candidate satisfies the specification.

        """
        ...

    def __and__(self, other: Specification[T]) -> AndSpecification[T]:
        """Combine this specification with another using logical AND."""
        return AndSpecification(self, other)

    def __or__(self, other: Specification[T]) -> OrSpecification[T]:
        """Combine this specification with another using logical OR."""
        return OrSpecification(self, other)

    def __invert__(self) -> NotSpecification[T]:
        """Negate this specification."""
        return NotSpecification(self)


class AndSpecification(Specification[T]):
    """Combines two specifications with logical AND."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def satisfied_by(self, candidate: T) -> bool:
        return self._left.satisfied_by(candidate) and self._right.satisfied_by(candidate)


class OrSpecification(Specification[T]):
    """Combines two specifications with logical OR."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def satisfied_by(self, candidate: T) -> bool:
        return self._left.satisfied_by(candidate) or self._right.satisfied_by(candidate)


class NotSpecification(Specification[T]):
    """Negates a specification."""

    def __init__(self, spec: Specification[T]) -> None:
        self._spec = spec

    def satisfied_by(self, candidate: T) -> bool:
        return not self._spec.satisfied_by(candidate)
