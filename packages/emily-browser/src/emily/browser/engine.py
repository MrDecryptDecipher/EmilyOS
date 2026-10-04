"""Playwright browser engine with persistent profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from emily.browser.errors import BrowserError, BrowserNotFoundError
from emily.browser.grounding import capture_grounding, resolve_selector
from emily.browser.models import BrowserSessionInfo, BrowserTab, DomGrounding


class PlaywrightEngine:
    """Owns Playwright browser lifecycle for a single profile."""

    def __init__(
        self,
        *,
        profile: str = "default",
        profiles_root: Path | str = Path("data/browser/profiles"),
        headless: bool = True,
        channel: str | None = None,
    ) -> None:
        self.profile = profile
        self.profiles_root = Path(profiles_root)
        self.headless = headless
        self.channel = channel
        self.user_data_dir = self.profiles_root / profile
        self.session = BrowserSessionInfo(
            profile=profile,
            user_data_dir=str(self.user_data_dir),
        )
        self._playwright: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._last_grounding: DomGrounding | None = None
        self._tab_ids: dict[int, str] = {}
        self._id_seq = 0

    @property
    def page(self) -> Any:
        if self._page is None:
            raise BrowserError("browser is not open")
        return self._page

    @property
    def context(self) -> Any:
        if self._context is None:
            raise BrowserError("browser is not open")
        return self._context

    async def start(self) -> BrowserSessionInfo:
        if self._context is not None:
            return self.session
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise BrowserError("playwright package is required", cause=exc) from exc

        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": str(self.user_data_dir),
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 800},
        }
        if self.channel:
            launch_kwargs["channel"] = self.channel
        try:
            self._context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as exc:
            await self.stop()
            raise BrowserError("failed to launch Chromium", cause=exc) from exc
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()
        self._remember_page(self._page)
        return self.session

    async def stop(self) -> None:
        context = self._context
        playwright = self._playwright
        self._page = None
        self._context = None
        self._playwright = None
        self._tab_ids.clear()
        if context is not None:
            await context.close()
        if playwright is not None:
            await playwright.stop()

    def _remember_page(self, page: Any) -> str:
        key = id(page)
        if key not in self._tab_ids:
            self._id_seq += 1
            self._tab_ids[key] = f"tab_{self._id_seq}"
        return self._tab_ids[key]

    async def tabs(self) -> list[BrowserTab]:
        context = self.context
        active = self._page
        rows: list[BrowserTab] = []
        for page in context.pages:
            tab_id = self._remember_page(page)
            rows.append(
                BrowserTab(
                    tab_id=tab_id,
                    url=page.url,
                    title=await page.title(),
                    active=page is active,
                )
            )
        return rows

    async def goto(self, url: str, *, wait_until: str = "domcontentloaded") -> BrowserTab:
        page = self.page
        await page.goto(url, wait_until=wait_until)
        return BrowserTab(
            tab_id=self._remember_page(page),
            url=page.url,
            title=await page.title(),
            active=True,
        )

    async def snapshot(self) -> DomGrounding:
        grounding = await capture_grounding(self.page)
        self._last_grounding = grounding
        return grounding

    async def click(
        self,
        *,
        selector: str | None = None,
        ref: str | None = None,
        role: str | None = None,
        name: str | None = None,
    ) -> dict[str, str]:
        mode, payload = resolve_selector(
            selector=selector,
            ref=ref,
            grounding=self._last_grounding,
            role=role,
            name=name,
        )
        page = self.page
        if mode == "css":
            await page.click(payload["selector"])
        else:
            locator = page.get_by_role(payload["role"], name=payload["name"] or None)
            await locator.first.click()
        return {"mode": mode, **payload}

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
        mode, payload = resolve_selector(
            selector=selector,
            ref=ref,
            grounding=self._last_grounding,
            role=role,
            name=name,
        )
        page = self.page
        if mode == "css":
            target = page.locator(payload["selector"]).first
        else:
            target = page.get_by_role(payload["role"], name=payload["name"] or None).first
        if clear:
            await target.fill(text)
        else:
            await target.click()
            await target.type(text)
        return {"mode": mode, "text_len": str(len(text)), **payload}

    async def fill(
        self,
        text: str,
        *,
        selector: str | None = None,
        ref: str | None = None,
        role: str | None = None,
        name: str | None = None,
    ) -> dict[str, str]:
        return await self.type_text(
            text,
            selector=selector,
            ref=ref,
            role=role,
            name=name,
            clear=True,
        )

    async def evaluate(self, expression: str) -> Any:
        return await self.page.evaluate(expression)

    async def cdp(self, method: str, params: dict[str, Any] | None = None) -> Any:
        session = await self.page.context.new_cdp_session(self.page)
        try:
            return await session.send(method, params or {})
        finally:
            await session.detach()

    async def select_tab(self, tab_id: str) -> BrowserTab:
        for page in self.context.pages:
            if self._remember_page(page) == tab_id:
                self._page = page
                await page.bring_to_front()
                return BrowserTab(
                    tab_id=tab_id,
                    url=page.url,
                    title=await page.title(),
                    active=True,
                )
        raise BrowserNotFoundError(f"tab not found: {tab_id}")
