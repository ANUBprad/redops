"""Tests for analytics export service."""

from __future__ import annotations

import json

from app.analytics.domain.entities import (
    GeneratedReport,
    ReportDefinition,
    ReportSection,
    ReportType,
)
from app.analytics.services.export_service import ExportService


class TestExportService:
    def setup_method(self) -> None:
        self.service = ExportService()
        self.report = GeneratedReport(
            definition=ReportDefinition(
                id="rpt-1",
                report_type=ReportType.EXECUTIVE_SUMMARY,
                title="Test Report",
                description="A test report",
            ),
            sections=(
                ReportSection(
                    title="Overview",
                    content="Test content here",
                    statistics={"total": 10.0, "success_rate": 85.5},
                ),
            ),
            summary="This is a test summary",
            recommendations=("Rec 1", "Rec 2"),
        )

    async def test_export_json(self) -> None:
        result = await self.service.export(self.report, format="json")
        data = json.loads(result)
        assert data["report"]["title"] == "Test Report"
        assert data["report"]["type"] == "executive_summary"
        assert data["summary"] == "This is a test summary"
        assert len(data["recommendations"]) == 2
        assert len(data["sections"]) == 1
        assert data["sections"][0]["title"] == "Overview"

    async def test_export_csv(self) -> None:
        result = await self.service.export(self.report, format="csv")
        assert "Section" in result
        assert "Metric" in result
        assert "Value" in result
        assert "Test Report" in result
        assert "Overview" in result
        assert "total" in result

    async def test_export_pdf_html(self) -> None:
        result = await self.service.export(self.report, format="pdf")
        assert "<!DOCTYPE html>" in result
        assert "Test Report" in result
        assert "Test content here" in result
        assert "Rec 1" in result

    async def test_export_defaults_to_json(self) -> None:
        result = await self.service.export(self.report, format="unknown")
        data = json.loads(result)
        assert data["report"]["title"] == "Test Report"
