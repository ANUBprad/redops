# Execution Pipeline

> **Status:** Architecture Design  
> **Depends on:** [EVALUATION_ENGINE.md](EVALUATION_ENGINE.md), [STATE_MACHINE.md](STATE_MACHINE.md)

---

## 1. Purpose

The Execution Pipeline defines the ordered sequence of stages that transform a dataset item into a scored result. Each stage is a discrete, testable, and replaceable unit. The pipeline is the inner loop of the Evaluation Engine — executed once per item per model.

---

## 2. Pipeline Architecture

### 2.1 Stage Chain

```
Input: EvaluationItem + EvaluationProfile
  │
  ▼
┌─────────────────────────┐
│  1. Template Rendering   │  Render prompt templates with item variables
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  2. Context Assembly     │  Assemble messages, tools, system prompt
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  3. Provider Invocation  │  Call provider through contract
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  4. Response Parsing     │  Validate and normalize response
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  5. Output Validation    │  Check response against constraints
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  6. Metric Computation   │  Dispatch to metric plugins
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│  7. Result Assembly      │  Build ItemResult from all outputs
└────────────┬────────────┘
             ▼
Output: ItemResult
```

### 2.2 Stage Contract

Every stage implements the same protocol:

```
PipelineStage {
    name:               str
    stage_type:         StageType

    async execute(
        context: PipelineContext,
    ) -> PipelineContext

    async compensate(
        context: PipelineContext,
    ) -> None
}
```

**Key design decision:** Stages receive and return the same `PipelineContext` object. This makes stages composable, testable, and independently replaceable. The context carries all data through the pipeline without the stages needing to know about each other.

### 2.3 Pipeline Context

The `PipelineContext` is an immutable-at-rest, mutable-during-execution carrier:

```
PipelineContext {
    # Input (set before pipeline starts)
    item:                EvaluationItem
    profile:             EvaluationProfile
    evaluation:          Evaluation

    # Populated by stages
    rendered_prompt:     str | None              # after TemplateRendering
    messages:            list[Message] | None    # after ContextAssembly
    chat_options:        ChatOptions | None      # after ContextAssembly
    provider_response:   ChatResponse | None     # after ProviderInvocation
    parsed_output:       ParsedOutput | None     # after ResponseParsing
    validation_result:   ValidationResult | None # after OutputValidation
    metric_results:      dict[str, MetricResult] # after MetricComputation

    # Metadata
    stage_timings:       dict[str, float]        # stage_name → duration_ms
    warnings:            list[str]
    correlation_id:      str
}
```

---

## 3. Stage Definitions

### 3.1 Template Rendering

**Purpose:** Replace template variables in the prompt with actual values from the dataset item.

**Input:** `item.input` (dict of variables) + `profile.system_prompt` / dataset prompt template  
**Output:** `context.rendered_prompt`

**Behavior:**
- Supports Jinja2-style template syntax: `{{ variable_name }}`
- Validates that all required template variables are present
- Fails the item (not the run) if required variables are missing
- Supports nested variable access: `{{ context.passages[0].text }}`

**Failure mode:** `TemplateRenderError` → item marked FAILED, run continues.

**Compensation:** None required (no side effects).

---

### 3.2 Context Assembly

**Purpose:** Transform the rendered prompt into the provider's expected message format.

**Input:** `context.rendered_prompt` + `profile` + `item.input`  
**Output:** `context.messages`, `context.chat_options`

**Behavior:**
- Constructs `Message.system(profile.system_prompt)` if present
- Constructs `Message.user(context.rendered_prompt)`
- For RAG evaluation: assembles context passages into user message or separate messages
- For multi-turn evaluation: constructs conversation from dataset history
- Builds `ChatOptions` from profile parameters
- Attaches tool definitions if profile specifies tools

**Failure mode:** `ContextAssemblyError` → item marked FAILED.

**Compensation:** None required.

---

### 3.3 Provider Invocation

**Purpose:** Call the AI provider through the Provider Framework contract.

**Input:** `context.messages` + `context.chat_options` + `profile.provider_name` + `profile.model_id`  
**Output:** `context.provider_response`

**Behavior:**
- Resolves provider from `ProviderRegistry.resolve(provider_name)`
- Verifies provider supports required capabilities via `provider.supports()`
- Calls `provider.chat(messages, model=model_id, options=options)`
- Captures `ChatResponse` including `content`, `tool_calls`, `usage`, `finish_reason`
- Records latency and token usage for cost tracking
- Publishes `ProviderInvoked` event

**Failure modes:**
| Error | Handler |
|---|---|
| `ProviderUnavailable` | Retry with backoff (see RETRY_POLICY.md) |
| `RateLimitExceeded` | Retry with `retry_after_seconds` |
| `ContextWindowExceeded` | Fail item, log, continue run |
| `ProviderTimeout` | Retry with backoff |
| `InvalidModel` | Fail run (configuration error) |
| `AuthenticationRequired` | Fail run (configuration error) |

**Compensation:** None (provider invocation is idempotent for reads).

---

### 3.4 Response Parsing

**Purpose:** Validate and normalize the raw provider response into a structured format.

**Input:** `context.provider_response`  
**Output:** `context.parsed_output`

**Behavior:**
- Extracts text content from `ChatResponse.content`
- Parses tool calls if present (for tool-calling evaluations)
- Handles streaming chunk reassembly (if streaming was used)
- Normalizes finish reasons to internal enum
- Extracts reasoning content if present (for reasoning models)
- Validates response is not empty

**Failure modes:**
| Error | Handler |
|---|---|
| Empty response | Retry once, then fail item |
| Malformed tool calls | Fail item, log warning |
| Unexpected format | Fail item with detail |

**Compensation:** None required.

---

### 3.5 Output Validation

**Purpose:** Check the response against evaluation-specific constraints before computing metrics.

**Input:** `context.parsed_output` + `context.item` + `context.evaluation`  
**Output:** `context.validation_result`

**Behavior:**
- For safety evaluations: check for policy violations, harmful content
- For regression evaluations: check response is within acceptable deviation from baseline
- For structured output: validate JSON schema compliance
- For tool-calling: validate tool call format and arguments
- Sets `validation_result.passed` to determine if metrics should be computed

**Failure modes:**
| Error | Handler |
|---|---|
| Validation failure | Record as `SKIPPED` item, do not compute metrics |
| Validation error | Fail item with detail |

**Compensation:** None required.

---

### 3.6 Metric Computation

**Purpose:** Dispatch the parsed output to all configured metric plugins and collect results.

**Input:** `context.parsed_output` + `context.item` + `context.evaluation.metric_configs`  
**Output:** `context.metric_results`

**Behavior:**
- Iterates over `evaluation.metric_configs`
- For each config, resolves the metric plugin from `PluginRegistry`
- Constructs `MetricRequest` with:
  - `prediction`: the model's output
  - `reference`: the expected output (if dataset provides one)
  - `context`: the input context (for context-dependent metrics)
  - `metadata`: additional context (model, provider, latency, etc.)
- Calls `metric_plugin.compute(request)` for each metric
- Captures `MetricResult` with score, details, and metadata
- Publishes `MetricCompleted` event per metric
- **Continues even if individual metrics fail** — records failure in `metric_results`

**Failure modes:**
| Error | Handler |
|---|---|
| Metric plugin not found | Skip metric, log warning |
| Metric computation error | Record as `metric_error`, continue with other metrics |
| Metric timeout | Record as `metric_timeout`, continue |

**Compensation:** None required (metrics are pure computations).

**Critical invariant:** Metric failures never cause item or run failures. The run completes with partial metrics.

---

### 3.7 Result Assembly

**Purpose:** Combine all pipeline outputs into a final `ItemResult`.

**Input:** All populated fields in `PipelineContext`  
**Output:** `ItemResult`

**Behavior:**
- Constructs `ItemResult` from:
  - `item.item_id`
  - `item.rendered_prompt`
  - `context.provider_response` (raw)
  - `context.parsed_output` (normalized)
  - `context.metric_results` (all computed)
  - `context.validation_result`
  - `context.stage_timings` (performance data)
- Marks item as `COMPLETED` or `SKIPPED` based on validation
- Persists result through repository
- Publishes `ItemCompleted` event

**Compensation:** Result persistence is idempotent (upsert by `item_id`).

---

## 4. Pipeline Variants

The pipeline stages are fixed, but the execution strategy varies by evaluation type:

### 4.1 Single Prompt

```
TemplateRendering → ContextAssembly → ProviderInvocation → ResponseParsing → OutputValidation → MetricComputation → ResultAssembly
```

No dataset iteration. One item, one result.

### 4.2 Dataset Evaluation

```
For each row in dataset:
    TemplateRendering → ContextAssembly → ProviderInvocation → ResponseParsing → OutputValidation → MetricComputation → ResultAssembly
Aggregate → Persist → Report
```

Items processed in parallel (see PARALLEL_EXECUTION.md).

### 4.3 Regression Testing

Same as Dataset Evaluation, but `OutputValidation` includes baseline comparison logic. Metrics include delta calculations against baseline scores.

### 4.4 Safety Testing

Same as Dataset Evaluation, but `OutputValidation` includes safety classifier checks. Additional safety-specific metrics are auto-configured.

### 4.5 RAG Evaluation

Same as Dataset Evaluation, but `ContextAssembly` includes retrieval context from dataset. Additional RAG-specific metrics (faithfulness, relevance, context recall) are auto-configured.

> **Accuracy note:** RAG is not yet fully wired. The `RAGASAdapter`
> (`app/evaluation/evaluators/adapters.py`) maps `faithfulness`,
> `answer_relevancy`, `context_precision`, and `context_recall`, but it is **not
> registered into any engine** and `ragas` is **not a runtime dependency**. No
> RAGAS-backed metric is auto-configured today; the built-in `FaithfulnessMetric`
> and `ContextRelevanceMetric` use the standard (non-RAGAS) pipeline.

### 4.6 Multi-Model Comparison

```
For each model in comparison set:
    For each row in dataset:
        TemplateRendering → ContextAssembly → ProviderInvocation → ...
Aggregate per-model → Cross-model comparison → Persist → Report
```

Each model gets its own EvaluationRun. Comparison is post-hoc aggregation.

---

## 5. Extensibility: Adding a New Stage

To add a new pipeline stage (e.g., guardrail checking):

1. Implement `PipelineStage` protocol
2. Define `stage_type` and `name`
3. Implement `execute(context) -> context`
4. Implement `compensate(context) -> None` if side effects exist
5. Register the stage in the pipeline configuration
6. Insert at the desired position in the stage chain

**Example positions for new stages:**
- After `ProviderInvocation`: Output guardrails
- After `ResponseParsing`: Content filtering
- Before `MetricComputation`: Output normalization
- After `MetricComputation`: Metric validation

---

## 6. Performance Characteristics

| Metric | Target | Notes |
|---|---|---|
| Stage overhead (excl. provider) | < 10ms per stage | Minimal processing per stage |
| Total pipeline overhead | < 100ms per item | Excluding provider latency |
| Memory per item | < 1MB | PipelineContext is lightweight |
| Checkpoint serialization | < 5ms | Snapshot of PipelineContext |

---

## 7. Testing Strategy

| Component | Test Type | Approach |
|---|---|---|
| Individual stages | Unit test | Mock adjacent stages, verify context mutations |
| Pipeline chain | Integration test | Run full pipeline with mock provider |
| Stage compensation | Unit test | Verify side-effect reversal |
| Pipeline context | Unit test | Verify immutability semantics |
| Error propagation | Integration test | Verify stage failures propagate correctly |
