# Milestone 7 — Browser Runtime

## Design decisions

1. **Real Playwright only** — Chromium via Playwright async API; no simulated browser.
2. **Policy-first** — `allow_browser` or `browser_automation` required for all actions.
3. **Persistent profiles** — Playwright persistent context under `data/browser/profiles/<name>`.
4. **DOM grounding** — CDP `Accessibility.getFullAXTree` + selector/ref targeting for reliable actions.
5. **CDP available** — `new_cdp_session` for advanced Chrome DevTools Protocol calls.
6. **Tool + agent wiring** — `browser.*` tools and `BrowserWorker` drive the live runtime.

## Package

`packages/emily-browser` → `emily.browser`

## CLI

- `emily browser status|open|goto|snapshot|click|type|tabs|eval|close`

## Status

**Complete** — see [24-milestone-7-complete.md](24-milestone-7-complete.md).
