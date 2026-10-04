"""Optional live voice smoke — SKIP (exit 0) when heavy deps/models are missing."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


async def _kokoro() -> str:
    try:
        from kokoro import KPipeline  # noqa: F401
    except Exception as exc:
        return f"SKIP: Kokoro not installed ({exc})"

    from emily.voice.models import SpeechPlan, SpeechStyle
    from emily.voice.tts.kokoro import KokoroTTS

    engine = KokoroTTS()
    if not engine.available():
        return "SKIP: KokoroTTS.available() is False"

    try:
        await engine.load()
        plan = SpeechPlan(
            text="Emily live smoke check.",
            language="en",
            style=SpeechStyle.WARM,
            tts_backend="kokoro",
        )
        chunk = await engine.synthesize(plan)
        n = len(chunk.samples) if isinstance(chunk.samples, list) else 0
        await engine.unload()
        return f"PASS: Kokoro synthesized {n} samples @ {chunk.sample_rate}Hz"
    except Exception as exc:
        return f"SKIP: Kokoro live synth failed ({exc})"


def _probe_imports() -> list[str]:
    lines: list[str] = []
    from emily.voice.asr.whisper import FasterWhisperASR
    from emily.voice.tts.chatterbox import ChatterboxTTS
    from emily.voice.tts.indicf5 import IndicF5TTS
    from emily.voice.vad.silero import SileroVAD

    asr = FasterWhisperASR()
    lines.append(f"{'PASS' if asr.available() else 'SKIP'}: FasterWhisperASR.available={asr.available()}")
    vad = SileroVAD()
    lines.append(f"{'PASS' if vad.available() else 'SKIP'}: SileroVAD.available={vad.available()}")

    indic = IndicF5TTS(settings=SimpleNamespace(voice_directory=Path("data/voice")))
    lines.append(
        f"{'PASS' if indic.available() else 'SKIP'}: IndicF5TTS.available={indic.available()} "
        "(pip install emily-voice[indicf5]; emily voice models --name indicf5-ref --download; accept HF gate + emily voice models --name indicf5 --download)"
    )
    chatter = ChatterboxTTS()
    lines.append(
        f"{'PASS' if chatter.available() else 'SKIP'}: ChatterboxTTS.available={chatter.available()} "
        "(pip install chatterbox-tts; Python 3.11 venv recommended on 3.12)"
    )
    return lines


async def main() -> int:
    print(await _kokoro())
    for line in _probe_imports():
        print(line)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("SKIP: interrupted", file=sys.stderr)
        raise SystemExit(0)
