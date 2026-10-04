"""Typed data models. Models contain no credentials, wallets, or executable actions."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Severity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TriageState(StrEnum):
    UNTRIAGED = "untriaged"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


@dataclass(slots=True)
class ProgramRules:
    scope: str = ""
    exclusions: list[str] = field(default_factory=list)
    reward: str = ""
    required_report_fields: list[str] = field(default_factory=list)
    source_url: str = ""
    fetched_at: str = ""
    source_hash: str = ""
    terms_note: str = "Rules imported from a user-provided source; confirm current terms manually."


@dataclass(slots=True)
class Target:
    name: str
    kind: str = "contract"
    identifier: str = ""
    allowed: bool = True
    notes: str = ""


@dataclass(slots=True)
class BountyProgram:
    id: str
    name: str
    platform: str = ""
    rules: ProgramRules = field(default_factory=ProgramRules)
    targets: list[Target] = field(default_factory=list)
    catalog_entry: bool = False


@dataclass(slots=True)
class AuditRun:
    id: str
    program_id: str
    source_root: str
    started_at: str = field(default_factory=now_iso)
    completed_at: str = ""
    findings: list[str] = field(default_factory=list)
    local_only: bool = True


@dataclass(slots=True)
class Finding:
    id: str
    fingerprint: str
    title: str
    severity: Severity
    confidence: float
    evidence: str
    file: str = ""
    line: int = 0
    rule_citation: str = ""
    triage: TriageState = TriageState.UNTRIAGED
    heuristic: bool = True


@dataclass(slots=True)
class Approval:
    approved_by: str
    approved_at: str = field(default_factory=now_iso)
    note: str = ""


@dataclass(slots=True)
class ReportDraft:
    id: str
    program_id: str
    title: str
    summary: str
    findings: list[str] = field(default_factory=list)
    platform_fields: dict[str, str] = field(default_factory=dict)
    reproduce_safely: str = "Reproduce only in a local test fixture; do not contact live targets."
    remediation: str = ""
    rule_citations: list[str] = field(default_factory=list)
    triage: TriageState = TriageState.UNTRIAGED
    approval: Approval | None = None
    status: str = "draft"


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {k: to_dict(v) for k, v in asdict(value).items()}
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, list):
        return [to_dict(v) for v in value]
    if isinstance(value, dict):
        return {k: to_dict(v) for k, v in value.items()}
    return value
