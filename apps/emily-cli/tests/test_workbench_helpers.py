from __future__ import annotations

import pytest
import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).parents[1] / "src" / "emily_cli" / "workbench.py"
_SPEC = importlib.util.spec_from_file_location("workbench_helpers", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
bounded_text = _MODULE.bounded_text
is_local_origin = _MODULE.is_local_origin


def test_origin_policy_accepts_local_clients_only() -> None:
    assert is_local_origin(None)
    assert is_local_origin("http://localhost:5173")
    assert is_local_origin("http://127.0.0.1:8000")
    assert not is_local_origin("https://example.test")


def test_bounded_text_rejects_oversized_input() -> None:
    assert bounded_text(" hello ", name="message", maximum=10) == "hello"
    with pytest.raises(ValueError, match="character limit"):
        bounded_text("123456", name="message", maximum=5)
