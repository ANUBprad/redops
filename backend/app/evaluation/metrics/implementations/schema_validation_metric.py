"""Schema Validation metric — validates response against a JSON schema."""

from __future__ import annotations

import json
import time

from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)


class SchemaValidationMetric(Metric):
    """Validates that the response conforms to a provided JSON schema.

    The schema is provided via input_data.metadata["schema"].
    Uses jsonschema library if available, falls back to basic validation.
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="schema_validation",
            display_name="Schema Validation",
            description="Validates that the response conforms to a JSON schema",
            category=MetricCategory.VALIDATION,
            scale=MetricScale.BINARY,
            evaluator_type=EvaluatorType.HEURISTIC,
            required_inputs=("response",),
            tags=("validation", "format", "schema"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()
        metric_version = self.definition().version

        if not input_data.response:
            return MetricResult(
                metric_name="schema_validation",
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                version=metric_version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        schema = input_data.metadata.get("schema")
        if isinstance(schema, str) and schema:
            try:
                schema = json.loads(schema)
            except (json.JSONDecodeError, ValueError):
                schema = None
        if not schema or not isinstance(schema, dict):
            return MetricResult(
                metric_name="schema_validation",
                score=0.0,
                normalized_score=0.0,
                error="No schema provided in metadata['schema']",
                version=metric_version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            parsed = json.loads(input_data.response)
        except (json.JSONDecodeError, ValueError) as exc:
            return MetricResult(
                metric_name="schema_validation",
                score=0.0,
                normalized_score=0.0,
                reasoning=f"Response is not valid JSON: {exc}",
                version=metric_version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            from jsonschema import validate as jsonschema_validate

            jsonschema_validate(instance=parsed, schema=schema)
            return MetricResult(
                metric_name="schema_validation",
                score=1.0,
                normalized_score=1.0,
                reasoning="Response conforms to the provided schema",
                version=metric_version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )
        except ImportError:
            pass
        except Exception as exc:
            return MetricResult(
                metric_name="schema_validation",
                score=0.0,
                normalized_score=0.0,
                reasoning=f"Schema validation failed: {exc}",
                version=metric_version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        required = schema.get("required", [])
        properties = schema.get("properties", {})

        if isinstance(parsed, dict):
            missing = [r for r in required if r not in parsed]
            if missing:
                return MetricResult(
                    metric_name="schema_validation",
                    score=0.0,
                    normalized_score=0.0,
                    reasoning=f"Missing required fields: {', '.join(missing)}",
                    metadata={"missing_fields": missing},
                    version=metric_version,
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                )

            extra_types = []
            for key, value in parsed.items():
                if key in properties:
                    expected_type = properties[key].get("type")
                    if expected_type:
                        actual_type = _json_type(value)
                        if actual_type != expected_type:
                            extra_types.append(
                                f"{key}: expected {expected_type}, got {actual_type}"
                            )

            if extra_types:
                return MetricResult(
                    metric_name="schema_validation",
                    score=0.5,
                    normalized_score=0.5,
                    reasoning=f"Type mismatches: {'; '.join(extra_types)}",
                    metadata={"type_mismatches": extra_types},
                    version=metric_version,
                    execution_time_ms=int((time.monotonic() - start) * 1000),
                )

        return MetricResult(
            metric_name="schema_validation",
            score=1.0,
            normalized_score=1.0,
            reasoning="Response passes basic schema validation",
            version=metric_version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )


def _json_type(value: object) -> str:
    """Map Python type to JSON schema type string."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return "string"
