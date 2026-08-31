"""Pydantic schemas for the Red Team & Safety API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AttackDefinitionResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    category: str
    severity: str
    status: str = "draft"
    prompt_template: str = ""
    system_prompt_override: str | None = None
    expected_behavior: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_by: str | None = None
    version: int = 1
    created_at: str
    updated_at: str


class AttackDefinitionSummary(BaseModel):
    id: str
    name: str
    category: str
    severity: str
    status: str
    version: int
    created_at: str
    updated_at: str


class AttackDefinitionListResponse(BaseModel):
    items: list[AttackDefinitionSummary] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateAttackDefinitionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    category: str = "prompt_injection"
    severity: str = "medium"
    prompt_template: str = ""
    system_prompt_override: str | None = None
    expected_behavior: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_by: str | None = None


class UpdateAttackDefinitionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = None
    severity: str | None = None
    prompt_template: str | None = None
    system_prompt_override: str | None = None
    expected_behavior: str | None = None
    parameters: dict[str, Any] | None = None
    tags: list[str] | None = None


class AttackRunResponse(BaseModel):
    id: str
    evaluation_run_id: str | None = None
    status: str
    attack_definition_ids: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    items_total: int = 0
    items_completed: int = 0
    items_passed: int = 0
    items_violated: int = 0
    items_failed: int = 0
    progress: float = 0.0
    campaign_results: dict[str, Any] | None = None
    version: int = 1
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str
    updated_at: str


class AttackRunSummary(BaseModel):
    id: str
    evaluation_run_id: str | None = None
    status: str
    items_total: int = 0
    items_completed: int = 0
    progress: float = 0.0
    version: int = 1
    created_at: str
    updated_at: str


class AttackRunListResponse(BaseModel):
    items: list[AttackRunSummary] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateAttackRunRequest(BaseModel):
    evaluation_run_id: str | None = None
    attack_definition_ids: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)


class StartAttackRunRequest(BaseModel):
    total_items: int = 0


class FailAttackRunRequest(BaseModel):
    error_message: str = ""
