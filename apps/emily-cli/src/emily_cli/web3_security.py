"""CLI-facing helpers for local Web3 security audits; no network scanner or submit command."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emily_web3_security import audit_directory, import_program_file
from emily_web3_security.models import to_dict


def audit_local(source_root: str) -> dict[str, Any]:
    run, findings = audit_directory(Path(source_root))
    return {"run": to_dict(run), "findings": [to_dict(f) for f in findings], "network_scanning": False}


def import_program(path: str) -> dict[str, Any]:
    program = import_program_file(path)
    return {"id": program.id, "name": program.name, "source_url": program.rules.source_url,
            "source_hash": program.rules.source_hash}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Emily local-only Web3 forensics")
    parser.add_argument("source", help="local source directory")
    print(json.dumps(audit_local(parser.parse_args().source), default=str, indent=2))


if __name__ == "__main__":
    main()
