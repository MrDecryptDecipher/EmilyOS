"""Voicebox TTS adapter unit tests (mocked HTTP)."""



from __future__ import annotations



from types import SimpleNamespace



import numpy as np

import pytest



from emily.voice.models import SpeechPlan

from emily.voice.tts.voicebox import VoiceboxTTS





class _FakeResp:

    def __init__(self, *, status_code: int = 200, json_data=None, content: bytes = b"", text: str = ""):

        self.status_code = status_code

        self._json = json_data

        self.content = content

        self.text = text

        self.headers = {}



    def json(self):

        return self._json





@pytest.mark.asyncio

async def test_voicebox_synthesize_uses_generate_with_personality_off(monkeypatch: pytest.MonkeyPatch) -> None:

    import io



    import soundfile as sf



    buf = io.BytesIO()

    sf.write(buf, np.zeros(2400, dtype=np.float32), 24000, format="WAV")

    wav_bytes = buf.getvalue()



    calls: list[str] = []

    posted: list[dict] = []



    class _FakeAsyncClient:

        def __init__(self, *args, **kwargs):

            pass



        async def __aenter__(self):

            return self



        async def __aexit__(self, *args):

            return False



        async def get(self, url: str, **kwargs):

            calls.append(f"GET {url}")

            if url.endswith("/profiles"):

                return _FakeResp(

                    json_data=[

                        {

                            "id": "p1",

                            "name": "Emily-kokoro-af_bella-en",

                            "voice_type": "preset",

                            "preset_engine": "kokoro",

                            "preset_voice_id": "af_bella",

                        }

                    ]

                )

            if "/audio/" in url:

                return _FakeResp(content=wav_bytes)

            return _FakeResp(status_code=404, json_data={"detail": "not ready"})



        async def post(self, url: str, **kwargs):

            calls.append(f"POST {url}")

            if url.endswith("/profiles"):

                return _FakeResp(json_data={"id": "p-new", "name": "Emily-kokoro-af_bella-en"})

            posted.append(kwargs.get("json") or {})

            return _FakeResp(json_data={"id": "g1", "status": "generating"})



    class _FakeSyncClient:

        def __init__(self, *args, **kwargs):

            pass



        def __enter__(self):

            return self



        def __exit__(self, *args):

            return False



        def get(self, url: str, **kwargs):

            return _FakeResp(status_code=200, json_data={"ok": True})



    import httpx



    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    monkeypatch.setattr(httpx, "Client", _FakeSyncClient)



    eng = VoiceboxTTS(

        settings=SimpleNamespace(

            voice_voicebox_profile="Emily",

            voice_voicebox_use_presets=True,

            voice_voicebox_personality=False,

        )

    )

    assert eng.available() is True

    chunk = await eng.synthesize(SpeechPlan(text="Hello Emily", language="en"))

    assert chunk.backend == "voicebox"

    assert len(chunk.samples) > 0

    assert any("POST" in c and "/generate" in c for c in calls)

    assert not any("/speak" in c for c in calls)

    assert posted and posted[0].get("personality") is False

    assert posted[0].get("engine") == "kokoro"

