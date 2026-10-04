"""Cryptographically hash-chained audit logger for enterprise security tracing."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from emily.core.ids import new_id


@dataclass
class AuditRecord:
    record_id: str
    event_type: str
    actor: str
    details: dict[str, Any]
    prev_hash: str
    record_hash: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "details": self.details,
            "prev_hash": self.prev_hash,
            "record_hash": self.record_hash,
            "timestamp": self.timestamp.isoformat(),
        }


class AuditLogger:
    """Tamper-evident hash-chained audit log recorder."""

    def __init__(self, log_path: Path | str | None = None) -> None:
        self.log_path = Path(log_path) if log_path else Path("logs/audit.jsonl")
        self._last_hash: str = "GENESIS"

    def record_event(self, event_type: str, actor: str, details: dict[str, Any] | None = None) -> AuditRecord:
        """Record an audit event into the tamper-evident log."""
        rec_id = new_id("audit")
        now = datetime.now(UTC)
        payload = {
            "record_id": rec_id,
            "event_type": event_type,
            "actor": actor,
            "details": details or {},
            "prev_hash": self._last_hash,
            "timestamp": now.isoformat(),
        }
        serialized = json.dumps(payload, sort_keys=True)
        rec_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        record = AuditRecord(
            record_id=rec_id,
            event_type=event_type,
            actor=actor,
            details=details or {},
            prev_hash=self._last_hash,
            record_hash=rec_hash,
            timestamp=now,
        )
        self._last_hash = rec_hash
        self._append_to_file(record)
        return record

    def log_event(self, event_type: str, details: dict[str, Any] | None = None, actor: str = "system") -> AuditRecord:
        """Convenience alias for record_event."""
        return self.record_event(event_type=event_type, actor=actor, details=details)

    def _append_to_file(self, record: AuditRecord) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

    def verify_integrity(self) -> bool:
        """Verify hash chain integrity across all records in log file."""
        if not self.log_path.exists():
            return True
        last_h = "GENESIS"
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line.strip())
                if d.get("prev_hash") != last_h:
                    return False
                payload = {
                    "record_id": d["record_id"],
                    "event_type": d["event_type"],
                    "actor": d["actor"],
                    "details": d["details"],
                    "prev_hash": d["prev_hash"],
                    "timestamp": d["timestamp"],
                }
                expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
                if d.get("record_hash") != expected:
                    return False
                last_h = expected
        return True
