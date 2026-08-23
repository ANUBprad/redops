# RedOps Eval

**Production-grade LLM Evaluation & Red Teaming Platform**

RedOps Eval is an open-source platform for evaluating Large Language Models before deployment. It measures hallucination, faithfulness, answer relevancy, toxicity, bias, prompt injection resistance, jailbreak resistance, latency, cost, and token usage across multiple LLM providers.

## Quick Start

```bash
# Start all services
docker compose -f docker/docker-compose.yml up

# API:        http://localhost:8000
# API Docs:   http://localhost:8000/docs
# Frontend:   http://localhost:5173
# Temporal:   http://localhost:8233
```

## Architecture

```
Workspace (Team) → Project → Experiment → Evaluation Run
```

The platform uses:

- **Temporal** for durable workflow orchestration (evaluation runs, red team campaigns)
- **FastAPI** for the REST API with async-first design
- **PostgreSQL** for structured evaluation data
- **Redis** for event bus (Redis Streams), rate limiting, and caching
- **React + Vite + Tailwind** for the dashboard UI

## Repository Structure

```
redops-eval/
├── backend/          # FastAPI application (Python 3.12)
│   ├── app/          # Application code
│   ├── alembic/      # Database migrations
│   └── tests/        # Test suite
├── frontend/         # React SPA (TypeScript)
│   └── src/          # Application code
├── docker/           # Docker Compose and related configs
├── .github/          # CI/CD workflows
└── docs/             # Architecture and planning documentation
```

## Documentation

See the `docs/` directory for comprehensive architecture documentation:

- **[VISION.md](docs/VISION.md)** — Project mission and goals
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — System architecture and design
- **[ROADMAP.md](docs/ROADMAP.md)** — Implementation phases
- **[TECH_STACK.md](docs/TECH_STACK.md)** — Technology choices and rationale
- **[DATABASE.md](docs/DATABASE.md)** — Database design
- **[API_SPEC.md](docs/API_SPEC.md)** — REST API specification
- **[MODULES.md](docs/MODULES.md)** — Module descriptions
- **[CONTRIBUTING.md](docs/CONTRIBUTING.md)** — Engineering standards
- **[DECISIONS.md](docs/DECISIONS.md)** — Architecture Decision Records

## Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker and Docker Compose

### Local Setup

```bash
# Copy environment configuration
cp .env.example .env

# Backend setup
cd backend
pip install -e ".[dev]"

# Frontend setup
cd ../frontend
npm install

# Start infrastructure (PostgreSQL, Redis, Temporal)
docker compose -f ../docker/docker-compose.yml up postgres redis temporal

# Start API (in a separate terminal)
cd backend
uvicorn app.main:create_app --reload --factory

# Start Frontend (in a separate terminal)
cd frontend
npm run dev
```

## License

Apache 2.0. See [LICENSE](LICENSE).
