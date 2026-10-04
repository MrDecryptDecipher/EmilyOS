"""Browser policy gate."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from emily.browser.errors import BrowserPolicyError
from emily.browser.models import BrowserAction


class BrowserPolicy:
    def __init__(self, settings: Any | None = None) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        if self.settings is None:
            return False
        return bool(getattr(self.settings, "allow_browser", False)) or bool(
            getattr(self.settings, "browser_automation", False)
        )

    def require_browser(self) -> None:
        if not self.enabled:
            raise BrowserPolicyError("browser automation requires allow_browser or browser_automation")

    def check_action(self, action: BrowserAction) -> None:
        self.require_browser()
        _ = action

    def url_allowed(self, url: str) -> bool:
        prefixes = getattr(self.settings, "browser_url_allow_prefixes", None) if self.settings else None
        if not prefixes:
            return True
        parsed = urlparse(url)
        candidate = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return any(candidate.lower().startswith(str(p).lower()) for p in prefixes)

    def require_url(self, url: str) -> None:
        if not self.url_allowed(url):
            raise BrowserPolicyError(f"URL not allowlisted: {url}")
