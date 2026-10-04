"""DOM / accessibility grounding via CDP Accessibility.getFullAXTree."""

from __future__ import annotations

import re
from typing import Any

from emily.browser.models import DomGrounding, DomNode

_ACTIONABLE_ROLES = {
    "button",
    "link",
    "textbox",
    "searchbox",
    "checkbox",
    "radio",
    "combobox",
    "menuitem",
    "tab",
    "switch",
}

_SKIP_ROLES = {
    "",
    "none",
    "generic",
    "InlineTextBox",
    "StaticText",
    "LineBreak",
    "Ignored",
}


def _ax_string(prop: Any) -> str:
    if prop is None:
        return ""
    if isinstance(prop, dict):
        return str(prop.get("value") or "")
    return str(prop)


def nodes_from_ax_tree(raw_nodes: list[dict[str, Any]], *, max_nodes: int = 120) -> list[DomNode]:
    """Convert CDP Accessibility.getFullAXTree nodes into DomNode list."""
    out: list[DomNode] = []
    counter = 0
    for node in raw_nodes:
        if not isinstance(node, dict) or node.get("ignored"):
            continue
        role = _ax_string(node.get("role")).strip()
        name = _ax_string(node.get("name")).strip()
        value = _ax_string(node.get("value")).strip()
        if role in _SKIP_ROLES and not name:
            continue
        actionable = role.lower() in _ACTIONABLE_ROLES or bool(name)
        if not actionable and role.lower() in {"document", "webarea", "rootwebarea"}:
            continue
        if not role and not name:
            continue
        counter += 1
        hint = f"role={role}[name={name[:80]}]" if role and name else (f"role={role}" if role else "")
        out.append(
            DomNode(
                ref=f"e{counter}",
                role=role,
                name=name,
                selector_hint=hint,
                value=value,
                actionable=actionable,
            )
        )
        if len(out) >= max_nodes:
            break
    return out


async def capture_grounding(page: Any, *, max_nodes: int = 120) -> DomGrounding:
    """Build a grounded DOM snapshot from CDP AX tree + body text."""
    url = page.url
    title = await page.title()
    session = await page.context.new_cdp_session(page)
    try:
        payload = await session.send("Accessibility.getFullAXTree")
    finally:
        await session.detach()

    raw_nodes = payload.get("nodes") if isinstance(payload, dict) else None
    nodes = nodes_from_ax_tree(list(raw_nodes or []), max_nodes=max_nodes)

    text_preview = ""
    try:
        text_preview = await page.inner_text("body")
    except Exception:
        text_preview = ""
    text_preview = re.sub(r"\s+", " ", text_preview).strip()[:1200]

    return DomGrounding(
        url=url,
        title=title,
        nodes=nodes,
        text_preview=text_preview,
    )


def resolve_selector(
    *,
    selector: str | None = None,
    ref: str | None = None,
    grounding: DomGrounding | None = None,
    role: str | None = None,
    name: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Return (mode, payload) where mode is css|role|ref."""
    if selector:
        return "css", {"selector": selector}
    if role:
        return "role", {"role": role, "name": name or ""}
    if ref and grounding is not None:
        for node in grounding.nodes:
            if node.ref == ref:
                if node.role:
                    return "role", {"role": node.role, "name": node.name}
                if node.selector_hint.startswith("role="):
                    return "role", {"role": node.role or "generic", "name": node.name}
        raise KeyError(f"unknown grounding ref: {ref}")
    raise ValueError("selector, role, or ref required")
