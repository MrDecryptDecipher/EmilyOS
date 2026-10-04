# Milestone 8 — Voice Engine (complete)

## Delivered

- Package `packages/emily-voice` — Speech Director, TTS router (Kokoro / IndicF5 / Chatterbox), Silero/Energy VAD, Faster-Whisper ASR, barge-in monitor, hardware profiles, ModelManager, user adaptation, spoken policy, streaming converse
- Kernel `VoiceSubsystem` + `voice.*` tools + `VoiceWorker` + CLI `emily voice …`
- Docs: `docs/VOICE_*.md`, design `25-milestone-8-voice.md`, naturalness rubric
- Live verified: **Kokoro synth PASS**; ASR + Silero VAD available after `pip install -e "packages/emily-voice[kokoro,asr,audio]"`
- Fallbacks: Chatterbox/IndicF5 unavailable → Kokoro / fail-closed without crashing

## Deferred / environment limits

- Chatterbox/IndicF5 need extra disk + (IndicF5) gated HF + reference audio
- Continuous wake-word spotting loop (flag exists)
- Tauri Listening/Thinking UI → M12

## Next

Vision follow-on (`emily-vision`) or later milestones per `02-milestones.md`.
