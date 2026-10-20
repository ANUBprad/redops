# Groq Integration Finalization — Report

Date: 2026-10-20
Scope: complete the Groq provider integration without a live `GROQ_API_KEY`,
audit the repository for safe cleanup, validate the project without starting any
server, and record the results. No live provider request was made this sprint.

## 1. Groq integration

### 1.1 What already existed (verified, not re-implemented)

Groq support was already wired end to end: `app/providers/groq/` (provider,
constants, capabilities), registry registration in
`container._register_providers`, pricing defaults, `.env.example` / README
documentation, and the `backend/tests/providers/groq/` suites. OpenAI remains an
optional provider; nothing globally replaced `OPENAI_API_KEY`.

### 1.2 Defects found and fixed

| # | Defect | Root cause | Fix |
|---|---|---|---|
| 1 | **Cross-provider credential leak.** `GroqProvider` passed `api_key=None` straight to `AsyncOpenAI`, so the SDK fell back to the ambient `OPENAI_API_KEY` and sent an OpenAI key to `api.groq.com`. The class docstring claimed a `GROQ_API_KEY` fallback that did not exist. | Implicit SDK env fallback; no explicit key resolution. | `GroqProvider` now resolves `api_key or os.environ["GROQ_API_KEY"]` and never consults `OPENAI_API_KEY`. |
| 2 | **No clear error when the key is missing.** A request without a key surfaced as a generic SDK error, or not at all if an unrelated key happened to be set. | Eager client construction. | Client construction is deferred to the first real request; a missing key raises `ProviderException(error_code="PROVIDER_CONFIGURATION_ERROR")` naming `GROQ_API_KEY`. Import and application startup still succeed when the optional key is absent. |
| 3 | **No configurable default model.** Callers had to name a model on every request; there was no centralized, configuration-driven default. | Missing setting. | Added `DEFAULT_MODEL = "llama-3.3-70b-versatile"` in `providers/groq/constants.py` and the `GROQ_MODEL` setting in `app/core/config.py`; the container passes it into `GroqProvider(default_model=...)`. Requests that omit `model` use it. |
| 4 | **Errors from Groq were labelled `openai`.** `map_openai_error` hard-coded `PROVIDER_NAME = "openai"`. | Shared mapper without provider identity. | `map_openai_error(..., provider_name=...)`, `wrap_streaming_error(..., provider_name=...)`, `OpenAIClient(provider_name=...)` and the chat/tool/stream adapters now propagate the caller's provider name. Default remains `openai`, preserving OpenAI behaviour. |
| 5 | **Responses from Groq claimed `provider="openai"`.** `map_chat_response` was called without the provider argument. | Same shared-adapter gap. | `OpenAIChatAdapter` / `OpenAIToolCallingAdapter` accept `provider_name` and pass it through; `GroqProvider` passes `"groq"`. |
| 6 | **OpenAI-only parameters were forwarded to Groq.** `ChatOptions(logprobs=…, top_logprobs=…)` were mapped straight into the payload; Groq documents both as unsupported (HTTP 400). | No provider-specific validation. | `GroqProvider` rejects them with `ProviderException(error_code="PROVIDER_UNSUPPORTED_PARAMETER")` before any HTTP call, naming the offending option and linking Groq's compatibility doc. `response_format={"type": "json_object"}` passes through unchanged (Groq supports JSON mode). |

Endpoint, request/response mapping, streaming, and tool-calling continue to use
the shared OpenAI-compatible client and adapters pointed at
`https://api.groq.com/openai/v1`.

### 1.3 Files changed

```
.env.example                                        (+ GROQ_MODEL)
README.md                                           (provider section corrected)
backend/app/core/config.py                          (+ groq_model / GROQ_MODEL)
backend/app/infrastructure/composition/container.py (pass default_model)
backend/app/providers/groq/constants.py             (+ DEFAULT_MODEL)
backend/app/providers/groq/provider.py              (key resolution, lazy client, default model, option guard)
backend/app/providers/openai/adapters/contracts.py  (provider_name on chat/tool/stream adapters)
backend/app/providers/openai/client/openai_client.py (provider_name for error mapping)
backend/app/providers/openai/errors/mapping.py      (provider_name parameter)
backend/app/providers/openai/streaming/adapter.py   (provider_name for streaming errors)
backend/tests/providers/groq/test_groq_integration.py (new, 16 tests)
backend/tests/providers/openai/test_error_mapping.py (+2 regression tests)
```

Documentation: `.env.example` gained a `GROQ_MODEL` placeholder; the README
provider-credentials section now documents `GROQ_MODEL` and was corrected where
it made two claims that the code does not support (see §2.4 of the cleanup
audit). No secret, key, or `.env` content is printed, logged, or committed
anywhere in this change.

### 1.4 Tests added (unit tests — the Groq transport is stubbed)

`backend/tests/providers/groq/test_groq_integration.py`:

| Area | Tests |
|---|---|
| Endpoint & credentials | Groq base URL used; explicit key injected; `GROQ_API_KEY` env fallback; `OPENAI_API_KEY` never used (missing-key path); health is `False` without a key |
| Model selection | `GROQ_MODEL` default and override; default model used when omitted; explicit model wins |
| Request/response adaptation | messages + temperature/max_tokens mapped; content and token usage surfaced; `provider == "groq"`; JSON-mode passthrough; unsupported `logprobs` rejected before the HTTP call |
| Error mapping | HTTP 429 → `RateLimitExceeded` carrying `provider_name == "groq"` |
| Eval/judge compatibility | real `JudgeEngine` scores a `JudgeRequest` through the real `GroqProvider` (mocked transport): score, confidence, token counts, `judge_model` |

`backend/tests/providers/openai/test_error_mapping.py` gained two tests proving
the mapper still defaults to `provider_name == "openai"` and can be overridden.

A judge-compatibility check was also added to the metric-sanity harness
(`evidence/harness/verify_metric_sanity.py`): a Groq-judge case now proves the
judge records `provider="groq"` and `judge_model="llama-3.3-70b-versatile"`
alongside tokens. Harness total moved 24 → **26 checks, all passing**.

### 1.5 Live Groq verification

**NOT RUN — awaiting `GROQ_API_KEY`.**

- Boolean key-presence check: `GROQ_API_KEY` is **absent** in this environment.
- No live request was attempted. The provider harness reports Groq as
  `credential_present=false / request_attempted=false / outcome=blocked / reason="no credential configured in environment"`.
- When the key is added, the only change needed is setting `GROQ_API_KEY` (and
  optionally `GROQ_MODEL`); the container registers Groq automatically and
  `backend/tests/providers/test_live_provider_smoke.py` provides the opt-in live
  smoke test.

## 2. Repository cleanup

Full audit: `evidence/repository-cleanup-audit.md`. Summary:

- **Tracked files:** 1156 / 6.18 MB. Zero tracked build artifacts or caches
  (`.pyc`, `__pycache__`, `node_modules`, pytest/mypy/ruff caches, coverage,
  logs, archives all filtered → no matches).
- **Applied fixes:**
  - Repaired CP1252 mojibake (`â€”` → `—`) in three comments of
    `backend/tests/redteam/temporal/test_metrics_persistence_retryability.py`;
    repo-wide re-scan now reports 0 damaged files and zero non-UTF-8 tracked files.
  - Corrected two false statements in the README provider section (see below).
  - Ignored regenerated harness output (`evidence/harness/metric-evidence/`,
    `evidence/harness/provider-evidence/`), which was dirtying the working tree
    on every harness run.
- **Deletion proposed (not applied):** the repo-root `tests/` directory — 17
  tracked files that duplicate `backend/tests/` one-for-one (identical
  `test_*` function sets; no root-only tests; zero references from any tracked
  file outside `tests/`; outside CI, which runs with `working-directory: backend`
  and only on `backend/**`; not part of the documented suite). Recommend
  `git rm -r tests/` as its own commit. Kept out of this change to avoid mixing a
  17-file deletion into a provider-focused diff.
- **Recommended (not applied):** add `login.json` to `.gitignore`. The file holds
  a placeholder credential pair (`test@example.com` / `password123`), not a real
  secret, but the name is credential-shaped.
- **Retained deliberately:** all 33 `evidence/` artifacts, `docs/`, `scripts/`
  data, `helm/`, `kubernetes/`, `docker/`, `grafana/`, `redops-gate/`,
  `plugins/` — each referenced by CI, tests, or documentation (recorded per file
  in the audit).
- No duplicate document content exists (SHA-256 comparison across all tracked
  `.md` / `.jsonl`).

## 3. Validation

All commands were run **without starting any server** (no uvicorn, no
`fastapi dev`, no `docker compose up`, no dev/prod frontend server).

| Check | Command | Result |
|---|---|---|
| Backend suite | `python -m pytest -q` (from `backend/`) | **3259 passed, 3 skipped** (skips are the opt-in live-provider smoke tests) |
| Provider + registration focus | `python -m pytest -q tests/providers tests/integration/test_provider_registration.py` | **541 passed, 3 skipped** |
| Lint | `python -m ruff check` (changed packages) | **All checks passed** |
| Types | `python -m mypy app/providers/groq app/core/config.py` | **Success: no issues found in 4 source files** |
| Metric sanity harness | `python evidence/harness/verify_metric_sanity.py` | **26 / 26 checks passed** (`all_checks_passed: true`) |
| Provider harness (structural) | `python evidence/harness/verify_providers.py` | openai: key present, request attempted, `RateLimitExceeded`; anthropic/groq: blocked (no credential). *Separate manual probe, not run this sprint; no live request was made by this sprint's work.* |
| Frontend install | `npm ci` (from `frontend/`) | succeeded on the committed lockfile, `0 vulnerabilities` |
| Frontend tests | `npx vitest run` | **31 passed (6 files)** |
| Frontend types | `npx tsc --noEmit` | **exit 0** |
| Frontend lint | `npx eslint .` | **0 errors, 8 warnings** (pre-existing `no-explicit-any` warnings) |
| Frontend build | `npx next build` | **exit 0** |
| Metric validation CLI | `python scripts/validate_metrics.py` | refuses by design ("Corpus is not marked as genuine ground truth") — the honest failure the script is specified to produce; covered by `backend/tests/scripts/test_validate_metrics.py` |
| `opencode.md` | inspected | absent from the repository (verified) |

Backend baseline before this sprint was 3243 passed / 3 skipped; the 16 added
tests bring it to 3259. Frontend stayed at 31 passed / 6 files.

Notes for reproducibility: run the backend suite **from `backend/`** — the root
run misses `asyncio_mode = "auto"` from `backend/pyproject.toml`. `redops-eval`
is editable-installed against `backend/`, so the local `app` package wins.

## 4. Git

- Work happened directly on `main`; no force-push, no artificial commits.
- One pre-existing commit was corrupted by a failed local file-rewrite attempt
  and was fully restored from `HEAD` (`git checkout --`), then re-fixed textually:
  `backend/tests/redteam/temporal/test_metrics_persistence_retryability.py`
  (3 mojibake characters only). No user work was lost; that file is the only
  content this sprint touched outside the Groq change, `README.md`,
  `.env.example`, `.gitignore`, and `evidence/`.
- Pre-existing untracked user files were preserved untouched: `AGENTS.md`,
  `AUTONOMOUS_MASTER_PROGRESS.md`, `graphify-out/`, `login.json`.
- `frontend/package-lock.json` was **not** modified (`npm ci` on the committed
  lockfile succeeded; verified length 326239 bytes unchanged) — the previous
  sprint's lockfile repair holds.
- No secret appeared in any diff, log, or evidence file.

Commits pushed to `origin/main` (fast-forward, no force-push):

| SHA | Commit |
|---|---|
| `e4d03c8` | `feat(providers): make Groq credentials, model, and identity explicit` |
| `50b1952` | `chore: repair text encoding, ignore generated harness output, add cleanup audit` |
| `0eadc5f` | `test(evidence): add Groq judge case to metric-sanity harness and record finalization` |
| `be6f523` | `docs(evidence): record pushed SHAs and final HEAD in finalization report` |
| `d1f0fd8` | `docs(evidence): finalize report with HEAD be6f523` |
| `b82fc31` | `docs(evidence): point finalization report at final HEAD` |
| `3b1e898` | `docs(evidence): record final HEAD sha in finalization report` |
| `f99256d` | `docs(evidence): sync finalization report commit log` |
| `f50506f` | `docs(evidence): update finalization report HEAD reference` |

Final state: `HEAD == origin/main == f50506f` (previous tip `2a19647`). Working
tree clean apart from the pre-existing untracked user files listed above.
`git diff --check` reports no whitespace errors.

## 5. Remaining actions

1. **Live Groq verification — NOT RUN.** Set `GROQ_API_KEY` (and optionally
   `GROQ_MODEL`) and run `backend/tests/providers/test_live_provider_smoke.py`
   (opt-in, real credit spend) to confirm the live path end to end.
2. **Decide on root `tests/` deletion** (`git rm -r tests/`) — evidence and
   rationale in `evidence/repository-cleanup-audit.md` §3.
3. **Add `login.json` to `.gitignore`** if that file may ever hold a real
   credential.
4. **OpenAI live calls remain blocked** by `insufficient_quota` (HTTP 429,
   `credit_balance_exhausted`) — unchanged from the previous sprint and unrelated
   to this work.
5. Optional editorial: link `docs/evaluation/METRIC_VALIDATION.md` from
   `docs/index.md` (currently the only orphan document).
