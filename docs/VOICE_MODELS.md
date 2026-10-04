# Voice Models

Licenses and capabilities verified against upstream sources at implementation time (2026-08). Re-check before redistribution.

| Model | Repository | License | Params (approx) | Languages | Streaming | Notes |
|-------|------------|---------|-----------------|-----------|-----------|-------|
| **Kokoro-82M** | [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), pip `kokoro` | Apache-2.0 | 82M | EN (+ HI via lang `h`), ES, FR, IT, PT, JA, ZH | Yes (chunk generator) | Default lightweight path |
| **IndicF5** | [ai4bharat/IndicF5](https://huggingface.co/ai4bharat/IndicF5), git install | Upstream TOU — voice cloning requires permission; check HF card | ~0.4B | as, bn, gu, hi, kn, ml, mr, or, pa, ta, te | No | Needs reference audio + transcript; gated HF access |
| **Chatterbox Multilingual** | [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox), pip `chatterbox-tts` | MIT | ~500M | 23+ (incl. hi, en, …) | Backend-dependent | Optional expressive path; watermarked |
| **Silero VAD** | snakers4/silero-vad | MIT (upstream) | small | language-agnostic | N/A | Preferred VAD when torch available |
| **Faster-Whisper** | Systran/faster-whisper | MIT | tiny→large | multilingual | segment streaming | Default ASR adapter |

## Hardware (guidance)

| Profile | Recommendation |
|---------|----------------|
| LOW | Kokoro CPU; skip IndicF5/Chatterbox |
| MEDIUM | Kokoro + optional IndicF5 |
| HIGH | GPU; all backends eligible |

## Install status (this workstation)

Verified during M8 hardening:

| Component | Status |
|-----------|--------|
| `kokoro` + torch | Installed; **live synth PASS** (`smoke_m8_voice_live.py`) |
| `faster-whisper` | Installed; available |
| `sounddevice` | Installed |
| Silero VAD (torch.hub) | Available when torch present |
| `chatterbox-tts` | Not installed here (**Python 3.12** — upstream tested on **3.11**; use `py -3.11 -m venv .venv311` if pip fails); adapter uses `chatterbox.mtl_tts.ChatterboxMultilingualTTS` |
| IndicF5 | `pip install -e "packages/emily-voice[indicf5]"` + `pip install "git+https://github.com/ai4bharat/IndicF5.git"` + `transformers==4.49.0` + `hf auth login` + accept gate at [ai4bharat/IndicF5](https://huggingface.co/ai4bharat/IndicF5) + `emily voice models --name indicf5 --download` |

**Disk note:** Optional backends need multi-GB free space *before* `pip install`. Emily remains fully usable with Kokoro + Faster-Whisper + Silero when those are present.

Re-check licenses at upgrade time against upstream repos.

## Multilingual capability matrix (honest)

What works **out of the box** depends on which backends are installed and enabled. Emily routes per language segment when code-switching is on.

| Language | ASR (Faster-Whisper) | Kokoro TTS | IndicF5 TTS | Notes |
|----------|----------------------|------------|-------------|-------|
| English (`en`) | Yes | Yes | No (use Kokoro) | Default path |
| Hindi (`hi`) | Yes | Yes (`lang=h`) | Yes | IndicF5 preferred for native script; Kokoro works for Hinglish |
| Bengali (`bn`) | Yes | No | Yes | **IndicF5 required** for TTS |
| Telugu (`te`) | Yes | No | Yes | **IndicF5 required** for TTS |
| Tamil (`ta`) | Yes | No | Yes | **IndicF5 required** for TTS |
| Odia (`or`) | Partial (retries as `hi`) | No | Yes | Whisper has no `or`; ASR may mis-detect — set `VOICE_ASR_LANGUAGE=or` if needed |
| Kannada (`kn`) | Yes | No | Yes | IndicF5 |
| Malayalam (`ml`) | Yes | No | Yes | IndicF5 |
| Marathi (`mr`) | Yes | No | Yes | Segmentation maps `mr` → `hi` script runs |
| Gujarati (`gu`) | Yes | No | Yes | IndicF5 |
| Punjabi (`pa`) | Yes | No | Yes | IndicF5 |
| Assamese (`as`) | Yes | No | Yes | IndicF5 |

### Code-switching (Hinglish, Tenglish, etc.)

| Scenario | Behavior |
|----------|----------|
| User speaks mixed en+hi | ASR detects dominant language; LLM prompted to reply in same mix |
| Reply mixes Latin + Devanagari | Speech Director splits script runs; TTS router picks Kokoro (en) + IndicF5 (hi) per segment |
| Romanized Hindi only | May detect as `hi`; Kokoro or IndicF5 depending on script and router |
| Kokoro-only install | en + hi (Latin/Devanagari via Kokoro `h`); **no** bn/te/ta/or TTS without IndicF5 |

### Recommended `.env` for Hindi-first use

```env
VOICE_ASR_LANGUAGE=hi
VOICE_ASR_MODEL=small
TTS_ENABLE_INDICF5=true
VOICE_CODE_SWITCHING=true
```

### Still partial / not implemented

| Feature | Status |
|---------|--------|
| Streaming ASR partials during listen | Batch Whisper only |
| Barge-in during LLM "Thinking" | Barge-in during TTS playback; LLM pump cancels on interrupt |
| Chatterbox expressive path | Optional; needs Python 3.11 + `chatterbox-tts` |
| Full Tauri desktop voice UI | Status HTTP + React scaffold only |
