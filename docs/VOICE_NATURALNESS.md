# Voice Naturalness Evaluation Checklist

Use this template after listening to Emily on real hardware with a live TTS backend
(Kokoro / IndicF5 / Chatterbox). Score each row **1–5** (1 = poor, 5 = excellent).

| Criterion | Score (1–5) | Notes |
|-----------|-------------|-------|
| Natural pacing / pauses | | |
| Emotion / warmth match | | |
| Code-switching preservation | | |
| Technical accuracy of spoken answer | | |
| Barge-in responsiveness | | |
| End-to-end latency feel | | |
| No filler / theatrical speech | | |
| Language stickiness across turns | | |

**Session metadata**

- Date:
- Backend:
- Device (`cpu` / `cuda` / `mps`):
- Hardware profile:
- Languages tested:

**Overall (avg):** ______

## How to run supporting smokes

```bash
python scripts/smoke_m8_voice.py
python scripts/smoke_m8_voice_live.py   # SKIP if Kokoro missing — never fails CI
```
