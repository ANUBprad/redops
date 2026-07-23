# RedOps Eval — Contributing Guide

## Development Setup

See `README.md` for local development setup instructions. In brief:

```bash
git clone https://github.com/redops-eval/redops-eval.git
cd redops-eval
docker compose up -d   # Starts PostgreSQL, Redis, API
# Frontend runs separately:
cd frontend && npm install && npm run dev
```

---

## Branch Naming

Branches follow a strict naming convention:

```
<type>/<short-description>
```

**Types:**

| Type       | Purpose                              |
|-----------|--------------------------------------|
| `feat/`   | New feature                          |
| `fix/`    | Bug fix                              |
| `refactor/` | Code restructuring, no behavior change |
| `docs/`   | Documentation only                    |
| `test/`   | Adding or modifying tests             |
| `chore/`  | Build process, dependencies, tooling  |
| `perf/`   | Performance improvement               |
| `ops/`    | CI/CD, infrastructure, deployment    |

**Examples:**
- `feat/add-hallucination-metric`
- `fix/oauth-token-refresh`
- `refactor/extract-metric-base-class`

Use kebab-case. Keep descriptions under 60 characters.

---

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:** feat, fix, refactor, docs, test, chore, perf, ops, style.

**Scope:** Module name (auth, projects, prompts, datasets, evaluations, metrics, red-team, providers, reports, webhooks, dashboard, api, frontend, deps).

**Examples:**
```
feat(evaluations): add async worker dispatch for evaluation runs
fix(auth): handle expired refresh token gracefully
docs(api): document webhook payload schema
chore(deps): upgrade fastapi to 0.110.0
```

**Rules:**
- Description is imperative, present tense, lowercase, no period.
- Body explains *why* the change was made, not *what* (the diff shows what).
- Footer references GitHub issues: `Closes #123`, `Refs #456`.

---

## Testing Strategy

### Layers

| Layer           | Framework    | Scope                                            | Target Coverage |
|----------------|-------------|--------------------------------------------------|-----------------|
| Unit           | pytest      | Service layer, metrics, provider adapters        | 90%+            |
| Integration    | pytest + httpx | API endpoints with test database               | 80%+            |
| E2E            | Playwright  | Critical user flows (create run → view report)   | Key paths only  |
| Property-based | hypothesis  | Metric edge cases, input validation              | Critical paths  |

### Guidelines

- **Unit tests** mock external I/O (database, HTTP calls). Test business logic in isolation.
- **Integration tests** use a dedicated PostgreSQL test database (created/destroyed per session via pytest fixtures with `docker compose`).
- **Provider adapter tests** use mocked HTTP responses (responses library or pytest-httpx). Do not call real LLM providers in CI.
- **Metric tests** use known-input/known-output pairs to verify score calculation correctness.
- **Async tests** use `pytest-asyncio`. All async tests must have an event loop fixture.
- **No test is too small.** If it can break, test it.

### Running Tests

```bash
# Backend
cd backend && pytest                          # All tests
cd backend && pytest tests/unit              # Unit only
cd backend && pytest tests/integration       # Integration only
cd backend && pytest -k "metric"             # Filter by keyword

# Frontend
cd frontend && npm run test                  # Vitest
cd frontend && npm run test:e2e              # Playwright
```

---

## Code Style

### Python

- **Formatter:** ruff (line length: 100).
- **Linter:** ruff with strict ruleset (all built-in rules enabled, plus selected flake8 plugins).
- **Type checker:** mypy with `--strict` mode.
- Import order: ruff's built-in import sorting.
- **Docstrings:** Google style for public functions; no docstrings for private helpers unless the logic is non-obvious.

```bash
cd backend && ruff check . && ruff format --check . && mypy src/
```

### TypeScript / React

- **Formatter:** Prettier (line length: 100, single quotes, trailing commas).
- **Linter:** ESLint with `@typescript-eslint/strict`.
- **Type checker:** TypeScript `--strict` mode.
- **Naming:** PascalCase for components, camelCase for functions/variables, UPPER_CASE for constants.
- **File structure:** One component per file. Colocated tests: `Button.tsx`, `Button.test.tsx`.

```bash
cd frontend && npm run lint && npm run typecheck
```

### Pre-commit Hooks

The repository includes a `.pre-commit-config.yaml` with:
- ruff format check
- ruff lint
- mypy
- prettier (frontend)
- eslint (frontend)
- No secrets check (detect-secrets or similar)

All hooks must pass before committing.

---

## Review Process

### Before Opening a PR

1. Run full test suite locally (backend + frontend).
2. Run linter and type checker.
3. Write or update tests for the change.
4. Update documentation if the change affects the API or user-facing behavior.
5. Rebase onto the latest `main` branch.

### Pull Request Checklist

- [ ] Branch name follows convention.
- [ ] Commit messages follow Conventional Commits.
- [ ] All tests pass.
- [ ] Lint and type checks pass.
- [ ] New code includes tests (unit + integration where applicable).
- [ ] API changes are reflected in OpenAPI schema (auto-generated, verify diff).
- [ ] Database migrations are included if schema changed.
- [ ] No secrets, hardcoded credentials, or local paths.
- [ ] Documentation updated (README, docs/, API comments).
- [ ] PR description explains the problem, solution, and any tradeoffs.
- [ ] PR size is under 400 lines changed (exceptions: migrations, generated files).

### Review Guidelines

- Every PR requires at least one approval from a maintainer.
- Reviewers focus on:
  1. Correctness — Does it work? Are edge cases handled?
  2. Security — Are inputs validated? Are credentials handled safely?
  3. Maintainability — Is the code clear? Would a new contributor understand it?
  4. Test coverage — Are the tests meaningful? Do they test behavior, not implementation?
- Nitpicks (typos, style) should be marked as optional. Do not block the PR.
- The author should respond to every review comment (resolve or reply).

### Definition of Done

A task is "done" when:

- [ ] Code is implemented and merged to `main`.
- [ ] Tests pass in CI.
- [ ] Lint and type checks pass in CI.
- [ ] API documentation is updated (if applicable).
- [ ] User-facing changes are reflected in the UI.
- [ ] Database migrations are applied and reversible.
- [ ] Changelog is updated (if applicable).
- [ ] No regression in existing functionality.

---

## Documentation Standards

- **Code comments:** Avoid comments that restate the code. Use comments to explain *why* a non-obvious decision was made.
- **Docstrings:** Required for all public functions and classes in the backend. Use Google style.
- **API documentation:** Auto-generated from OpenAPI (FastAPI). Manually annotate with `description` parameters where the auto-generation is insufficient.
- **Architecture docs:** Live in `docs/`. Updated when architectural decisions change. Prefer concise, decision-focused documentation over detailed prose.
- **README:** The single entry point for new users and contributors. Keep it concise. Link to `docs/` for detailed information.

---

## Issue Reporting

- Use GitHub Issues for bug reports and feature requests.
- Bug reports should include: steps to reproduce, expected behavior, actual behavior, environment (OS, Python version, Docker version).
- Feature requests should explain the use case and desired behavior.
- Security vulnerabilities should be reported privately (see `SECURITY.md`).
