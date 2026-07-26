"""Tests for token accounting."""

from __future__ import annotations

from app.providers.tokenization.counter import TokenCounter
from app.providers.tokenization.estimator import TokenEstimator
from app.providers.tokenization.report import UsageReport
from app.providers.tokenization.usage import TokenUsage


class TestTokenUsage:
    """Tests for TokenUsage."""

    def test_defaults(self) -> None:
        u = TokenUsage()
        assert u.total_tokens == 0
        assert u.billable_tokens == 0

    def test_total_tokens(self) -> None:
        u = TokenUsage(input_tokens=100, output_tokens=50)
        assert u.total_tokens == 150

    def test_billable_tokens(self) -> None:
        u = TokenUsage(input_tokens=100, output_tokens=50, cached_tokens=20)
        assert u.billable_tokens == 130

    def test_add(self) -> None:
        u1 = TokenUsage(input_tokens=100, output_tokens=50)
        u2 = TokenUsage(input_tokens=200, output_tokens=30)
        result = u1.add(u2)
        assert result.input_tokens == 300
        assert result.output_tokens == 80

    def test_add_preserves_metadata(self) -> None:
        u1 = TokenUsage(metadata={"key": "val1"})
        u2 = TokenUsage(metadata={"key2": "val2"})
        result = u1.add(u2)
        assert result.metadata["key"] == "val1"
        assert result.metadata["key2"] == "val2"

    def test_repr(self) -> None:
        u = TokenUsage(input_tokens=10, output_tokens=5)
        assert "10" in repr(u)
        assert "5" in repr(u)


class TestTokenEstimator:
    """Tests for TokenEstimator."""

    def test_estimate_tokens(self) -> None:
        est = TokenEstimator()
        count = est.count_tokens("hello world")
        assert count > 0

    def test_estimate_empty(self) -> None:
        est = TokenEstimator()
        count = est.count_tokens("")
        assert count >= 1

    def test_custom_ratio(self) -> None:
        est = TokenEstimator(chars_per_token=2.0)
        count = est.count_tokens("hello")
        assert count == 2  # 5 chars / 2 = 2

    def test_estimate_messages(self) -> None:
        est = TokenEstimator()
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        count = est.count_messages(messages)
        assert count > 0


class TestUsageReport:
    """Tests for UsageReport."""

    def test_defaults(self) -> None:
        r = UsageReport()
        assert r.total_tokens == 0
        assert r.average_input_tokens == 0.0
        assert r.cache_hit_ratio == 0.0

    def test_total_tokens(self) -> None:
        r = UsageReport(total_input_tokens=100, total_output_tokens=50)
        assert r.total_tokens == 150

    def test_average_input_tokens(self) -> None:
        r = UsageReport(total_input_tokens=100, total_requests=10)
        assert r.average_input_tokens == 10.0

    def test_average_output_tokens(self) -> None:
        r = UsageReport(total_output_tokens=50, total_requests=10)
        assert r.average_output_tokens == 5.0

    def test_cache_hit_ratio(self) -> None:
        r = UsageReport(total_input_tokens=100, total_cached_tokens=30)
        assert r.cache_hit_ratio == 0.3

    def test_repr(self) -> None:
        r = UsageReport(total_requests=5, total_cost_usd=0.1234)
        assert "5" in repr(r)
        assert "0.1234" in repr(r)
