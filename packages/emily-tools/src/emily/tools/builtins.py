"""Built-in tools."""

from __future__ import annotations

import ast
import operator
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from emily.core.types.tool import ToolPermissionLevel
from emily.tools.models import ToolSource, ToolSpec
from emily.tools.registry import ToolRegistry

_OPS: dict[type[ast.AST], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expr: str) -> float | int:
    node = ast.parse(expr, mode="eval")

    def _eval(n: ast.AST) -> float | int:
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            op = _OPS[type(n.op)]
            result = op(_eval(n.left), _eval(n.right))
            assert isinstance(result, (int, float))
            return result
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            op = _OPS[type(n.op)]
            result = op(_eval(n.operand))
            assert isinstance(result, (int, float))
            return result
        raise ValueError("unsupported expression")

    return _eval(node)


def register_builtins(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="echo",
            title="Echo",
            description="Return the provided message unchanged",
            permissions=[ToolPermissionLevel.READ],
            source=ToolSource.BUILTIN,
            input_schema={"message": {"type": "string"}},
        ),
        _echo,
    )
    registry.register(
        ToolSpec(
            name="clock.now",
            title="Clock Now",
            description="Return the current UTC timestamp",
            permissions=[ToolPermissionLevel.READ],
            source=ToolSource.BUILTIN,
        ),
        _clock_now,
    )
    registry.register(
        ToolSpec(
            name="math.eval",
            title="Safe Math Eval",
            description="Evaluate a simple arithmetic expression",
            permissions=[ToolPermissionLevel.EXECUTE],
            source=ToolSource.BUILTIN,
            input_schema={"expression": {"type": "string"}},
        ),
        _math_eval,
    )
    registry.register(
        ToolSpec(
            name="text.stats",
            title="Text Stats",
            description="Count characters, words, and lines",
            permissions=[ToolPermissionLevel.READ],
            source=ToolSource.BUILTIN,
            input_schema={"text": {"type": "string"}},
        ),
        _text_stats,
    )


async def _echo(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    message = str(arguments.get("message", ""))
    return {"message": message}


async def _clock_now(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    _ = arguments
    now = datetime.now(UTC)
    return {"iso": now.isoformat(), "epoch_ms": int(now.timestamp() * 1000)}


async def _math_eval(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    expression = str(arguments.get("expression", "")).strip()
    if not expression:
        raise ValueError("expression is required")
    value = _safe_eval(expression)
    return {"expression": expression, "value": value}


async def _text_stats(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    text = str(arguments.get("text", ""))
    lines = text.splitlines() or ([text] if text else [])
    words = [w for w in text.split() if w]
    return {
        "chars": len(text),
        "words": len(words),
        "lines": len(lines),
    }
