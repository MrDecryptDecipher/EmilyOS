"""Browser domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from emily.core.ids import new_id


class BrowserAction(StrEnum):
    OPEN = "open"
    GOTO = "goto"
    SNAPSHOT = "snapshot"
    CLICK = "click"
    TYPE = "type"
    FILL = "fill"
    EVAL = "eval"
    TABS = "tabs"
    CLOSE = "close"
    CDP = "cdp"


class BrowserTab(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab_id: str
    url: str = ""
    title: str = ""
    active: bool = False


class DomNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    role: str = ""
    name: str = ""
    tag: str = ""
    selector_hint: str = ""
    value: str = ""
    actionable: bool = False


class DomGrounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = ""
    title: str = ""
    nodes: list[DomNode] = Field(default_factory=list)
    text_preview: str = ""
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BrowserSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: str
    headless: bool
    tabs: list[BrowserTab] = Field(default_factory=list)
    grounding: DomGrounding | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrowserSessionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(default_factory=lambda: new_id("bsess"))
    profile: str
    user_data_dir: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
