# emily-browser

Real Playwright browser runtime for Emily OS — Chromium, persistent profiles, DOM grounding, CDP.

## Capabilities

- Persistent profiles under `data/browser/profiles/<name>`
- Navigate / tabs / evaluate JS
- Accessibility-tree DOM grounding
- Click / type by CSS selector, ARIA role/name, or grounding ref
- CDP command passthrough

## Policy

Requires `EMILY_ALLOW_BROWSER=true` or `EMILY_BROWSER_AUTOMATION=true`.

## CLI

```powershell
emily browser status
emily browser open --profile default
emily browser goto https://example.com
emily browser snapshot
emily browser click --role link --name "More information"
emily browser type "hello" --selector "input[name=q]" --clear
emily browser tabs
emily browser eval "document.title"
emily browser close
```
