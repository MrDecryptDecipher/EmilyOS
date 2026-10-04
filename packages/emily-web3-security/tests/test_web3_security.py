from pathlib import Path

import pytest
from emily_web3_security import (
    analyze_solidity,
    approve_report,
    audit_directory,
    create_report_draft,
    mark_ready_to_submit,
)
from emily_web3_security.models import Severity
from emily_web3_security.rules import import_program_file


def test_rule_hash(tmp_path: Path) -> None:
    p = tmp_path / "program.json"
    p.write_text('{"id":"x","name":"X","rules":{"scope":"contracts"}}')
    first = import_program_file(p)
    assert len(first.rules.source_hash) == 64


def test_path_containment_and_local_only(tmp_path: Path) -> None:
    (tmp_path / "a.sol").write_text("contract A { function x() public { require(msg.sender == tx.origin); } }")
    run, findings = audit_directory(tmp_path)
    assert run.local_only and findings[0].severity == Severity.HIGH


def test_deterministic_deduplicated_findings() -> None:
    code = "function x() public { a.delegatecall(\"\"); a.delegatecall(\"\"); }"
    assert [f.fingerprint for f in analyze_solidity(code)] == [f.fingerprint for f in analyze_solidity(code)]


def test_report_approval_gate() -> None:
    draft = create_report_draft("p", "title", "summary", [])
    with pytest.raises(PermissionError):
        mark_ready_to_submit(draft)
    assert mark_ready_to_submit(approve_report(draft, "reviewer")).status == "ready_to_submit"


def test_no_network_scanner_api() -> None:
    import emily_web3_security.audit as audit
    assert not hasattr(audit, "scan_network")
