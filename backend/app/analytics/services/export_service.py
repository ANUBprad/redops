"""Export service for reports."""

from __future__ import annotations

import csv
import io
import json

from app.analytics.domain.entities import ExportFormat, GeneratedReport


class ExportService:
    """Service for exporting reports in various formats."""

    async def export(
        self,
        report: GeneratedReport,
        format: str = "json",
    ) -> str:
        """Export a report in the specified format.

        Args:
            report: The generated report to export.
            format: Export format (json, csv, pdf).

        Returns:
            The exported content as a string.

        """
        fmt = (
            ExportFormat(format) if format in [e.value for e in ExportFormat] else ExportFormat.JSON
        )

        if fmt == ExportFormat.JSON:
            return self._export_json(report)
        if fmt == ExportFormat.CSV:
            return self._export_csv(report)
        if fmt == ExportFormat.PDF:
            return self._export_pdf(report)
        return self._export_json(report)

    def _export_json(self, report: GeneratedReport) -> str:
        """Export report as JSON."""
        data = {
            "report": {
                "id": report.definition.id,
                "type": report.definition.report_type.value,
                "title": report.definition.title,
                "description": report.definition.description,
                "generated_at": report.definition.generated_at.isoformat()
                if report.definition.generated_at
                else None,
                "generated_by": report.definition.generated_by,
            },
            "summary": report.summary,
            "statistics": report.statistics,
            "recommendations": list(report.recommendations),
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "statistics": s.statistics,
                }
                for s in report.sections
            ],
        }
        return json.dumps(data, indent=2, default=str)

    def _export_csv(self, report: GeneratedReport) -> str:
        """Export report as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Section", "Metric", "Value"])
        writer.writerow(
            [
                "Report",
                "Title",
                report.definition.title,
            ]
        )
        writer.writerow(
            [
                "Report",
                "Type",
                report.definition.report_type.value,
            ]
        )
        writer.writerow(
            [
                "Report",
                "Generated",
                report.definition.generated_at.isoformat()
                if report.definition.generated_at
                else "",
            ]
        )
        writer.writerow([])

        for section in report.sections:
            writer.writerow([section.title, "Content", section.content[:500]])
            for metric, value in section.statistics.items():
                writer.writerow([section.title, metric, value])
            writer.writerow([])

        writer.writerow(["Recommendations"])
        for rec in report.recommendations:
            writer.writerow(["", rec])

        return output.getvalue()

    def _export_pdf(self, report: GeneratedReport) -> str:
        """Export report as PDF-compatible HTML.

        Returns HTML that can be converted to PDF by a browser
        or by a library like weasyprint.
        """
        sections_html = ""
        for section in report.sections:
            stats_rows = ""
            for metric, value in section.statistics.items():
                stats_rows += f"<tr><td>{metric}</td><td>{value}</td></tr>"

            sections_html += f"""
            <div class="section">
                <h2>{section.title}</h2>
                <p>{section.content}</p>
                {"<table>" + stats_rows + "</table>" if stats_rows else ""}
            </div>
            """

        recs_html = "".join(f"<li>{r}</li>" for r in report.recommendations)

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{report.definition.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #1a1a1a; }}
        h2 {{ color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
        .section {{ margin: 20px 0; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <h1>{report.definition.title}</h1>
    <p>{report.definition.description}</p>
    <p><em>Generated: {
            report.definition.generated_at.isoformat() if report.definition.generated_at else "N/A"
        }</em></p>

    <h2>Summary</h2>
    <p>{report.summary}</p>

    {sections_html}

    <h2>Recommendations</h2>
    <ul>{recs_html}</ul>
</body>
</html>"""
