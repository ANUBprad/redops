# RedOps Eval — Documentation

Welcome to the RedOps Eval documentation. RedOps Eval is an open-source platform for
evaluating Large Language Models before deployment — measuring hallucination, faithfulness,
answer relevancy, toxicity, bias, prompt-injection resistance, jailbreak resistance, latency,
cost, and token usage across multiple LLM providers.

Use this index to find the right documentation for what you're trying to do.

---

## Getting Started

| Document                   | Purpose                                              |
|----------------------------|------------------------------------------------------|
| [GETTING_STARTED.md](GETTING_STARTED.md) | From zero to your first evaluation run in ~10 minutes. |
| [README.md](../README.md)  | Quick start, local setup, repo layout.               |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deploy to production (Docker, Kubernetes, Helm).   |
| [MONITORING.md](MONITORING.md) | Prometheus + Grafana dashboards, metrics, alerts.   |

## For Contributors

| Document           | Purpose                                                       |
|--------------------|---------------------------------------------------------------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, branch naming, commits, tests, review. |
| [SECURITY.md](../SECURITY.md) | Security policy and vulnerability reporting.               |
| [ROADMAP.md](ROADMAP.md) | Implementation phases and planned work.                    |

## Architecture & Reference

| Document          | Purpose                                            |
|-------------------|----------------------------------------------------|
| [VISION.md](VISION.md)       | Project mission and goals.               |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and design.       |
| [TECH_STACK.md](TECH_STACK.md) | Technology choices and rationale.       |
| [MODULES.md](MODULES.md)     | Module descriptions.                    |
| [DATABASE.md](DATABASE.md)   | Database design.                        |
| [API_SPEC.md](API_SPEC.md)   | REST API specification.                 |
| [DECISIONS.md](DECISIONS.md) | Architecture Decision Records.          |

## Evaluation Engine

| Document                                                            | Purpose                                 |
|---------------------------------------------------------------------|-----------------------------------------|
| [EXECUTION_MODEL.md](evaluation/EXECUTION_MODEL.md)                  | Execution model overview.               |
| [EXECUTION_PIPELINE.md](evaluation/EXECUTION_PIPELINE.md)            | End-to-end pipeline.                    |
| [STATE_MACHINE.md](evaluation/STATE_MACHINE.md)                      | Run/item state transitions.             |
| [PARALLEL_EXECUTION.md](evaluation/PARALLEL_EXECUTION.md)            | Concurrency model.                      |
| [CHECKPOINTING.md](evaluation/CHECKPOINTING.md)                      | Durable checkpointing.                  |
| [CANCELLATION_MODEL.md](evaluation/CANCELLATION_MODEL.md)            | Cancellation semantics.                 |
| [RETRY_POLICY.md](evaluation/RETRY_POLICY.md)                        | Retry policies.                         |
| [FAILURE_HANDLING.md](evaluation/FAILURE_HANDLING.md)                | Failure handling.                       |
| [EVENT_FLOW.md](evaluation/EVENT_FLOW.md)                            | Event flow.                             |
| [EVALUATION_ENGINE.md](evaluation/EVALUATION_ENGINE.md)              | Engine internals.                       |
| [DESIGN_DECISIONS.md](evaluation/DESIGN_DECISIONS.md)                | Engine design decisions.                |

## Operations

- [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) — Go/No-Go checklist for public releases.
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deployment instructions and troubleshooting.

## Sample Data

A ready-to-use sample evaluation dataset ships with the repo:

`scripts/sample_data/redops-sample-eval.jsonl`

See [GETTING_STARTED.md](GETTING_STARTED.md) for how to load it.
