# Parallel Execution

> **Status:** Architecture Design  
> **Depends on:** [EXECUTION_MODEL.md](EXECUTION_MODEL.md), [CHECKPOINTING.md](CHECKPOINTING.md)

---

## 1. Purpose

Parallel execution distributes evaluation items across multiple workers to reduce total evaluation time. This document defines the partitioning strategy, coordination mechanism, and consistency guarantees.

---

## 2. When to Use Parallel Execution

| Scenario | Parallel? | Rationale |
|---|---|---|
| Dataset > 100 items | Yes | Reduces wall-clock time |
| Dataset <= 100 items | No | Overhead exceeds benefit |
| Provider has strict rate limits | No | Serial execution respects rate limits |
| Provider supports concurrency | Yes | Higher throughput |
| Cost-sensitive evaluation | No | Parallel calls may exceed rate limits, triggering retries |

---

## 3. Partitioning Strategy

### 3.1 Dataset Partitioning

The dataset is partitioned into non-overlapping chunks:

```
Dataset: [item_1, item_2, ..., item_1000]
Partition size: 100

Partition 0: [item_1, ..., item_100]
Partition 1: [item_101, ..., item_200]
Partition 2: [item_201, ..., item_300]
...
Partition 9: [item_901, ..., item_1000]
```

### 3.2 Partition Size Calculation

```python
def calculate_partition_size(
    total_items: int,
    max_concurrency: int,
    items_per_partition: int = 100,
) -> int:
    """Balance partition size with available concurrency."""
    desired_partitions = max(1, total_items // items_per_partition)
    effective_partitions = min(desired_partitions, max_concurrency)
    return math.ceil(total_items / effective_partitions)
```

### 3.3 Fixed vs Dynamic Partitioning

| Approach | Description | Tradeoff |
|---|---|---|
| **Fixed** | All partitions created upfront | Simple, but may imbalance if items vary in complexity |
| **Dynamic** | Work-stealing between partitions | Better load balancing, more complex coordination |

**Decision:** Use fixed partitioning for v1. Dynamic partitioning can be added later if profiling shows imbalance.

---

## 4. Coordination Model

### 4.1 Temporal Child Workflows

Each partition is processed by a Temporal child workflow:

```
ParentWorkflow: EvaluationRunWorkflow
    │
    ├── ChildWorkflow: PartitionWorkflow(partition=0)
    │   Activities: ExecuteItem for items 1-100
    │
    ├── ChildWorkflow: PartitionWorkflow(partition=1)
    │   Activities: ExecuteItem for items 101-200
    │
    ├── ChildWorkflow: PartitionWorkflow(partition=2)
    │   Activities: ExecuteItem for items 201-300
    │
    └── AggregateResults (waits for all children)
```

### 4.2 Child Workflow Lifecycle

```
ParentWorkflow
    │
    ├── for each partition:
    │       child = start_child_workflow(PartitionWorkflow, partition_data)
    │
    ├── await all children (Temporal handles concurrency)
    │
    ├── collect results from each child
    │
    └── aggregate and persist
```

### 4.3 Child Workflow Failure Handling

| Failure | Parent Behavior |
|---|---|
| One child fails | Parent continues. Failed items recorded as FAILED. |
| All children fail | Parent fails. |
| Parent cancelled | All children cancelled. |
| Parent timeout | Children cancelled. |

---

## 5. Concurrency Limits

### 5.1 Max Concurrent Partitions

```python
evaluation.max_concurrent_partitions: 10  # Default

# Set based on:
# - Provider rate limits
# - Worker pool size
# - Database connection pool size
# - Cost constraints
```

### 5.2 Max Concurrent Items Per Partition

Each partition workflow processes items sequentially within the partition. Parallelism comes from running multiple partitions concurrently.

```
Partition 0: item_1 → item_2 → item_3 → ... (sequential)
Partition 1: item_101 → item_102 → item_103 → ... (sequential)
Partition 2: item_201 → item_202 → item_203 → ... (sequential)
```

**Rationale:** Sequential within partition simplifies checkpointing and reduces provider pressure. Parallelism comes from partition-level concurrency.

### 5.3 Provider-Specific Concurrency

Some providers support higher concurrency than others:

```python
ProviderConcurrencyConfig {
    "openai": {
        "max_concurrent_partitions": 5,
        "max_concurrent_items_per_partition": 1,
        "rate_limit_rpm": 500,
    },
    "anthropic": {
        "max_concurrent_partitions": 3,
        "max_concurrent_items_per_partition": 1,
        "rate_limit_rpm": 200,
    },
    "local": {
        "max_concurrent_partitions": 10,
        "max_concurrent_items_per_partition": 1,
        "rate_limit_rpm": 999999,
    },
}
```

---

## 6. Result Aggregation

### 6.1 Partition-Level Results

Each child workflow returns its results to the parent:

```python
PartitionResult {
    partition_index:    int
    items_completed:    int
    items_failed:       int
    item_results:       list[ItemResult]
    partition_tokens:   TokenUsage
    partition_cost:     CostBreakdown
    duration_ms:        int
}
```

### 6.2 Aggregation Logic

The parent workflow aggregates partition results:

```python
async def aggregate_results(
    partition_results: list[PartitionResult],
) -> AggregatedMetrics:
    all_item_results = []
    total_tokens = TokenUsage()
    total_cost = CostBreakdown()

    for pr in partition_results:
        all_item_results.extend(pr.item_results)
        total_tokens = total_tokens + pr.partition_tokens
        total_cost = total_cost + pr.partition_cost

    # Compute aggregated metrics across all items
    metrics = compute_aggregated_metrics(all_item_results)

    return AggregatedMetrics(
        metrics=metrics,
        total_items=len(all_item_results),
        total_tokens=total_tokens,
        total_cost=total_cost,
    )
```

---

## 7. Checkpointing in Parallel Execution

### 7.1 Checkpoint Scope

Each partition checkpoints independently. The parent aggregates partition checkpoints:

```
ParentCheckpoint {
    run_id:                 UUIDv7
    checkpoint_number:      int
    partition_checkpoints:  dict[int, PartitionCheckpoint]  # Per-partition state
    aggregated_metrics:     dict[str, AggregatedMetrics]
    aggregated_tokens:      TokenUsage
    aggregated_cost:        CostBreakdown
}
```

### 7.2 Resume Strategy

On resume, the parent loads partition checkpoints and resumes only the failed/incomplete partitions:

```python
async def resume_parallel_run(checkpoint: ParentCheckpoint):
    for partition_index, partition_checkpoint in checkpoint.partition_checkpoints.items():
        if partition_checkpoint.status == PartitionStatus.COMPLETED:
            continue  # Skip completed partitions
        # Resume incomplete partition
        start_child_workflow(PartitionWorkflow, partition_checkpoint)
```

---

## 8. Backpressure

### 8.1 Purpose

Backpressure prevents overwhelming providers or workers when partitions complete at different speeds.

### 8.2 Mechanism

The parent workflow limits the number of concurrent child workflows:

```python
# Temporal handles this via task queue concurrency limits
# max_concurrent_workflow_tasks controls how many child workflows
# can execute simultaneously
```

### 8.3 Adaptive Concurrency

If provider rate limits are encountered, reduce concurrent partitions:

```python
# In parent workflow
if rate_limit_encountered:
    max_concurrent_partitions = max(1, max_concurrent_partitions - 1)
    # Notify remaining children to slow down
```

---

## 9. Monitoring Parallel Execution

### 9.1 Per-Partition Metrics

```
evaluation_partition_duration_seconds{partition="0"} 45.2
evaluation_partition_duration_seconds{partition="1"} 38.7
evaluation_partition_duration_seconds{partition="2"} 52.1
evaluation_partition_items_completed{partition="0"} 100
evaluation_partition_items_failed{partition="1"} 2
```

### 9.2 Imbalance Detection

If partition durations vary significantly (> 2x median), alert for investigation:

```
Imbalanced partitions detected:
  Partition 0: 45s
  Partition 1: 95s (2.1x median)
  Partition 2: 42s
  Consider: dataset item complexity variation or provider throttling
```
