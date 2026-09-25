# redops-gate

An evaluation gate CLI for RedOps Eval. It triggers an evaluation run and
blocks (exits non-zero) when any configured metric threshold is breached —
designed to be used as a CI/CD quality gate.

The client uses only the Python standard library, so it runs anywhere
without extra dependencies.

## Usage

```bash
python redops_gate.py run \
  --api-url http://localhost:8000 \
  --api-key "$REDOPS_API_KEY" \
  --evaluation-id eval_123 \
  --provider openai \
  --model gpt-4o \
  --metric accuracy \
  --threshold "accuracy>=0.9" \
  --threshold "toxicity<0.1"
```

### Exit codes

| Code | Meaning                                          |
|------|--------------------------------------------------|
| 0    | Gate passed (all metrics within thresholds).     |
| 1    | At least one metric breached a threshold.        |
| 2    | Usage or configuration error.                    |
| 3    | Evaluation run failed or was cancelled.          |
| 4    | Timed out waiting for the run to complete.       |

### Options

- `--evaluation-id` / `--evaluation-name` — identify the evaluation (one required).
- `--metric <name>` — include a metric in the run (repeatable).
- `--threshold "<metric><op><value>"` — gate threshold (repeatable); ops are
  `>=, <=, >, <, ==, !=`, e.g. `accuracy>=0.9`.
- `--idempotency-key <key>` — enables safe CI/CD retries; a repeated key does
  not create a duplicate run.
- `--timeout <secs>` / `--poll-interval <secs>` — polling controls.

Environment variables: `REDOPS_API_URL`, `REDOPS_API_KEY`,
`REDOPS_IDEMPOTENCY_KEY`.

## GitHub Action

```yaml
- uses: ./redops-gate
  with:
    api-url: https://eval.example.com
    api-key: ${{ secrets.REDOPS_API_KEY }}
    evaluation-id: eval_123
    provider: openai
    model: gpt-4o
    metrics: "accuracy,toxicity"
    thresholds: "accuracy>=0.9,toxicity<0.1"
    idempotency-key: ${{ github.run_id }}
```

## GitLab CI

See `redops-gate.gitlab-ci.yml` for a reusable template.

## Idempotency

Pass a stable `--idempotency-key` (for example `$CI_PIPELINE_ID-$CI_JOB_ID`
in GitLab or `${{ github.run_id }}` in GitHub Actions) so that retries of
the same job do not spawn duplicate evaluation runs.
