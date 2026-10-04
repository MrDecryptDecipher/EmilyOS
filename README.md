<div align="center">

# Emily OS

**An AI-native desktop operating platform for Windows 11.**
Multi-agent reasoning · durable missions · real desktop & browser automation · local multilingual voice · enterprise-grade observability.

[![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2011-0078D6?logo=windows&logoColor=white)](#requirements)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Status](https://img.shields.io/badge/milestones-0–8%20complete-success)](#roadmap)
[![Tests](https://img.shields.io/badge/tests-344%20functions-informational)](#quality-gates)
[![Packages](https://img.shields.io/badge/workspace-19%20packages-blueviolet)](#monorepo-layout)

[![Emily OS — 35-second launch film](brag-output/brag.jpg)](brag-output/brag.mp4)

▶ **Watch the 35-second launch film:** [`brag-output/brag.mp4`](brag-output/brag.mp4)

</div>

---

Emily OS is not a chatbot wrapper. It is a modular, event-driven operating
platform in which the intelligence is the operating system itself: an executive
kernel coordinates nineteen bounded-context packages that plan, execute,
verify, and remember — then act on the real machine through native Windows,
browser, vision, and voice runtimes.

## Table of contents

- [Why Emily](#why-emily)
- [What it is](#what-it-is)
- [Architecture](#architecture)
- [How a mission runs](#how-a-mission-runs)
- [Cognition: providers, agents, memory](#cognition-providers-agents-memory)
- [Runtimes: tools, desktop, browser, voice, vision](#runtimes-tools-desktop-browser-voice-vision)
- [Trust: security & observability](#trust-security--observability)
- [The Workbench](#the-workbench)
- [Monorepo layout](#monorepo-layout)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Configuration](#configuration)
- [Quality gates](#quality-gates)
- [Roadmap](#roadmap)
- [License](#license)

---

## Why Emily

Modern work is spread across dozens of apps that share nothing. Assistants can
talk, but they cannot operate the machine, and nothing about their reasoning is
inspectable. Emily closes that gap with one platform:

- **It reasons** — missions are decomposed by a provider-backed planner and run
  as durable graphs, not one-shot prompts.
- **It acts** — a permission-gated tool runtime drives real Win32 windows, a
  real Chromium browser, and on-device screenshot understanding.
- **It listens and speaks** — a local, multilingual voice loop with VAD,
  streaming ASR, barge-in, and a four-engine TTS router.
- **It remembers** — sixteen kinds of memory plus a continuously updated world
  model of entities, relations, and facts.
- **It stays observable** — every subsystem emits typed events, metrics, traces,
  and a tamper-evident, SHA-256 hash-chained audit log.

## What it is

```mermaid
mindmap
  root((Emily OS))
    Executive Kernel
      lifecycle FSM
      subsystem registry
      8-phase orchestration
      typed event bus
    Cognition
      Provider fabric
      LangGraph missions
      Multi-agent supervisor
      Memory + world model
    Runtimes
      Tools + MCP
      Desktop Win32
      Browser Playwright
      Vision OCR YOLO
      Voice 23 languages
    Trust
      Capability tokens
      Approval gates
      Hash-chained audit
      Observability
    Surface
      emily CLI
      Workbench UI
      Voice cockpit
```

## Architecture

The kernel owns lifecycle and coordination only — never reasoning. Every
capability lives in a package that implements a protocol port defined in
`emily-core`, communicates over the event bus, and registers its tools with the
unified tool runtime.

```mermaid
flowchart TB
  subgraph UX["Experience layer"]
    CLI["emily CLI<br/>72 commands"]
    WB["Workbench UI<br/>React + Vite"]
    VOICEC["Voice cockpit<br/>legacy.html"]
  end

  subgraph KERNEL["Executive kernel"]
    KER["Kernel<br/>lifecycle FSM + registry"]
    BUS["Async event bus<br/>59 typed events"]
    ORCH["Deep orchestration<br/>8-phase workflow"]
  end

  subgraph COGNITION["Cognition"]
    PROV["Providers<br/>NVIDIA NIM + RoutesMe"]
    MIS["Missions<br/>LangGraph"]
    AG["Agents<br/>14 roles"]
    MEM["Memory<br/>16 kinds + world model"]
  end

  subgraph RUNTIMES["Runtimes"]
    TOOLS["Tools + MCP<br/>30 tools"]
    DESK["Desktop<br/>Win32"]
    BROW["Browser<br/>Playwright + CDP"]
    VIS["Vision<br/>OCR + YOLOv8"]
    VOICE["Voice<br/>Kokoro/IndicF5/Chatterbox"]
  end

  subgraph TRUST["Trust"]
    SEC["Security<br/>tokens · approval · audit"]
    OBS["Observability<br/>metrics · traces · replay"]
  end

  UX --> KER
  KER --> BUS
  KER --> ORCH
  ORCH --> COGNITION
  COGNITION --> RUNTIMES
  KER --> TRUST
  COGNITION -. events .-> BUS
  RUNTIMES -. events .-> BUS
  TRUST -. events .-> BUS
```

**Kernel lifecycle** — start/stop ordering is priority-driven; a failed start
flips the kernel to `FAILED` and surfaces the error.

```mermaid
stateDiagram-v2
  [*] --> CREATED
  CREATED --> INITIALIZING
  INITIALIZING --> RUNNING
  RUNNING --> DRAINING
  DRAINING --> STOPPED
  INITIALIZING --> FAILED
  RUNNING --> FAILED
  FAILED --> [*]
  STOPPED --> [*]
```

**Event model** — one in-process async bus with prefix subscriptions,
middleware "onion" wrapping, and per-handler exception isolation so a failing
subscriber can never break delivery.

```mermaid
flowchart LR
  P["Publisher"] --> EB["AsyncEventBus"]
  EB --> MW["Middleware onion"]
  MW --> S1["Subscriber A"]
  MW --> S2["Subscriber B"]
  MW --> S3["Subscriber C"]
  S2 -. handler error isolated .-> EB
```

## How a mission runs

A mission is the unit of work: `Mission → Objective → Task`, executed on a
LangGraph backbone with checkpoints and first-class pause / resume / cancel.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant CLI as emily CLI
  participant M as MissionRuntime
  participant G as LangGraph
  participant A as AgentSupervisor
  participant P as ProviderRouter
  participant MEM as Memory + world model

  U->>CLI: emily mission run "Research. Draft. Deliver."
  CLI->>M: create + start
  M->>G: plan
  G->>P: decompose goal
  P-->>G: task graph
  loop each task
    G->>A: execute objective
    A->>P: work
    P-->>A: result
    A->>A: verify → critique → retry
    A-->>G: verified result
    G->>MEM: emit mission/agent events
  end
  G->>M: finalize + checkpoint
  M-->>CLI: durable mission archive
  CLI-->>U: summary, tokens, cost
```

Execution graph:

```mermaid
flowchart LR
  PLAN["plan"] --> EXEC["execute"]
  EXEC --> VERIFY["verify"]
  VERIFY --> REFLECT["reflect"]
  REFLECT --> FINAL["finalize"]
  VERIFY -->|retry| EXEC
  REFLECT -->|revise| EXEC
```

The planner is **provider-backed and fails closed** — it never emits a silent
fake plan; a deterministic heuristic path is used only when explicitly
requested.

## Cognition: providers, agents, memory

### Provider fabric

```mermaid
sequenceDiagram
  participant R as ProviderRouter
  participant N as NVIDIA NIM
  participant S as RoutesMe
  R->>N: complete() / stream()
  alt healthy
    N-->>R: completion + latency/token/cost analytics
  else timeout or error
    R->>S: failover complete()
    S-->>R: completion + analytics
  end
```

Two adapters over one OpenAI-compatible transport, default-on failover, transport
retries, streaming SSE parsing, and per-call cost accounting.

### Multi-agent verification loop

Ephemeral agents are spawned from a role registry, supervised with a concurrency
pool, and driven through a work → verify → critique → capped-retry loop that
returns a structured `VerificationDecision`. Teams run as sequential pipelines
with handoff, or concurrent fan-out.

```mermaid
flowchart LR
  W["work"] --> V["verify"]
  V -->|pass| DONE["accept"]
  V -->|fail| C["critique feedback"]
  C --> R["retry (capped by role)"]
  R --> W
  subgraph TEAM["Agent team"]
    direction LR
    A1["researcher"] --> A2["coder"] --> A3["verifier"]
  end
```

### Memory & world model

Sixteen `MemoryKind` tiers with a weighted lexical retriever, a consolidator
that promotes short-term into long-term, and a world model that continuously
upserts entities, relations, and facts.

```mermaid
flowchart TB
  EV["mission.* / agent.* events"] --> STORE["MemoryStore<br/>working · episodic · semantic · task · preferences …"]
  STORE --> RET["LexicalRetriever<br/>0.55 overlap + 0.25 importance + 0.20 recency"]
  STORE --> CONS["Consolidator<br/>promote + prune"]
  EV --> WM["World model"]
  WM --> ENT["Entities"]
  WM --> REL["Relations"]
  WM --> FACT["Facts (capped, snapshotted)"]
```

## Runtimes: tools, desktop, browser, voice, vision

One permission-gated tool runtime fronts every capability. Built-in, MCP, and
plugin tools share a single registry, and MCP servers are discovered and
hot-reloaded over a real stdio JSON-RPC client.

```mermaid
flowchart LR
  AG["Agent"] --> REG["Tool registry<br/>30 tools"]
  REG --> POL{"Permission policy<br/>8 levels + capability token"}
  POL -->|allowed| EX["Executor<br/>timeout + events"]
  POL -->|denied| DENY["tool.denied event"]
  EX --> B["Builtins<br/>echo · clock · math · text"]
  EX --> D["desktop.*"]
  EX --> R["browser.*"]
  EX --> V["voice.*"]
  EX --> S["vision_*"]
  EX --> M["mcp.* (hot reload)"]
```

```mermaid
flowchart TB
  AG["Agent / mission"] --> D["Desktop runtime"]
  AG --> B["Browser runtime"]
  AG --> VO["Voice runtime"]
  AG --> VI["Vision runtime"]

  D --> D1["Win32 windows · clipboard"]
  D --> D2["SendInput · PowerShell · winreg"]

  B --> B1["Chromium persistent profiles"]
  B --> B2["CDP accessibility-tree grounding"]

  VO --> VO1["VAD → streaming ASR (faster-whisper)"]
  VO --> VO2["Speech Director → TTS router"]
  VO --> VO3["barge-in · wake word"]

  VI --> VI1["Screen OCR (Tesseract / winOCR)"]
  VI --> VI2["YOLOv8 objects · DeepFace emotion"]
```

**Voice routing** picks a backend by language support, hardware, and
expressiveness, and keeps a backend pinned for a consistent turn:

```mermaid
flowchart LR
  T["Text + language"] --> SD["Speech Director<br/>emotion · pace · segments"]
  SD --> RT{"TTS router<br/>scored fallback"}
  RT --> K["Kokoro<br/>9 ISO languages"]
  RT --> I["IndicF5<br/>11 Indic languages"]
  RT --> C["Chatterbox<br/>23 languages"]
  RT --> VB["Voicebox REST<br/>23 languages"]
  K --> OUT["Audio out"]
  I --> OUT
  C --> OUT
  VB --> OUT
```

## Trust: security & observability

```mermaid
flowchart LR
  ACT["Privileged action"] --> TOK{"Capability token<br/>grants + expiry"}
  TOK -->|valid| GATE{"Approval gate<br/>human-in-the-loop"}
  TOK -->|invalid| BLOCK["Denied"]
  GATE -->|approved| RUN["Execute"]
  GATE -->|pending| WAIT["Await review"]
  RUN --> AUD["Audit log"]
```

Every operation is appended to a **SHA-256 hash chain** seeded with `GENESIS`;
`verify_integrity()` re-walks the file and detects any tampering.

```mermaid
flowchart LR
  E1["event #1"] --> H1["H1 = SHA256(GENESIS ∥ e1)"]
  H1 --> H2["H2 = SHA256(H1 ∥ e2)"]
  H2 --> H3["H3 = SHA256(H2 ∥ e3)"]
  H3 --> VER["verify_integrity() ✓"]
```

Observability is first-class: structured JSON logs, durable JSONL metrics and
spans, provider analytics, voice latency metrics, and an **execution replay**
engine that records per-step mission frames and can reload them exactly.

```mermaid
flowchart LR
  RUNTIME["Runtime"] --> LOG["JSON logs"]
  RUNTIME --> MET["Metrics (JSONL)"]
  RUNTIME --> TR["Traces / spans"]
  RUNTIME --> REP["Execution replay (per-mission frames)"]
  RUNTIME --> EV["Typed events → Workbench"]
```

## The Workbench

A React + Vite control plane (`apps/emily-ui`) reads live state from the FastAPI
server: health, telemetry over WebSocket, missions, agents, chat, a non-custodial
wallet + x402 payment-requirement inspector, and an offline Web3 security
workbench. Values are reported by the backend and never estimated.

```mermaid
flowchart LR
  subgraph UI["Workbench views"]
    OV["Overview"]; MI["Missions"]; AGv["Agents"]; CH["Chat"]; WA["Wallet + x402"]; SE["Security"]
  end
  UI --> API["FastAPI server<br/>25 endpoints"]
  API --> KER["Kernel health"]
  API --> TEL["/ws/telemetry (1 Hz)"]
  API --> M["missions / agents"]
  API --> SEC["security workbench"]
```

## Monorepo layout

19 workspace packages plus the CLI app and the UI.

| Package | Role |
|---|---|
| `emily-core` | Typed IDs, domain enums, error taxonomy, protocol ports |
| `emily-events` | Typed event envelopes + async bus |
| `emily-config` | Pydantic v2 settings |
| `emily-observability` | Logging, metrics, tracing, replay |
| `emily-kernel` | Executive kernel lifecycle + deep orchestration |
| `emily-providers` | LLM provider fabric (NVIDIA NIM, RoutesMe, router) |
| `emily-missions` | Mission runtime (LangGraph, checkpoints, control) |
| `emily-agents` | Agent runtime (spawn, supervise, verify) |
| `emily-memory` | Multi-kind memory + world model |
| `emily-tools` | Tool & MCP runtime (permissions, discovery, hot reload) |
| `emily-desktop` | Desktop runtime (Win32, clipboard, PowerShell, registry) |
| `emily-browser` | Browser runtime (Playwright, profiles, DOM grounding, CDP) |
| `emily-voice` | Local multilingual voice (ASR / TTS / VAD / Speech Director) |
| `emily-vision` | Screen capture, OCR, GUI grounding, object & emotion analysis |
| `emily-security` | Secrets vault, capability tokens, approval gates, audit chain |
| `emily-coding` | Repository AST indexing, static review, git |
| `emily-trading` | Paper-trading broker + risk enforcer |
| `emily-web3-security` | Offline, human-gated Solidity audit workbench |
| `emily-plugins` | Plugin discovery & lifecycle |
| `apps/emily-cli` | `emily` command-line interface |
| `apps/emily-ui` | React + Vite Workbench |

```mermaid
flowchart TB
  CORE["emily-core<br/>ports + types"] --> EVENTS["emily-events"]
  CORE --> CONFIG["emily-config"]
  CORE --> OBS["emily-observability"]
  EVENTS --> KERNEL["emily-kernel"]
  CONFIG --> KERNEL
  OBS --> KERNEL
  KERNEL --> PROV["emily-providers"]
  KERNEL --> MISSIONS["emily-missions"]
  KERNEL --> AGENTS["emily-agents"]
  KERNEL --> MEMORY["emily-memory"]
  KERNEL --> TOOLS["emily-tools"]
  KERNEL --> DESKTOP["emily-desktop"]
  KERNEL --> BROWSER["emily-browser"]
  KERNEL --> VOICE["emily-voice"]
  KERNEL --> VISION["emily-vision"]
  KERNEL --> SECURITY["emily-security"]
  KERNEL --> CODING["emily-coding"]
  KERNEL --> TRADING["emily-trading"]
  KERNEL --> WEB3["emily-web3-security"]
  KERNEL --> PLUGINS["emily-plugins"]
  MISSIONS --> AGENTS
  AGENTS --> TOOLS
  TOOLS --> DESKTOP
  TOOLS --> BROWSER
```

## Quick start

```powershell
git clone https://github.com/MrDecryptDecipher/EmilyOS.git
cd EmilyOS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
.\scripts\install-dev.ps1
copy .env.example .env      # then add your provider keys
emily version
emily health
emily providers
emily chat "hello"
```

### Optional voice stack

```powershell
pip install -e "packages/emily-voice[kokoro,asr,audio]"
# Optional expressive / Indic backends (large, opt-in):
# pip install chatterbox-tts
# pip install "git+https://github.com/ai4bharat/IndicF5.git"
python scripts/smoke_m8_voice.py
```

## CLI reference

72 commands across 11 groups plus the root app.

| Group | Commands |
|---|---|
| root | `version` · `health` · `config` · `boot` · `providers` · `chat` · `workbench`/`server`/`ui` · `orchestrate` · `benchmark` · `impress` |
| `mission` | `create` · `start` · `list` · `get` · `pause` · `resume` · `cancel` · `run` |
| `agent` | `roles` · `list` · `run` · `pipeline` · `stats` · `history` |
| `memory` | `kinds` · `put` · `get` · `search` · `stats` · `consolidate` |
| `world` | `show` · `observe` · `entities` |
| `tool` | `list` · `info` · `invoke` · `permissions` |
| `mcp` | `list` · `reload` · `show` |
| `desktop` | `status` · `windows` · `focus` · `clipboard` · `type` · `powershell` · `registry` |
| `browser` | `status` · `open` · `goto` · `snapshot` · `click` · `type` · `tabs` · `eval` · `close` |
| `voice` | `status` · `speak` · `listen` · `barge-in` · `models` · `converse` · `metrics` · `wake` · `serve` |
| `vision` | `screenshot` |
| `security` | `set-secret` · `get-secret` · `audit` |

## Configuration

Non-secret defaults live in [`configs/default.yaml`](configs/default.yaml);
everything else is `EMILY_`-prefixed environment variables documented in
[`.env.example`](.env.example). Secrets are never committed.

| Area | Keys (examples) |
|---|---|
| Providers | `EMILY_PRIMARY_PROVIDER`, `EMILY_NVIDIA_API_KEY`, `EMILY_ROUTESME_API_KEY` |
| Missions / agents | `EMILY_MISSION_LLM_PLANNER`, `EMILY_AGENT_MAX_CONCURRENT` |
| Voice | `EMILY_VOICE_ENABLED`, `EMILY_VOICE_WAKE_WORD`, `EMILY_TTS_DEFAULT` |
| Desktop / browser | `EMILY_DESKTOP_LIVE`, `EMILY_BROWSER_ENABLED` |
| Security | `EMILY_CONFIRM_DESTRUCTIVE_ACTIONS`, policy gates |

## Quality gates

```powershell
pytest                # test suite
ruff check packages apps tests
black --check packages apps tests
mypy                  # strict
```

344 test functions across 86 test files, branch-aware coverage with a 70%
floor, strict `mypy`, and Ruff/Black configured at line length 100.

## Roadmap

```mermaid
flowchart LR
  M0["M0 platform spine"] --> M1["M1 providers"]
  M1 --> M2["M2 missions"]
  M2 --> M3["M3 agents"]
  M3 --> M4["M4 memory"]
  M4 --> M5["M5 tools + MCP"]
  M5 --> M6["M6 desktop"]
  M6 --> M7["M7 browser"]
  M7 --> M8["M8 voice"]
  M8 --> NEXT["Vision follow-on + later milestones"]
```

Milestones 0–8 are complete. See [`docs/architecture/`](docs/architecture) for
the full design notes and per-milestone test reports.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).

---

<div align="center">

**Emily OS.** *Quietly capable. Always observable.*

</div>
