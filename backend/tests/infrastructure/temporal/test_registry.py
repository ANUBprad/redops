"""Tests for ActivityRegistry and WorkflowRegistry."""

from __future__ import annotations

from typing import Any

from app.infrastructure.temporal.worker import ActivityRegistry, WorkflowRegistry


async def _dummy_activity() -> str:
    return "done"


class _DummyWorkflow:
    @staticmethod
    async def run() -> str:
        return "done"


class TestActivityRegistry:
    def test_register_and_get_all(self) -> None:
        registry = ActivityRegistry()
        registry.register(_dummy_activity)
        activities = registry.get_all()
        assert _dummy_activity in activities
        assert registry.count == 1

    def test_register_with_custom_name(self) -> None:
        registry = ActivityRegistry()
        registry.register(_dummy_activity, name="custom_activity")
        activities = registry.get_all()
        assert _dummy_activity in activities
        assert registry.count == 1

    def test_unregister(self) -> None:
        registry = ActivityRegistry()
        registry.register(_dummy_activity)
        registry.unregister(_dummy_activity.__name__)
        assert registry.count == 0

    def test_unregister_nonexistent(self) -> None:
        registry = ActivityRegistry()
        registry.unregister("nonexistent")
        assert registry.count == 0


class TestWorkflowRegistry:
    def test_register_and_get_all(self) -> None:
        registry = WorkflowRegistry()
        registry.register(_DummyWorkflow)
        workflows = registry.get_all()
        assert _DummyWorkflow in workflows
        assert registry.count == 1

    def test_unregister(self) -> None:
        registry = WorkflowRegistry()
        registry.register(_DummyWorkflow)
        registry.unregister(_DummyWorkflow.__name__)
        assert registry.count == 0
