# RedOps Metric Plugin Template

This directory is a minimal template for creating custom metric plugins for RedOps.

## Quick Start

1. Copy this directory to create your own plugin:
   ```bash
   cp -r plugins/redops-metric-example plugins/redops-my-metric
   ```

2. Update `pyproject.toml`:
   - Change `name`, `version`, `description`
   - Update the entry-point module path in `[project.entry-points."redops.metrics"]`

3. Implement your metric in `my_metric/metrics.py`:
   - Extend `BaseMetric` from `app.evaluation.metrics.domain`
   - Set metadata fields (name, category, scale, evaluator_type, etc.)
   - Implement the `evaluate()` method

4. Install in development mode:
   ```bash
   pip install -e plugins/redops-my-metric
   ```

5. Verify discovery:
   ```python
   from app.evaluation.metrics.registry import MetricRegistry
   registry = MetricRegistry()
   registry.discover_external()
   print(registry.list_plugin_metrics())
   ```

## Entry Point Convention

Plugins register under the `redops.metrics` entry-point group:

```toml
[project.entry-points."redops.metrics"]
my_metric_name = "package.module:MetricClassName"
```

The key (`my_metric_name`) should be unique across all installed plugins.

## Required Fields

Every metric must define:

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Unique identifier (snake_case) |
| `display_name` | str | Human-readable name |
| `description` | str | What the metric measures |
| `category` | MetricCategory | CORRECTNESS, RELEVANCE, etc. |
| `scale` | MetricScale | ZERO_TO_ONE, BINARY, etc. |
| `version` | str | SemVer version string |
| `evaluator_type` | EvaluatorType | HEURISTIC, CUSTOM, etc. |
| `required_inputs` | tuple[str, ...] | Input keys the metric needs |

## Validation

The `MetricRegistry` validates plugins at registration time:
- `required_inputs` must be non-empty
- `evaluator_type` must be a valid enum value
- `version` must follow SemVer format
- Metric name must be unique (no duplicates)
