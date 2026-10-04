# Voice Development

## Package

`packages/emily-voice` — develop with:

```powershell
pip install -e packages/emily-voice
pip install -e packages/emily-voice[kokoro,asr,audio]  # optional
python -m pytest packages/emily-voice/tests -q --cov=emily.voice --cov-fail-under=55
python scripts/smoke_m8_voice.py
```

## Extending TTS

1. Implement `TTSEngine` in `tts/`.
2. Register capabilities in `tts/registry.py`.
3. Construct in `VoiceRuntime.start()`.
4. Add ModelManager catalog entry.
5. Document license in `VOICE_MODELS.md`.

## Naturalness checklist (manual 1–5)

1. Roboticness
2. Prosody
3. Pausing
4. Pacing
5. Language / pronunciation
6. Code-switching preservation
7. Turn-taking / barge-in
8. Personality consistency

Do not inject random fillers (`um`/`uh`). Prefer pacing + pauses.

## Debugging

- Structured logs: `event=tts_route`, `event=speech_plan`, `event=barge_in`
- Never log raw microphone PCM
- Transcripts only when `EMILY_DEBUG=true`
