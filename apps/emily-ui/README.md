# Emily Workbench

Accessible React + Vite control plane for Emily’s local runtime. The UI only displays values reported by the backend; unavailable values are shown as **Unavailable**.

## Run locally

```powershell
cd apps/emily-ui
npm install
npm run dev
```

Vite proxies `/api` and `/ws` to the workbench server at `127.0.0.1:8000` (the default `emily workbench` port). Build output uses `/ui/` as its base for FastAPI static mounting:

```powershell
npm run build
```

## Runtime views

- **Overview** reads `/api/health` and `/ws/telemetry`, with explicit connecting, stale, disconnected, and unavailable states.
- **Missions** and **Agents** read `/api/missions` and `/api/agents`; empty responses are presented as empty states.
- **Chat** sends `POST /api/chat` and handles timeouts, cancellation, errors, and duplicate-send prevention.
- Portfolio telemetry is labelled paper-only and is never presented as real trading.

The original vanilla voice interface is preserved at [`/ui/legacy.html`](./legacy.html). Voice source files remain untouched.

## Wallet and x402

The Wallet view is non-custodial. It discovers injected EVM wallets through
EIP-6963 and requests accounts only after the user selects **Connect**. Emily
does not create, store, or expose private keys. Signing and chain changes always
remain explicit wallet-confirmed actions.

The x402 panel performs HTTP 402 payment-requirement discovery using CAIP-2
network identifiers and displays the advertised scheme, asset, amount,
recipient, and timeout. It never silently signs or settles a payment. A
payment scheme adapter and explicit confirmation are required before settlement;
unsupported networks are shown as unsupported rather than treated as EVM.
