"""Tests for correlation ID management."""

from __future__ import annotations

from app.infrastructure.observability.correlation import (
    get_correlation_id,
    get_request_id,
    reset_context,
    set_correlation_id,
    set_request_id,
)


class TestCorrelationId:
    def teardown_method(self) -> None:
        reset_context()

    def test_default_is_empty(self) -> None:
        assert get_correlation_id() == ""

    def test_set_and_get(self) -> None:
        cid = set_correlation_id("test-correlation-id")
        assert cid == "test-correlation-id"
        assert get_correlation_id() == "test-correlation-id"

    def test_auto_generate(self) -> None:
        cid = set_correlation_id()
        assert cid != ""
        assert get_correlation_id() == cid

    def test_reset(self) -> None:
        set_correlation_id("test-id")
        reset_context()
        assert get_correlation_id() == ""


class TestRequestId:
    def teardown_method(self) -> None:
        reset_context()

    def test_default_is_empty(self) -> None:
        assert get_request_id() == ""

    def test_set_and_get(self) -> None:
        rid = set_request_id("test-request-id")
        assert rid == "test-request-id"
        assert get_request_id() == "test-request-id"

    def test_auto_generate(self) -> None:
        rid = set_request_id()
        assert rid != ""
        assert get_request_id() == rid
