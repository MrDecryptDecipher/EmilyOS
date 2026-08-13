# emily-voice

Local-first conversational voice for Emily OS — ASR, VAD, Speech Director, and TTS routing (Kokoro / IndicF5 / Chatterbox).

## Principles

- **No fabricated audio** — unavailable backends raise `BackendUnavailableError` / fall back honestly
- **Lazy heavy models** — IndicF5 and Chatterbox load only when routed
- **No silent multi-GB downloads** — use `ModelManager` / `emily voice models … --allow-download`
- **Kokoro default** — lightweight path when installed (`pip install 'emily-voice[kokoro]'`)

## Optional installs

```powershell
pip install -e "packages/emily-voice[kokoro]"
pip install -e "packages/emily-voice[chatterbox]"
pip install -e "packages/emily-voice[asr]"
pip install -e "packages/emily-voice[audio]"
# IndicF5 (not on PyPI):
pip install "git+https://github.com/ai4bharat/IndicF5.git"
```

## Policy

`EMILY_VOICE_ENABLED=true` is required for speak/listen/converse tools and runtime actions.

## Tools

- `voice.speak` / `voice.listen` / `voice.status` / `voice.barge_in` / `voice.models`
