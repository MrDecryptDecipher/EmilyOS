"""Voicebox TTS adapter — local jamiepine/voicebox REST API (port 17493)."""



from __future__ import annotations



import asyncio

import io

import time

from collections.abc import AsyncIterator

from typing import Any



import numpy as np



from emily.voice.errors import BackendUnavailableError, TTSError

from emily.voice.models import AudioChunk, SpeechPlan, TTSCapability

from emily.voice.settings_bridge import voice_flag

from emily.voice.tts.registry import TTS_CAPABILITIES



_DEFAULT_BASE = "http://127.0.0.1:17493"

_CLIENT_ID = "emily"

# Warm young female presets — avoid cloned refs that sound panicky/aggressive.

_PRESET_KOKORO_EN = "af_bella"

_PRESET_KOKORO_HI = "hf_beta"

_PRESET_QWEN_EN = "Serena"





class VoiceboxTTS:

    """

    Talk to a running Voicebox desktop/backend instance.



    Uses ``POST /generate`` (never ``/speak``) so ``instruct`` and

    ``personality=false`` are always honored — ``/speak`` can rewrite text

    in-character and ignore style instructions.

    """



    name = "voicebox"



    def __init__(self, *, settings: Any | None = None) -> None:

        self.settings = settings

        self.sample_rate = 24000

        self._healthy: bool | None = None

        self._profile_ids: dict[str, str] = {}



    @property

    def capabilities(self) -> TTSCapability:

        return TTS_CAPABILITIES["voicebox"]



    def _base_url(self) -> str:

        raw = voice_flag(self.settings, "voice_voicebox_url", _DEFAULT_BASE) or _DEFAULT_BASE

        return str(raw).rstrip("/")



    def _profile_name(self) -> str | None:

        raw = voice_flag(self.settings, "voice_voicebox_profile", None)

        if raw is None:

            return None

        text = str(raw).strip()

        return text or None



    def _client_id(self) -> str:

        raw = voice_flag(self.settings, "voice_voicebox_client_id", _CLIENT_ID) or _CLIENT_ID

        return str(raw).strip() or _CLIENT_ID



    def _timeout_s(self) -> float:

        raw = float(voice_flag(self.settings, "voice_voicebox_timeout_seconds", 90) or 90)

        return max(15.0, min(raw, 300.0))



    def _use_presets(self) -> bool:

        return bool(voice_flag(self.settings, "voice_voicebox_use_presets", True))



    def _personality_enabled(self) -> bool:

        return bool(voice_flag(self.settings, "voice_voicebox_personality", False))



    def _instruct(self) -> str | None:

        raw = voice_flag(self.settings, "voice_voicebox_instruct", None)

        if raw is None:

            return (

                "Speak like a sweet young girl around eighteen — soft, warm, gentle, and slightly playful. "

                "Light bright tone, relaxed pace, never loud, mature, rushed, or panicky."

            )

        text = str(raw).strip()

        return text or None



    def _engine_setting(self) -> str:

        raw = str(voice_flag(self.settings, "voice_voicebox_engine", "auto") or "auto").strip().lower()

        return raw or "auto"



    def _preset_en(self) -> str:

        engine = self._engine_setting()

        if engine == "qwen_custom_voice":

            return str(voice_flag(self.settings, "voice_voicebox_preset_en", _PRESET_QWEN_EN) or _PRESET_QWEN_EN)

        return str(

            voice_flag(self.settings, "voice_voicebox_preset_kokoro_en", _PRESET_KOKORO_EN) or _PRESET_KOKORO_EN

        )



    def _preset_hi(self) -> str:

        return str(voice_flag(self.settings, "voice_voicebox_preset_kokoro_hi", _PRESET_KOKORO_HI) or _PRESET_KOKORO_HI)



    def _headers(self) -> dict[str, str]:

        return {

            "Content-Type": "application/json",

            "X-Voicebox-Client-Id": self._client_id(),

        }



    def available(self) -> bool:

        try:

            import httpx  # noqa: F401

        except Exception:

            return False

        try:

            import httpx



            with httpx.Client(timeout=1.5) as client:

                resp = client.get(f"{self._base_url()}/health")

                if resp.status_code == 200:

                    self._healthy = True

                    return True

                resp = client.get(f"{self._base_url()}/")

                self._healthy = resp.status_code < 500

                return self._healthy

        except Exception:

            self._healthy = False

            return False



    async def load(self, *, language: str = "en") -> None:

        if not self.available():

            raise BackendUnavailableError(

                "Voicebox is not running. Install from https://voicebox.sh or "

                "https://github.com/jamiepine/voicebox and start the app "

                f"(API expected at {self._base_url()}).",

                backend=self.name,

            )

        await self._resolve_profile_id(language=language)



    async def unload(self) -> None:

        self._healthy = None

        self._profile_ids.clear()



    def _engine_and_preset(self, language: str) -> tuple[str, str]:

        base = (language or "en").split("-")[0].lower()

        engine_cfg = self._engine_setting()

        if engine_cfg in {"kokoro", "qwen_custom_voice"}:

            engine = engine_cfg

        elif base == "hi":

            engine = "kokoro"

        else:

            # Kokoro is fast and stable on 4 GB GPUs; qwen_custom_voice needs more VRAM.

            engine = "kokoro"

        preset = self._preset_hi() if base == "hi" else self._preset_en()

        if engine == "qwen_custom_voice" and base == "hi":

            # Qwen CustomVoice has no Hindi preset — fall back to Kokoro.

            engine = "kokoro"

            preset = self._preset_hi()

        return engine, preset



    def _preset_profile_name(self, *, engine: str, preset: str, language: str) -> str:

        base_name = self._profile_name() or "Emily"

        if not self._use_presets():

            return base_name

        lang = (language or "en").split("-")[0].lower()

        return f"{base_name}-{engine}-{preset}-{lang}"



    async def _list_profiles(self, client: Any) -> list[dict[str, Any]]:

        resp = await client.get(f"{self._base_url()}/profiles", headers=self._headers())

        if resp.status_code != 200:

            return []

        payload = resp.json()

        items = payload if isinstance(payload, list) else payload.get("items") or payload.get("profiles") or []

        return [item for item in items if isinstance(item, dict)]



    async def _create_preset_profile(

        self,

        client: Any,

        *,

        name: str,

        engine: str,

        preset: str,

        language: str,

    ) -> str | None:

        body = {

            "name": name,

            "description": "Emily auto preset — soft young female voice",

            "language": (language or "en").split("-")[0].lower()[:2] or "en",

            "voice_type": "preset",

            "preset_engine": engine,

            "preset_voice_id": preset,

            "default_engine": engine,

        }

        resp = await client.post(f"{self._base_url()}/profiles", headers=self._headers(), json=body)

        if resp.status_code >= 400:

            return None

        payload = resp.json()

        pid = payload.get("id") if isinstance(payload, dict) else None

        return str(pid) if pid else None



    async def _resolve_profile_id(self, *, language: str = "en") -> str | None:

        cache_key = language.split("-")[0].lower()

        if cache_key in self._profile_ids:

            return self._profile_ids[cache_key]



        import httpx



        engine, preset = self._engine_and_preset(language)

        use_presets = self._use_presets()

        target_name = self._preset_profile_name(engine=engine, preset=preset, language=language)



        async with httpx.AsyncClient(timeout=8.0) as client:

            items = await self._list_profiles(client)

            if use_presets:

                needle = target_name.lower()

                for item in items:

                    if str(item.get("name") or "").strip().lower() == needle:

                        pid = str(item.get("id") or "")

                        if pid:

                            self._profile_ids[cache_key] = pid

                            return pid

                created = await self._create_preset_profile(

                    client,

                    name=target_name,

                    engine=engine,

                    preset=preset,

                    language=language,

                )

                if created:

                    self._profile_ids[cache_key] = created

                    return created



            # Legacy: resolve user-named cloned profile (only when presets disabled).

            name = self._profile_name()

            if name:

                needle = name.lower()

                for item in items:

                    if str(item.get("id") or "") == name:

                        pid = str(item["id"])

                        self._profile_ids[cache_key] = pid

                        return pid

                    if str(item.get("name") or "").strip().lower() == needle:

                        pid = str(item.get("id") or "")

                        if pid:

                            self._profile_ids[cache_key] = pid

                            return pid



            for item in items:

                if str(item.get("name") or "").lower() == "imported audio":

                    continue

                voice_type = str(item.get("voice_type") or "cloned").lower()

                if use_presets and voice_type != "preset":

                    continue

                pid = item.get("id")

                if pid:

                    pid_s = str(pid)

                    self._profile_ids[cache_key] = pid_s

                    return pid_s

        return None



    def _map_language(self, language: str | None) -> str:

        base = (language or "en").split("-")[0].lower()

        supported = {

            "zh",

            "en",

            "ja",

            "ko",

            "de",

            "fr",

            "ru",

            "pt",

            "es",

            "it",

            "he",

            "ar",

            "da",

            "el",

            "fi",

            "hi",

            "ms",

            "nl",

            "no",

            "pl",

            "sv",

            "sw",

            "tr",

        }

        return base if base in supported else "en"



    async def _poll_until_ready(self, client: Any, generation_id: str) -> None:

        deadline = time.monotonic() + self._timeout_s()

        while time.monotonic() < deadline:

            audio_probe = await client.get(f"{self._base_url()}/audio/{generation_id}")

            if audio_probe.status_code == 200 and audio_probe.content:

                return

            if audio_probe.status_code == 404:

                detail = ""

                try:

                    detail = str(audio_probe.json().get("detail") or "")

                except Exception:

                    detail = (audio_probe.text or "")[:200]

                if "failed" in detail.lower():

                    raise TTSError(

                        f"Voicebox generation failed: {detail}",

                        details={"generation_id": generation_id},

                    )

            await asyncio.sleep(0.45)

        raise TTSError(

            f"Voicebox timed out after {self._timeout_s():.0f}s waiting for audio",

            details={"generation_id": generation_id},

        )



    async def _decode_wav(self, data: bytes) -> AudioChunk:

        try:

            import soundfile as sf

        except Exception as exc:

            raise TTSError("soundfile required to decode Voicebox audio", cause=exc) from exc

        arr, sr = sf.read(io.BytesIO(data), dtype="float32")

        pcm = np.asarray(arr, dtype=np.float32)

        if pcm.ndim > 1:

            pcm = pcm.mean(axis=1)

        if pcm.size == 0:

            raise TTSError("Voicebox returned empty audio", details={"backend": self.name})

        self.sample_rate = int(sr) or self.sample_rate

        return AudioChunk(

            samples=pcm.astype(np.float32).tolist(),

            sample_rate=self.sample_rate,

            channels=1,

            backend=self.name,

        )



    async def synthesize(self, plan: SpeechPlan) -> AudioChunk:

        await self.load(language=plan.language)

        import httpx



        text = plan.text if not plan.segments else " ".join(s.text for s in plan.segments)

        text = text.replace("!", ".").replace("?", ".").strip()

        if not text:

            raise TTSError("empty text for Voicebox", details={"backend": self.name})



        language = self._map_language(plan.language)

        profile_id = await self._resolve_profile_id(language=language)

        if not profile_id:

            raise TTSError(

                "No Voicebox profile found. Start Voicebox or set VOICE_VOICEBOX_USE_PRESETS=true.",

                details={"backend": self.name},

            )



        engine, _preset = self._engine_and_preset(language)

        instruct = self._instruct()

        gen_body: dict[str, Any] = {

            "profile_id": profile_id,

            "text": text,

            "language": language,

            "engine": engine,

            "personality": self._personality_enabled(),

            "normalize": True,

        }

        if instruct and engine == "qwen_custom_voice":

            gen_body["instruct"] = instruct



        async with httpx.AsyncClient(timeout=self._timeout_s()) as client:

            try:

                resp = await client.post(

                    f"{self._base_url()}/generate",

                    headers=self._headers(),

                    json=gen_body,

                )

                if resp.status_code >= 400:

                    raise TTSError(

                        f"Voicebox HTTP {resp.status_code}: {resp.text[:300]}",

                        details={"backend": self.name, "engine": engine},

                    )

                payload = resp.json()

                generation_id = str(payload.get("id") or "")

                if not generation_id:

                    raise TTSError("Voicebox response missing generation id", details={"payload": payload})

                if str(payload.get("status") or "") == "failed":

                    raise TTSError(

                        f"Voicebox generation failed: {payload.get('error')}",

                        details={"generation_id": generation_id},

                    )

                if str(payload.get("status") or "") != "completed":

                    await self._poll_until_ready(client, generation_id)

                audio_resp = await client.get(f"{self._base_url()}/audio/{generation_id}")

                if audio_resp.status_code != 200 or not audio_resp.content:

                    raise TTSError(

                        f"Voicebox audio fetch failed ({audio_resp.status_code})",

                        details={"generation_id": generation_id},

                    )

                return await self._decode_wav(audio_resp.content)

            except (BackendUnavailableError, TTSError):

                raise

            except Exception as exc:

                raise TTSError(f"Voicebox synthesis failed: {exc}", cause=exc) from exc



    async def synthesize_stream(self, plan: SpeechPlan) -> AsyncIterator[AudioChunk]:

        yield await self.synthesize(plan)

