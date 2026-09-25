# RedOps Eval — Technology Stack

## Overview

Every technology choice below was evaluated against three criteria:
1. **Production readiness** — Is it battle-tested at scale in the AI/ML ecosystem?
2. **Developer experience** — Does it accelerate development without sacrificing correctness?
3. **Ecosystem fit** — Does it integrate naturally with the other tools in the stack?

---

## Backend

### FastAPI

**Why:** FastAPI provides native async support, automatic OpenAPI generation, Pydantic-based request/response validation, and first-class WebSocket support. For a platform making hundreds of LLM provider calls concurrently, synchronous frameworks (Flask, Django REST) would require significant workarounds to avoid blocking the event loop. FastAPI's dependency injection system also simplifies provider registry wiring and database session management.

**Alternatives considered:** Flask + Flask-RESTx, Django + DRF, Litestar.

**Tradeoffs:** FastAPI is younger than Django and has a smaller middleware ecosystem. However, its async-native design and OpenAPI compliance make it the correct choice for an API-driven, I/O-heavy platform.

---

### SQLAlchemy (v2.x with async)

**Why:** SQLAlchemy 2.0's async session support (`AsyncSession`, `asyncio`-compatible) pairs naturally with FastAPI's async event loop. Its declarative mapping, relationship loading strategies, and Alembic integration provide a mature ORM layer without sacrificing the ability to write optimized queries when needed.

**Alternatives considered:** SQLModel (too early, tight coupling to FastAPI), Tortoise-ORM (limited ecosystem), raw SQL via asyncpg (no migrations, no relationship mapping).

**Tradeoffs:** ORMs add abstraction overhead. For complex analytical queries (metric aggregation, time-series rollups), we will use SQLAlchemy Core or raw SQL via asyncpg directly. The ORM is for CRUD; analytical queries bypass it.

---

### Temporal (Workflow Orchestration)

**Why:** Evaluation runs are multi-step, long-lived (minutes to hours), and must survive process restarts. Temporal provides durable execution, automatic retries, built-in state management, event history, and cancellation scopes. Unlike a task queue (Celery), Temporal manages the entire workflow state machine — the application does not need to track "where are we in this evaluation run." Temporal's Python SDK integrates naturally with our async stack.

**Key features used:** Workflow definitions (evaluation orchestration), Activities (provider calls, metric computation), cron schedules (red team campaigns), saga patterns (rollback on failure), event history (debugging and audit).

**Alternatives considered:** Celery (task queue, not workflow engine — lacks durable state, event history, and cancellation scopes), Dramatiq (simpler but insufficient for multi-step workflows), Hatchet (newer, less battle-tested), Inngest (serverless, not self-hostable), native asyncio (no durability — state lost on restart).

**Tradeoffs:** Temporal adds operational complexity (requires Temporal Server + its own PostgreSQL database). The Temporal dev server (single binary) makes this trivial for development. For production, the Temporal cluster is a one-time operational investment that pays for itself in reliability guarantees.

---

### Alembic (Migrations)

**Why:** First-party migration tool for SQLAlchemy. Auto-generation of migration scripts from model changes reduces human error. No other tool integrates as tightly.

---

### Pydantic v2 (Validation)

**Why:** Already required by FastAPI. Pydantic v2 (Rust-based core) is significantly faster than v1 and provides serialization/deserialization for all API request/response models. Also used for configuration management (`BaseSettings`).

---

## Frontend

### React 18+ with TypeScript

**Why:** React's component model, ecosystem maturity, and hook-based state management make it the most pragmatic choice for a data-heavy dashboard. TypeScript provides type safety across the API boundary — we will auto-generate TypeScript types from the OpenAPI spec (openapi-typescript).

**Alternatives considered:** Vue 3 (smaller ecosystem for charting/table libraries), Svelte (younger, smaller hiring pool), Next.js (SSR adds complexity for an SPA dashboard).

**Tradeoffs:** React's bundle size is larger than alternatives. Tree-shaking and lazy loading via Vite will mitigate this. The isomorphic benefits of Next.js are unnecessary for an authenticated SPA behind a reverse proxy.

---

### Vite (Build Tool)

**Why:** Sub-second HMR, native TypeScript and JSX support, optimized production builds. The de-facto standard for new React projects.

---

### Tailwind CSS v3

**Why:** Utility-first CSS eliminates the need for a separate CSS codebase. For a team building dashboards, forms, and data tables, Tailwind's constraint-based design system results in consistent, responsive UIs without CSS-in-JS runtime overhead.

**Alternatives considered:** Chakra UI (too opinionated, difficult to customize), Material UI (heavy bundle, non-native feel), vanilla CSS (maintenance burden at scale).

**Tradeoffs:** JSX can become verbose with many utility classes. We will extract common patterns into reusable components (via shadcn/ui) to mitigate this.

---

### shadcn/ui

**Why:** Not a component library in the traditional sense — it provides copy-paste React components built on Radix UI primitives, styled with Tailwind. This gives full control over the component source code (no opaque dependency), tree-shakeable by default, and follows the same visual language as Tailwind.

**Alternatives considered:** Radix UI primitives directly (more work), Headless UI (fewer components), Ant Design (opinionated, difficult to theme).

**Tradeoffs:** Components live in your codebase, so you own every update. This is a feature, not a bug — it prevents version-lock and allows customization without fighting a design system.

---

### TanStack Query (React Query)

**Why:** Server state management — caching, background refetch, optimistic updates, pagination. For an API-heavy app with polling and WebSocket fallback, TanStack Query eliminates boilerplate and provides a declarative data-fetching model.

---

### Recharts

**Why:** Lightweight, declarative charting library built on React components. Sufficient for bar charts, line charts, histograms, and radar charts needed for metric visualization.

**Alternatives considered:** D3.js (too low-level), Chart.js + react-chartjs-2 (imperative, less React-idiomatic).

---

## Database

### PostgreSQL 16+

**Why:** The relational model is the correct choice for structured, interrelated evaluation data (projects → runs → metrics, datasets → prompts → responses). PostgreSQL's JSONB columns allow semi-structured metric configurations when needed. Its mature feature set (window functions, CTEs, partial indexes, GiST indexes for exclusion constraints) supports both transactional and analytical queries in the same database.

**Alternatives considered:** MySQL (weaker analytical query support, inferior JSON support), SQLite (not suitable for concurrent production access), MongoDB (no joins, weak integrity guarantees for interrelated data), TimescaleDB (specialized for time-series; unnecessary overhead for our volume — we will use PostgreSQL + materialized views for time-series rollups).

**Tradeoffs:** Scaling PostgreSQL for writes at very high throughput requires careful indexing and partitioning. For an evaluation platform (write-once, read-many), this is a negligible concern. If telemetry volume becomes extreme, we can extract time-series metric data into a separate PostgreSQL instance or migrate specific aggregations to ClickHouse, but this is premature until validated by production data.

---

### Redis

**Why:** Event Bus (Redis Streams), rate limiting counters, WebSocket pub/sub, and lightweight caching layer. Redis serves multiple infrastructure roles. Note: Redis is NOT used as a task queue — Temporal replaces Celery for all background processing.

---

## AI/Evaluation Libraries

### DeepEval

**Why:** DeepEval is the most comprehensive open-source LLM evaluation framework with 20+ built-in metrics (hallucination, faithfulness, relevancy, toxicity, bias, etc.). It supports both LLM-based evaluation (calling an evaluator model) and non-LLM metrics. Its modular metric interface aligns with our extension point philosophy.

**Alternatives considered:** LangChain's evaluation module (less comprehensive, coupled to LangChain's runtime), RAGAS (RAG-only), built-from-scratch metrics (too high a maintenance cost).

**Tradeoffs:** DeepEval is a dependency that evolves rapidly. We will wrap each metric in our own adapter layer so that swapping the underlying library does not affect the rest of the system.

---

### LangSmith

**Why:** Optional integration for tracing and debugging LLM calls during development. LangSmith provides a visual trace of every provider call, including latency, token usage, and raw inputs/outputs. This is invaluable during evaluation pipeline development and debugging.

**Decision:** LangSmith is **optional**. It is enabled via configuration. It is not a hard dependency. The platform does not rely on LangSmith for any core functionality.

---

### LangChain

**Why:** Was evaluated as a universal provider interface to support providers such as Ollama (`ChatOllama`) and Groq (`ChatGroq`). It is **not currently a dependency** — the shipped `openai/` and `anthropic/` adapters use their providers' native SDKs directly, and no LangChain import exists in the codebase.

**Decision:** LangChain is not part of the current implementation. Provider adapters use native SDKs. If a future Phase 11 provider (Groq, Ollama, etc.) benefits from LangChain, it would be introduced as an internal detail of that adapter only — not part of the public API or the evaluation pipeline.

---

## Infrastructure

### Docker + Docker Compose

**Why:** Containerization provides a reproducible development environment across macOS, Linux, and Windows. Docker Compose orchestrates the three required services (API, PostgreSQL, Redis) with a single `docker compose up` command. Production deployments target Kubernetes, but Compose is sufficient for development and CI.

**Alternatives considered:** Podman (Docker-compatible but smaller ecosystem), local development without containers (environment drift issues).

---

### GitHub Actions

**Why:** CI/CD natively integrated with the GitHub repository. Free for public repositories, large runner ecosystem, matrix builds, and native Docker support. For an open-source project, GitHub Actions is the default choice.

**Alternatives considered:** CircleCI (paid tier required for performance), GitLab CI (requires GitLab hosting), Jenkins (operational overhead).

---

## Summary

| Layer        | Choice                | Key Driver                     |
|-------------|----------------------|--------------------------------|
| API Framework | FastAPI              | Async-native, OpenAPI, Pydantic |
| ORM          | SQLAlchemy 2.0 async  | Mature, async, Alembic         |
| Database     | PostgreSQL 16+       | Relational model, JSONB, CTEs  |
| Workflow Engine | Temporal           | Durable execution, state mgmt, retries |
| Event Bus    | Redis Streams        | Decoupled services, pub/sub    |
| Frontend     | React + TypeScript   | Ecosystem, type safety         |
| Build Tool   | Vite                 | Speed, HMR, tree-shaking       |
| CSS          | Tailwind + shadcn/ui | Utility-first, full control    |
| State Mgmt   | TanStack Query       | Server state, caching          |
| Charts       | Recharts             | Declarative, React-native      |
| Metrics      | DeepEval             | Comprehensive, modular         |
| Tracing      | LangSmith (optional) | Debugging, observability       |
| CI/CD        | GitHub Actions       | Native, free for OSS           |
| Containers   | Docker + Compose     | Reproducibility                |
