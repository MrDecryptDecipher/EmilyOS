"""Explicit-source program import and bounded rules retrieval."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

from .models import BountyProgram, ProgramRules, Target, now_iso

MAX_RULE_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT = 10.0


def _rules(raw: dict[str, Any], source: str, content: bytes) -> BountyProgram:
    rules = raw.get("rules", raw)
    targets = [Target(**t) for t in raw.get("targets", [])]
    program_rules = ProgramRules(
        scope=str(rules.get("scope", "")), exclusions=list(rules.get("exclusions", [])),
        reward=str(rules.get("reward", "")), required_report_fields=list(rules.get("required_report_fields", [])),
        source_url=source, fetched_at=now_iso(), source_hash=hashlib.sha256(content).hexdigest(),
    )
    return BountyProgram(id=str(raw.get("id", hashlib.sha256(content).hexdigest()[:12])),
        name=str(raw.get("name", "Imported program")), platform=str(raw.get("platform", "")),
        rules=program_rules, targets=targets, catalog_entry=False)


def import_program_file(path: str | Path) -> BountyProgram:
    p = Path(path).expanduser().resolve()
    content = p.read_bytes()
    if len(content) > MAX_RULE_BYTES:
        raise ValueError("program definition exceeds maximum size")
    return _rules(json.loads(content), str(p), content)


def import_program_url(url: str, timeout: float = DEFAULT_TIMEOUT) -> BountyProgram:
    if not url.startswith(("https://", "http://")):
        raise ValueError("program URL must use HTTP(S)")
    request = urllib.request.Request(url, headers={"User-Agent": "Emily-Web3-Security/0.1 local importer"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = response.read(MAX_RULE_BYTES + 1)
    if len(content) > MAX_RULE_BYTES:
        raise ValueError("program definition exceeds maximum size")
    return _rules(json.loads(content), url, content)


def fetch_rules(program: BountyProgram, timeout: float = DEFAULT_TIMEOUT) -> BountyProgram:
    """Refresh only the program's already explicit source URL; never discovers URLs."""
    if not program.rules.source_url or Path(program.rules.source_url).exists():
        return import_program_file(program.rules.source_url) if program.rules.source_url else program
    return import_program_url(program.rules.source_url, timeout)


def import_catalog_entry(entry: dict[str, Any]) -> BountyProgram:
    """Import an explicit caller-supplied catalog entry; no scraping is performed."""
    content = json.dumps(entry, sort_keys=True).encode()
    result = _rules(entry, "catalog:explicit", content)
    result.catalog_entry = True
    return result


def ensure_target_allowed(program: BountyProgram, identifier: str) -> Target:
    """Resolve an exact allowlisted target; callers cannot audit an unlisted target."""
    for target in program.targets:
        if target.allowed and identifier in {target.identifier, target.name}:
            return target
    raise PermissionError("target is not explicitly allowlisted by the program")
