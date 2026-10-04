# Voice Configuration

All settings use `EmilySettings` / `EMILY_*` env vars (see `.env.example`).

| Variable | Default | Meaning |
|----------|---------|---------|
| `EMILY_VOICE_ENABLED` | `false` | Start `VoiceSubsystem` |
| `EMILY_WAKE_WORD` | `Hey Emily` | Phrase to detect (ASR mode). Also matches ASR variants like `Hry Emily`, `Hi Emily`. |
| `EMILY_VOICE_WAKE_WORD_ENABLED` | `false` | Enable continuous wake-word loop |
| `EMILY_VOICE_WAKE_WORD_THRESHOLD` | `0.5` | openWakeWord detection threshold |
| `EMILY_VOICE_WAKE_WORD_MODEL` | — | Optional path to openWakeWord ONNX model |
| `EMILY_VOICE_WAKE_WORD_MAX_LISTEN_S` | `8.0` | Max utterance length in ASR phrase mode |
| `EMILY_VOICE_UI_PORT` | `8765` | HTTP port for `emily voice serve` / Tauri UI |
| `EMILY_VOICE_DIRECTORY` | `data/voice` | Personality + runtime data |
| `EMILY_VOICE_MODELS_DIRECTORY` | `models/voice` | Local model cache root |
| `EMILY_VOICE_REGISTER_TOOLS` | `true` | Register `voice.*` tools |
| `EMILY_VOICE_STREAMING` | `true` | Sentence-pipelined LLM→TTS |
| `EMILY_VOICE_BARGE_IN` | `true` | Auto VAD barge-in while speaking |
| `EMILY_VOICE_LANGUAGE_AUTO_DETECT` | `true` | Sticky language detection |
| `EMILY_VOICE_CODE_SWITCHING` | `true` | Preserve mixed-language text |
| `EMILY_VOICE_EMOTION` | `true` | Mild style/emotion adaptation |
| `EMILY_VOICE_ADAPTIVE_PACING` | `true` | Pace from personality + user adaptation |
| `EMILY_VOICE_ADAPTIVE_PAUSES` | `true` | Punctuation-based pauses |
| `EMILY_VOICE_PREFER_ENERGY_VAD` | `false` | Skip Silero torch.hub; use energy VAD |
| `EMILY_TTS_DEFAULT` | `kokoro` | Preferred backend name |
| `EMILY_TTS_ENABLE_KOKORO` | `true` | Allow Kokoro in router |
| `EMILY_TTS_ENABLE_INDICF5` | `true` | Allow IndicF5 |
| `EMILY_TTS_ENABLE_CHATTERBOX` | `true` | Allow Chatterbox |
| `EMILY_TTS_DEVICE` | `auto` | `auto` / `cpu` / `cuda` / `mps` |
| `EMILY_VOICE_ASR_MODEL` | `base` | faster-whisper size |
| `EMILY_VOICE_INDICF5_REF_AUDIO` | — | Required for IndicF5 |
| `EMILY_VOICE_INDICF5_REF_TEXT` | `""` | Transcript of ref audio |

## Optional installs

```powershell
pip install -e "packages/emily-voice[kokoro]"
pip install -e "packages/emily-voice[asr,audio]"
pip install -e "packages/emily-voice[indicf5]"
pip install -e "packages/emily-voice[chatterbox]"   # Python 3.11 venv if 3.12 pip fails
pip install -e "packages/emily-voice[wakeword]"
```

## CLI

```powershell
emily voice status
emily voice speak "Haan, ek second... check karta hoon."
emily voice wake          # needs EMILY_VOICE_WAKE_WORD_ENABLED=true
emily voice serve         # UI status API for apps/emily-ui
emily voice models --name indicf5-ref --download
emily voice models
emily voice metrics
```
