# Voice gaps — solutions (research-backed)

This doc records how the three former “honest limits” are addressed.

## 1. IndicF5

**Upstream:** [ai4bharat/IndicF5](https://huggingface.co/ai4bharat/IndicF5) (gated HF model).

**Requirements (from AI4Bharat README):**

1. `transformers` + `AutoModel.from_pretrained(..., trust_remote_code=True)`
2. Reference WAV + matching transcript (`ref_audio_path`, `ref_text`)
3. HuggingFace login after accepting the model license

**Emily integration:**

```powershell
pip install -e "packages/emily-voice[indicf5]"
pip install "git+https://github.com/ai4bharat/IndicF5.git"   # provides f5_tts
pip install "transformers==4.49.0"                            # avoids meta-tensor CPU bug
hf auth login
# Accept gate at https://huggingface.co/ai4bharat/IndicF5
emily voice models --name indicf5-ref --download   # ~760KB default ref WAV
emily voice models --name indicf5 --download
emily voice models --name indicf5 --verify
```

**Windows notes (verified Aug 2026):**

- Weights download to `models/voice/indicf5`, but **runtime loads via hub id** `ai4bharat/IndicF5` (HF cache). Passing a Windows path to `from_pretrained` fails transformers validation.
- `torchaudio` 2.9+ defaults to **torchcodec** (needs FFmpeg). Emily patches `torchaudio.load` to use **soundfile** inside the IndicF5 adapter — no FFmpeg required.
- First CPU synthesis is slow (~2–4 min); GPU is much faster.

Adapter: `packages/emily-voice/src/emily/voice/tts/indicf5.py`  
Bundled ref: `data/voice/indicf5_ref/PAN_F_HAPPY_00001.wav` (from [IndicF5 prompts](https://github.com/AI4Bharat/IndicF5/tree/main/prompts)).

## 2. Chatterbox

**Upstream:** [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) — `pip install chatterbox-tts`.

**API:** `from chatterbox.mtl_tts import ChatterboxMultilingualTTS`  
`model.generate(text, language_id="hi")` ([HF card](https://huggingface.co/ResembleAI/chatterbox)).

**Python version:** Upstream tested on **3.11** ([issue #427](https://github.com/resemble-ai/chatterbox/issues/427)). On 3.12, use a 3.11 venv if pip fails:

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\Activate.ps1
pip install -U pip setuptools wheel
pip install numpy
pip install chatterbox-tts
pip install -e packages/emily-voice
```

Adapter fixed in `chatterbox.py` to use `ChatterboxMultilingualTTS` + `language_id` mapping.

## 3. Wake-word loop

**Options researched:**

| Library | License | Notes |
|---------|---------|-------|
| [openWakeWord](https://github.com/dscripka/openWakeWord) | Apache-2.0 | Pre-trained ONNX models; custom models via training |
| [ViolaWake](https://github.com/GeeIHadAGoodTime/ViolaWake) | Apache-2.0 | Full pipeline (wake + STT + Kokoro) |
| [wakewordlab](https://github.com/ubermorgenland/wakewordlab) | — | Very low CPU vs openWakeWord |

**Emily approach (no fake KWS):**

- **ASR phrase mode (default):** VAD + faster-whisper; match `EMILY_WAKE_WORD` (default `Hey Emily`, incl. ASR variants like `Hry Emily`) — works without training a KWS model.
- **openWakeWord mode:** set `EMILY_VOICE_WAKE_WORD_MODEL` to an ONNX model path.

```powershell
pip install -e "packages/emily-voice[wakeword,asr,audio]"
emily voice wake
```

Implementation: `packages/emily-voice/src/emily/voice/session/wake_word.py`

## 4. Tauri / voice UI

No full M12 shell yet; **foundation added:**

- `emily voice serve` → `GET http://127.0.0.1:8765/voice/status` (stdlib HTTP, no mock state)
- `apps/emily-ui` — React panel (Listening / Thinking / Speaking / backends)
- Tauri: `npm run tauri dev` after Rust + `tauri init` (see `apps/emily-ui/README.md`)

```powershell
# terminal 1
emily voice serve

# terminal 2
cd apps/emily-ui && npm install && npm run dev
```
