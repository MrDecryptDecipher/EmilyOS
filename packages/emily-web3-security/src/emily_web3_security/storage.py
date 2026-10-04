"""Small JSON persistence layer rooted at an explicitly configured directory."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import to_dict


class JsonStore:
    def __init__(self, data_root: str | Path):
        self.root = Path(data_root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, collection: str, key: str, value: Any) -> Path:
        path = self.root / collection / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = to_dict(value)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return path

    def load(self, collection: str, key: str) -> dict[str, Any]:
        path = self.root / collection / f"{key}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, collection: str) -> list[dict[str, Any]]:
        directory = self.root / collection
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]
