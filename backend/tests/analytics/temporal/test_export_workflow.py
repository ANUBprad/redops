"""Tests for Temporal export workflow and activity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.analytics.domain.entities import (
    GeneratedReport,
    ReportDefinition,
    ReportType,
)
from app.analytics.services.export_service import ExportService
from app.analytics.temporal.activities import (
    ExportResult,
    GenerateExportInput,
    configure_export_session_factory,
    generate_export_activity,
)
from app.analytics.temporal.workflow import ExportReportWorkflow


def _make_report(title: str = "Test Report") -> GeneratedReport:
    """Create a minimal GeneratedReport for testing."""
    return GeneratedReport(
        definition=ReportDefinition(
            id="report-1",
            report_type=ReportType.EXECUTIVE_SUMMARY,
            title=title,
        ),
        summary="Test summary",
        statistics={"key": 1.0},
        recommendations=["rec1"],
        sections=[],
    )


class TestGenerateExportInput:
    """Tests for GenerateExportInput dataclass."""

    def test_defaults(self) -> None:
        input_data = GenerateExportInput()
        assert input_data.report_type == "executive_summary"
        assert input_data.export_format == "json"
        assert input_data.days == 30

    def test_custom_values(self) -> None:
        input_data = GenerateExportInput(
            report_type="safety_summary",
            project_id="proj-1",
            export_format="csv",
            days=7,
        )
        assert input_data.report_type == "safety_summary"
        assert input_data.project_id == "proj-1"
        assert input_data.export_format == "csv"


class TestExportResult:
    """Tests for ExportResult dataclass."""

    def test_defaults(self) -> None:
        result = ExportResult()
        assert result.report_type == ""
        assert result.content == ""

    def test_with_values(self) -> None:
        result = ExportResult(
            report_type="executive_summary",
            export_format="json",
            content='{"test": true}',
            section_count=3,
            title="My Report",
        )
        assert result.section_count == 3
        assert result.title == "My Report"


class TestExportReportWorkflow:
    """Tests for ExportReportWorkflow."""

    def test_workflow_class_exists(self) -> None:
        wf = ExportReportWorkflow()
        assert hasattr(wf, "run")


class TestExportActivity:
    """Tests for generate_export_activity."""

    def test_activity_is_callable(self) -> None:
        assert callable(generate_export_activity)

    def test_session_factory_not_configured_raises(self) -> None:
        import asyncio

        input_data = GenerateExportInput()

        with pytest.raises(RuntimeError, match="Session factory not configured"):
            asyncio.run(generate_export_activity(input_data))

    def test_configure_session_factory(self) -> None:
        mock_factory = MagicMock()
        configure_export_session_factory(mock_factory)
        from app.analytics.temporal.activities import _session_factory

        assert _session_factory is mock_factory


class TestExportService:
    """Tests for the ExportService used by the activity."""

    def test_export_json(self) -> None:
        svc = ExportService()
        report = _make_report()
        import asyncio

        result = asyncio.run(svc.export(report, format="json"))
        assert "Test Report" in result
        assert "Test summary" in result

    def test_export_csv(self) -> None:
        svc = ExportService()
        report = _make_report()
        import asyncio

        result = asyncio.run(svc.export(report, format="csv"))
        assert "Section" in result

    def test_export_pdf(self) -> None:
        svc = ExportService()
        report = _make_report()
        import asyncio

        result = asyncio.run(svc.export(report, format="pdf"))
        assert "Test Report" in result
        assert "<html>" in result
