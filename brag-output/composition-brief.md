# Hyperframes Composition Brief: Emily OS

## Objective
Create a 35-second WHAT / WHY / HOW / SO-WHAT product film for Emily OS — an AI-native desktop operating platform for Windows 11 — for a LinkedIn audience. Show the actual product: presence form, mission pipeline, real runtimes, voice loop, world model, and real Emily UI, over a music bed that builds and drops.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 35.0 seconds

## Source Material
- Project root: `C:\Users\FCI\Desktop\EMILY`
- Primary files read: `README.md`, `docs/architecture/*`, all `packages/*/README.md` + source, `apps/emily-cli/src/emily_cli/main.py` + `server.py`, `apps/emily-ui/src/App.tsx` + `styles.css` + `three/EmilyPresence.js`, root `ui_screenshot.png` (real UI capture)
- Product name: Emily OS
- Tagline: "Quietly capable. Always observable."
- Key UI/visual moment: an animated, immersive Workbench "control room" in the Cockpit chapter — live telemetry sparkline drawing, subsystem load bars, counting metrics, a scrolling activity feed, floating runtime/capture HUD panels, and a slow camera push-in — plus the real capture (`assets/images/ui_screenshot.png`) as a live inset
- Copy that must appear (all grounded in source):
  - "Your work lives in fifty tabs." / "Fifty apps. Zero memory." / "And the AI can only talk."
  - "So we built Emily OS." / "An AI-native desktop operating platform." / "It reasons. It acts. It stays observable."
  - "Missions, not prompts." · PLAN → EXECUTE → VERIFY → REFLECT → FINALIZE
  - "A supervised team of agents plans, executes, verifies, and retries."
  - "It uses your computer." · DESKTOP · BROWSER · VISION
  - "Native Windows control. A real browser. On-device sight."
  - "It hears you — in 23 languages." / "And it remembers." / "16 kinds of memory. One continuous world model."
  - "The Cockpit" · dock: Screen Vision, Code Review, AST Index, Look Around, Portfolio, Identify Song
  - "One control plane over every subsystem."
  - "Local-first. Hash-chained. Human-approved." / "Every action lands on a tamper-evident audit chain."
  - "Quietly capable. Always observable."
- Accuracy: no comparative or competitor claims. Counts verified from source (23 TTS languages; 16 MemoryKind; 5-stage LangGraph mission graph; desktop/browser/vision runtimes). Music swapped to vol-1.

## Creative Direction
- Tone preset: `cinematic`
- Creative direction: a human product story — problem → product → how it works → why it holds up
- Interpretation: large type, slower reveals than a spec reel; the music builds under WHY/WHAT and drops at the moment the product acts.
- Hook: "Your work lives in fifty tabs." → "So we built Emily OS."
- Outro / punchline: "Quietly capable. Always observable."
- Avoid: package-name listicle feel; competitor comparisons; generic SaaS language; abstract filler.

## Visual Identity
- Background `#0b0d10`; surfaces `#171b1e`/`#14181b`; borders `rgba(255,255,255,.12)`
- Text `#e8edf2`; muted `#9aa3a9`; accent `#9fe5b8`; glow `#06b6d4` → `#10b981`
- Fonts: DM Sans + DM Mono (`assets/fonts/`)
- Visual references: presence form, browser-tab strip, mission pipeline, action cards, voice waveform + language chips, world-model graph, real Workbench UI frame, hash chain

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Why — the problem — 4.53s — fifty tabs / fifty apps / AI can only talk
2. What — Emily OS — 3.99s — presence form + product statement
3. How 01 — Missions, not prompts — 4.99s — 5-stage pipeline + agent team
4. How 02 — It uses your computer — 5.01s — DESKTOP / BROWSER / VISION (music drop 16.02)
5. How 03 — It hears and remembers — 4.5s — waveform + language chips + world model
6. The Cockpit — 4.99s — real Emily UI + command dock
7. Why it holds up — 4.01s — hash chain
8. Emily OS — 2.98s — wordmark + tagline

## Audio
- Role: scored cinematic support with build-and-drop arc
- Music: `happy-beats-business-moves-vol-1-by-ende-dot-app.mp3` (~120 BPM), swapped in for a livelier bed
- Music treatment: fade in to 0.30 by 2.4s; build; drop to 0.48 at 16.02s; settle 0.42; outro swell 0.50 at 32.5s; fade to 0 by 35.0s
- Music cue guidance: bundled preset `assets/music/cues/happy-beats-business-moves-vol-1-by-ende-dot-app.music-cues.json`. Strong-cue locks: 16.02, 21.01, 23.52, 32.52.
- Audio-reactive: presence glow + voice waveform driven by pre-extracted bands (`assets/music/audio-data.js`).
- SFX: soft drops per line, pipeline node clicks, bell on the action drop, soft impact on the memory reveal, card-slide for the dock, bell on the wordmark.

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills. /brag is its own workflow: do not enter the `/hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions.

Requirements:
- Show the actual product (real UI capture + recreated product visuals).
- Keep all text readable; reveals hold before scene cuts.
- Include the music/SFX layer.
- Run `hyperframes check` before render — brag's single gate.
- Keep creation and rendering local.
