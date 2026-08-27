"""Tests for the redops-gate evaluation gate CLI."""

from __future__ import annotations

import argparse
import unittest
from unittest import mock

from redops_gate import _check_thresholds, _parse_thresholds, build_parser, run_gate


class ThresholdParsingTests(unittest.TestCase):
    def test_parse_valid_threshold(self) -> None:
        parsed = _parse_thresholds(["accuracy>=0.9"])
        self.assertEqual(parsed, [("accuracy", 0.9, ">=")])

    def test_parse_multiple_operators(self) -> None:
        parsed = _parse_thresholds(["a>=1", "b<0.5", "c==1", "d!=0", "e>2", "f<=3"])
        self.assertEqual(
            parsed,
            [
                ("a", 1.0, ">="),
                ("b", 0.5, "<"),
                ("c", 1.0, "=="),
                ("d", 0.0, "!="),
                ("e", 2.0, ">"),
                ("f", 3.0, "<="),
            ],
        )

    def test_parse_invalid_threshold_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_thresholds(["noop"])

    def test_parse_invalid_value_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_thresholds(["metric>=notanumber"])


class ThresholdCheckTests(unittest.TestCase):
    def test_all_passing(self) -> None:
        passed, violations = _check_thresholds(
            {"accuracy": 0.95, "toxicity": 0.05},
            [("accuracy", 0.9, ">="), ("toxicity", 0.1, "<")],
        )
        self.assertTrue(passed)
        self.assertEqual(violations, [])

    def test_breach_reported(self) -> None:
        passed, violations = _check_thresholds(
            {"accuracy": 0.8},
            [("accuracy", 0.9, ">=")],
        )
        self.assertFalse(passed)
        self.assertEqual(len(violations), 1)
        self.assertIn("accuracy", violations[0])

    def test_missing_metric_is_violation(self) -> None:
        passed, violations = _check_thresholds({}, [("accuracy", 0.9, ">=")])
        self.assertFalse(passed)
        self.assertIn("no score", violations[0])


class BuildParserTests(unittest.TestCase):
    def test_requires_command(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args([])

    def test_run_requires_provider_and_model(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["run", "--evaluation-id", "e"])


class RunGateTests(unittest.TestCase):
    def _namespace(self, **kwargs: object) -> argparse.Namespace:
        defaults = dict(
            api_url="http://test",
            api_key="key",
            evaluation_id="eval_1",
            evaluation_name=None,
            provider="openai",
            model="gpt-4o",
            metrics=["accuracy"],
            thresholds=[("accuracy", 0.9, ">=")],
            idempotency_key="idem-1",
            timeout=30.0,
            poll_interval=0.01,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def _install_fake_request(self, values: dict[str, dict]) -> None:
        def fake(
            url: str,
            headers: dict,  # noqa: ARG001
            *,
            method: str = "GET",
            payload: dict | None = None,  # noqa: ARG001
        ) -> dict:
            key = f"{method} {url}"
            if key not in values:
                raise RuntimeError(f"unexpected call: {key}")
            return values[key]

        patcher = mock.patch("redops_gate._request", side_effect=fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_gate_passes(self) -> None:
        self._install_fake_request(
            {
                "POST http://test/api/v1/runs": {"id": "run-1", "status": "queued"},
                "GET http://test/api/v1/runs/run-1": {
                    "id": "run-1",
                    "status": "completed",
                },
                "GET http://test/api/v1/runs/run-1/metrics": {
                    "results": [{"metric": "accuracy", "score": 0.95}]
                },
            }
        )
        code = run_gate(self._namespace())
        self.assertEqual(code, 0)

    def test_gate_blocked_on_breach(self) -> None:
        self._install_fake_request(
            {
                "POST http://test/api/v1/runs": {"id": "run-1", "status": "queued"},
                "GET http://test/api/v1/runs/run-1": {
                    "id": "run-1",
                    "status": "completed",
                },
                "GET http://test/api/v1/runs/run-1/metrics": {
                    "results": [{"metric": "accuracy", "score": 0.5}]
                },
            }
        )
        code = run_gate(self._namespace())
        self.assertEqual(code, 1)

    def test_gate_failed_run(self) -> None:
        self._install_fake_request(
            {
                "POST http://test/api/v1/runs": {"id": "run-1", "status": "queued"},
                "GET http://test/api/v1/runs/run-1": {
                    "id": "run-1",
                    "status": "failed",
                    "failure_reason": "provider error",
                },
            }
        )
        code = run_gate(self._namespace())
        self.assertEqual(code, 3)

    def test_gate_timeout(self) -> None:
        calls = {"n": 0}

        def fake(
            url: str,
            headers: dict,  # noqa: ARG001
            *,
            method: str = "GET",
            payload: dict | None = None,  # noqa: ARG001
        ) -> dict:
            if method == "POST":
                return {"id": "run-1", "status": "queued"}
            calls["n"] += 1
            return {"id": "run-1", "status": "queued", "items_completed": calls["n"]}

        with mock.patch("redops_gate._request", side_effect=fake):
            code = run_gate(self._namespace(timeout=0.01, poll_interval=0.01))
        self.assertEqual(code, 4)

    def test_missing_evaluation_is_usage_error(self) -> None:
        code = run_gate(self._namespace(evaluation_id=None, evaluation_name=None))
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
