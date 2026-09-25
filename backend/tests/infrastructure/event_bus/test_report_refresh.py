"""Tests for ReportRefreshService and ReportRefreshSubscriber."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.analytics.services.report_refresh_service import ReportRefreshService
from app.infrastructure.event_bus.subscribers.report_refresh_subscriber import (
    ReportRefreshSubscriber,
)
from app.kernel.entities.base import UUIDv7


class TestReportRefreshService:
    def test_invalidate_records_entry(self) -> None:
        service = ReportRefreshService()
        service.invalidate("evaluation", "eval-1", "test reason")

        assert service.is_stale("evaluation", "eval-1") is True

    def test_is_stale_returns_false_when_not_invalidated(self) -> None:
        service = ReportRefreshService()
        assert service.is_stale("evaluation", "eval-2") is False

    def test_is_stale_returns_false_for_different_entity(self) -> None:
        service = ReportRefreshService()
        service.invalidate("evaluation", "eval-1", "reason")
        assert service.is_stale("evaluation", "eval-2") is False
        assert service.is_stale("attack_run", "eval-1") is False

    def test_get_invalidations_returns_all(self) -> None:
        service = ReportRefreshService()
        service.invalidate("evaluation", "eval-1", "reason 1")
        service.invalidate("attack_run", "ar-1", "reason 2")

        all_entries = service.get_invalidations()
        assert len(all_entries) == 2

    def test_get_invalidations_filters_by_type(self) -> None:
        service = ReportRefreshService()
        service.invalidate("evaluation", "eval-1", "reason 1")
        service.invalidate("attack_run", "ar-1", "reason 2")

        eval_entries = service.get_invalidations(entity_type="evaluation")
        assert len(eval_entries) == 1
        assert eval_entries[0].entity_id == "eval-1"

    def test_get_invalidations_filters_by_time(self) -> None:
        service = ReportRefreshService()
        service.invalidate("evaluation", "eval-1", "reason")

        future = datetime(2099, 1, 1, tzinfo=UTC)
        entries = service.get_invalidations(since=future)
        assert len(entries) == 0

    def test_clear_removes_all(self) -> None:
        service = ReportRefreshService()
        service.invalidate("evaluation", "eval-1", "r1")
        service.invalidate("evaluation", "eval-2", "r2")

        removed = service.clear()
        assert removed == 2
        assert service.get_invalidations() == []

    def test_clear_removes_by_type(self) -> None:
        service = ReportRefreshService()
        service.invalidate("evaluation", "eval-1", "r1")
        service.invalidate("attack_run", "ar-1", "r2")

        removed = service.clear(entity_type="evaluation")
        assert removed == 1
        remaining = service.get_invalidations()
        assert len(remaining) == 1
        assert remaining[0].entity_type == "attack_run"

    def test_clear_removes_by_id(self) -> None:
        service = ReportRefreshService()
        service.invalidate("evaluation", "eval-1", "r1")
        service.invalidate("evaluation", "eval-2", "r2")

        removed = service.clear(entity_id="eval-1")
        assert removed == 1
        remaining = service.get_invalidations()
        assert len(remaining) == 1
        assert remaining[0].entity_id == "eval-2"


@dataclass(frozen=True, slots=True)
class _FakeEvaluationCompletedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    items_completed: int = 10
    items_total: int = 10
    duration_ms: int = 5000

    @property
    def event_type(self) -> str:
        return "evaluation.completed"


@dataclass(frozen=True, slots=True)
class _FakeFindingDetectedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    finding_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    campaign_id: str = "camp-xyz"
    attack_category: str = "prompt_injection"
    severity: str = "high"
    verdict: str = "fail"

    @property
    def event_type(self) -> str:
        return "safety.finding.detected"


class TestReportRefreshSubscriber:
    def test_invalidates_on_completed_event(self) -> None:
        service = ReportRefreshService()
        subscriber = ReportRefreshSubscriber(service)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        assert service.is_stale("evaluation", str(event.run_id))

    def test_invalidates_on_finding_detected(self) -> None:
        service = ReportRefreshService()
        subscriber = ReportRefreshSubscriber(service)
        event = _FakeFindingDetectedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        assert service.is_stale("finding", str(event.finding_id))

    def test_skips_unmapped_event(self) -> None:
        service = ReportRefreshService()
        subscriber = ReportRefreshSubscriber(service)

        @dataclass(frozen=True, slots=True)
        class _Unmapped:
            event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
            occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
            correlation_id: str | None = None

            @property
            def event_type(self) -> str:
                return "evaluation.item.started"

        import asyncio

        asyncio.run(subscriber.handle(_Unmapped()))

        assert service.get_invalidations() == []

    def test_skips_event_without_event_type(self) -> None:
        service = ReportRefreshService()
        subscriber = ReportRefreshSubscriber(service)

        import asyncio

        asyncio.run(subscriber.handle(None))

        assert service.get_invalidations() == []
