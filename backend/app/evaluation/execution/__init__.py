"""Execution pipeline layer.

Pure application-level abstractions that connect the Evaluation Domain
to future orchestration. Contains ZERO infrastructure dependencies.

This layer defines:
- ExecutionPlan: what to execute, deterministically and reproducibly
- PipelineContext: immutable context for execution
- ExecutionStage / ExecutionStep: composable execution units
- PipelineBuilder: transforms EvaluationRun → ExecutionPlan → Pipeline
- Execution contracts: interfaces for execution, observation, scheduling
- Execution events: domain events raised during execution lifecycle
"""
