"""Deterministic offline analyzers. No sockets, RPC, scanners, or transactions."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .models import AuditRun, Finding, Severity, now_iso

_PATTERNS = [
    ("tx-origin-auth", r"tx\.origin", "tx.origin used in authorization", Severity.HIGH, .92),
    ("delegatecall", r"\.delegatecall\s*\(", "delegatecall usage requires review", Severity.MEDIUM, .84),
    ("unchecked-call", r"(?:\.call|\.send)\s*(?:\{|\()", "unchecked low-level call pattern", Severity.MEDIUM, .78),
    ("selfdestruct-auth", r"selfdestruct\s*\(", "selfdestruct requires access-control review", Severity.HIGH, .80),
    ("unbounded-loop", r"for\s*\([^;]*;[^;]*(?:\.length|;)[^;]*;", "loop bound may depend on unbounded data", Severity.LOW, .65),
    ("reentrancy-heuristic", r"(?:call|send|transfer)\s*\([^;]*\)[^;]*;[\s\S]{0,180}(?:=|\+=|-=)", "external call before state update (heuristic)", Severity.HIGH, .67),
]


def _finding(code: str, path: str, line: int, key: str, title: str, severity: Severity, confidence: float, evidence: str) -> Finding:
    fingerprint = hashlib.sha256(f"{key}|{path}|{line}|{evidence.strip()}".encode()).hexdigest()[:20]
    return Finding(fingerprint, fingerprint, title, severity, confidence, evidence.strip(), path, line, key)


def analyze_solidity(source: str, file: str = "<memory>") -> list[Finding]:
    findings: list[Finding] = []
    for key, pattern, title, severity, confidence in _PATTERNS:
        for match in re.finditer(pattern, source, re.IGNORECASE):
            line = source.count("\n", 0, match.start()) + 1
            evidence = source.splitlines()[line - 1][:240]
            findings.append(_finding(source, file, line, key, title, severity, confidence, evidence))
    # stable deduplication and ordering
    return sorted({f.fingerprint: f for f in findings}.values(), key=lambda f: (f.file, f.line, f.fingerprint))


def is_path_contained(root: str | Path, candidate: str | Path) -> bool:
    """Return whether candidate is within root, resolving traversal and symlinks."""
    root_path = Path(root).expanduser().resolve()
    candidate_path = Path(candidate).expanduser().resolve()
    return candidate_path == root_path or root_path in candidate_path.parents


def analyze_dependencies(root: str | Path) -> list[Finding]:
    root_path = Path(root).resolve()
    findings: list[Finding] = []
    for name in ("package-lock.json", "npm-shrinkwrap.json", "requirements-lock.txt", "poetry.lock", "yarn.lock"):
        path = root_path / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            findings.append(_finding(text, name, 1, "empty-lockfile", "Empty dependency lockfile", Severity.MEDIUM, .99, name))
    return findings


def analyze_abi(abi: list[dict[str, object]] | str) -> list[Finding]:
    data = json.loads(abi) if isinstance(abi, str) else abi
    out: list[Finding] = []
    for item in data:
        if item.get("type") == "function" and item.get("stateMutability") in ("payable", "nonpayable"):
            name = str(item.get("name", "<unnamed>"))
            out.append(_finding(name, "abi.json", 0, "abi-mutator", f"ABI mutating function: {name}", Severity.INFORMATIONAL, .99, name))
    return sorted(out, key=lambda f: f.fingerprint)


def audit_directory(root: str | Path) -> tuple[AuditRun, list[Finding]]:
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise ValueError("audit root must be a local directory")
    findings: dict[str, Finding] = {}
    run = AuditRun(id=hashlib.sha256(str(root_path).encode()).hexdigest()[:16], program_id="local", source_root=str(root_path))
    for path in sorted(root_path.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".sol", ".txt"}:
            continue
        if not is_path_contained(root_path, path):
            raise ValueError("source path escaped audit root")
        for finding in analyze_solidity(path.read_text(encoding="utf-8", errors="replace"), str(path.relative_to(root_path))):
            findings.setdefault(finding.fingerprint, finding)
    result = sorted(findings.values(), key=lambda f: (f.file, f.line, f.fingerprint))
    run.findings = [f.fingerprint for f in result]
    run.completed_at = now_iso()
    return run, result
