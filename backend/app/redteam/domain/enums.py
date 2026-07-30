"""Enums for the Red Team & Safety domain."""

from __future__ import annotations

from enum import Enum, unique

_ATTACK_STATUS_TERMINAL = frozenset({"completed", "failed", "cancelled"})
_ATTACK_STATUS_ACTIVE = frozenset({"queued", "starting", "running"})
_DEF_STATUS_EDITABLE = frozenset({"draft"})
_DEF_STATUS_TERMINAL = frozenset({"archived"})


@unique
class AttackCategory(Enum):
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    SYSTEM_PROMPT_EXTRACTION = "system_prompt_extraction"
    ROLE_MANIPULATION = "role_manipulation"
    CONTEXT_POISONING = "context_poisoning"
    INSTRUCTION_OVERRIDE = "instruction_override"
    TOOL_MISUSE = "tool_misuse"
    SENSITIVE_DATA_EXTRACTION = "sensitive_data_extraction"
    POLICY_CIRCUMVENTION = "policy_circumvention"
    OUTPUT_FORMAT_MANIPULATION = "output_format_manipulation"


@unique
class AttackSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@unique
class AttackStatus(Enum):
    CREATED = "created"
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self.value in _ATTACK_STATUS_TERMINAL

    @property
    def is_active(self) -> bool:
        return self.value in _ATTACK_STATUS_ACTIVE


@unique
class AttackDefinitionStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"

    @property
    def is_editable(self) -> bool:
        return self.value in _DEF_STATUS_EDITABLE

    @property
    def is_terminal(self) -> bool:
        return self.value in _DEF_STATUS_TERMINAL


@unique
class SafetyVerdict(Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    VIOLATED = "violated"
    LEAKED = "leaked"
    ERROR = "error"


@unique
class SafetyDimension(Enum):
    HARMlessness = "harmlessness"
    POLICY_COMPLIANCE = "policy_compliance"
    PROMPT_INTEGRITY = "prompt_integrity"
    DATA_CONFIDENTIALITY = "data_confidentiality"
    TOOL_GOVERNANCE = "tool_governance"
    OUTPUT_FIDELITY = "output_fidelity"
