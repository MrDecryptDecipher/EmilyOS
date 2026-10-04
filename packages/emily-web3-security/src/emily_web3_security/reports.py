"""Draft and explicit approval workflow. Submission and payout are intentionally absent."""
from __future__ import annotations

from dataclasses import replace

from .models import Approval, Finding, ReportDraft, now_iso


def create_report_draft(program_id: str, title: str, summary: str, findings: list[Finding], **platform_fields: str) -> ReportDraft:
    citations = sorted({f.rule_citation for f in findings if f.rule_citation})
    return ReportDraft(id=f"draft-{len(findings)}-{abs(hash((program_id, title))) % 10**8}", program_id=program_id,
        title=title, summary=summary, findings=[f.fingerprint for f in findings],
        platform_fields=platform_fields, remediation="Review the evidence locally, add a minimal test, and apply least-privilege controls.", rule_citations=citations)


def approve_report(draft: ReportDraft, approved_by: str, note: str = "") -> ReportDraft:
    if not approved_by.strip():
        raise ValueError("explicit approver identity is required")
    return replace(draft, approval=Approval(approved_by.strip(), now_iso(), note), status="approved")


def mark_ready_to_submit(draft: ReportDraft) -> ReportDraft:
    if draft.approval is None:
        raise PermissionError("report requires explicit approval before ready-to-submit")
    return replace(draft, status="ready_to_submit")


def submit_report(*_args: object, **_kwargs: object) -> None:
    raise NotImplementedError("network report submission is disabled")
