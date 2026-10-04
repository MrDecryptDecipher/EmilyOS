"""Browser runtime facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.browser.engine import PlaywrightEngine
from emily.browser.errors import BrowserError
from emily.browser.models import (
    BrowserAction,
    BrowserSnapshot,
    BrowserTab,
    DomGrounding,
)
from emily.browser.policy import BrowserPolicy


class BrowserRuntime:
    """Primary API for browser automation."""

    def __init__(
        self,
        *,
        settings: Any | None = None,
        event_bus: Any | None = None,
        logger: Any | None = None,
        profiles_root: Path | str | None = None,
    ) -> None:
        self.settings = settings
        self.event_bus = event_bus
        self.logger = logger
        self.policy = BrowserPolicy(settings)
        if profiles_root is not None:
            root = Path(profiles_root)
        elif settings is not None:
            root = Path(getattr(settings, "browser_profiles_directory", Path("data/browser/profiles")))
        else:
            root = Path("data/browser/profiles")
        profile = str(getattr(settings, "browser_default_profile", "default") if settings else "default")
        headless = bool(getattr(settings, "browser_headless", True) if settings else True)
        channel = getattr(settings, "browser_channel", None) if settings else None
        self.engine = PlaywrightEngine(
            profile=profile,
            profiles_root=root,
            headless=headless,
            channel=str(channel) if channel else None,
        )
        self._started = False
        self._actions = 0
        self._open = False

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        if self._open:
            await self.engine.stop()
            self._open = False
        self._started = False

    async def open(self, *, profile: str | None = None) -> dict[str, Any]:
        self.policy.check_action(BrowserAction.OPEN)
        if profile and profile != self.engine.profile:
            if self._open:
                await self.engine.stop()
                self._open = False
            self.engine = PlaywrightEngine(
                profile=profile,
                profiles_root=self.engine.profiles_root,
                headless=self.engine.headless,
                channel=self.engine.channel,
            )
        if not self._open:
            await self.engine.start()
            self._open = True
        await self._emit(BrowserAction.OPEN, {"profile": self.engine.profile})
        return self.engine.session.model_dump(mode="json")

    async def ensure_open(self) -> None:
        if not self._open:
            await self.open()

    async def goto(self, url: str) -> BrowserTab:
        self.policy.check_action(BrowserAction.GOTO)
        self.policy.require_url(url)
        await self.ensure_open()
        tab = await self.engine.goto(url)
        await self._emit(BrowserAction.GOTO, {"url": tab.url, "title": tab.title})
        return tab

    async def snapshot(self) -> DomGrounding:
        self.policy.check_action(BrowserAction.SNAPSHOT)
        await self.ensure_open()
        grounding = await self.engine.snapshot()
        await self._emit(BrowserAction.SNAPSHOT, {"nodes": len(grounding.nodes), "url": grounding.url})
        return grounding

    async def click(
        self,
        *,
        selector: str | None = None,
        ref: str | None = None,
        role: str | None = None,
        name: str | None = None,
    ) -> dict[str, str]:
        self.policy.check_action(BrowserAction.CLICK)
        await self.ensure_open()
        try:
            result = await self.engine.click(selector=selector, ref=ref, role=role, name=name)
        except Exception as exc:
            raise BrowserError("click failed", cause=exc) from exc
        await self._emit(BrowserAction.CLICK, dict(result))
        return result

    async def type_text(
        self,
        text: str,
        *,
        selector: str | None = None,
        ref: str | None = None,
        role: str | None = None,
        name: str | None = None,
        clear: bool = False,
    ) -> dict[str, str]:
        self.policy.check_action(BrowserAction.TYPE)
        await self.ensure_open()
        try:
            result = await self.engine.type_text(
                text,
                selector=selector,
                ref=ref,
                role=role,
                name=name,
                clear=clear,
            )
        except Exception as exc:
            raise BrowserError("type failed", cause=exc) from exc
        await self._emit(BrowserAction.TYPE, dict(result))
        return result

    async def fill(
        self,
        text: str,
        *,
        selector: str | None = None,
        ref: str | None = None,
        role: str | None = None,
        name: str | None = None,
    ) -> dict[str, str]:
        self.policy.check_action(BrowserAction.FILL)
        await self.ensure_open()
        result = await self.engine.fill(text, selector=selector, ref=ref, role=role, name=name)
        await self._emit(BrowserAction.FILL, dict(result))
        return result

    async def evaluate(self, expression: str) -> Any:
        self.policy.check_action(BrowserAction.EVAL)
        await self.ensure_open()
        result = await self.engine.evaluate(expression)
        await self._emit(BrowserAction.EVAL, {"expression_len": len(expression)})
        return result

    async def cdp(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self.policy.check_action(BrowserAction.CDP)
        await self.ensure_open()
        result = await self.engine.cdp(method, params)
        await self._emit(BrowserAction.CDP, {"method": method})
        return result

    async def tabs(self) -> list[BrowserTab]:
        self.policy.check_action(BrowserAction.TABS)
        await self.ensure_open()
        tabs = await self.engine.tabs()
        await self._emit(BrowserAction.TABS, {"count": len(tabs)})
        return tabs

    async def close(self) -> None:
        self.policy.check_action(BrowserAction.CLOSE)
        if self._open:
            await self.engine.stop()
            self._open = False
        await self._emit(BrowserAction.CLOSE, {})

    async def status(self) -> BrowserSnapshot:
        tabs: list[BrowserTab] = []
        grounding = None
        if self._open:
            tabs = await self.engine.tabs()
            try:
                grounding = await self.engine.snapshot()
            except Exception:
                grounding = None
        return BrowserSnapshot(
            profile=self.engine.profile,
            headless=self.engine.headless,
            tabs=tabs,
            grounding=grounding,
            metadata={"open": self._open, "actions": self._actions},
        )

    def stats(self) -> dict[str, Any]:
        return {
            "backend": "playwright",
            "profile": self.engine.profile,
            "headless": self.engine.headless,
            "open": self._open,
            "browser_enabled": self.policy.enabled,
            "actions": self._actions,
            "user_data_dir": str(self.engine.user_data_dir),
        }

    async def _emit(self, action: BrowserAction, payload: dict[str, Any]) -> None:
        self._actions += 1
        if self.logger is not None:
            self.logger.info("browser action", action=action.value, **payload)
        if self.event_bus is None:
            return
        await self.event_bus.publish(
            f"browser.{action.value}",
            {"action": action.value, **payload},
            source="browser",
        )
