from __future__ import annotations

import io
import wave

import requests


class ElevenLabsClient:
    def __init__(
        self,
        api_key: str,
        voice_id: str,
        stt_model_id: str = "scribe_v1",
    ) -> None:
        self.api_key = api_key
        self.voice_id = voice_id
        self.stt_model_id = stt_model_id
        self.base_url = "https://api.elevenlabs.io/v1"
        self._session = requests.Session()

    def _headers(self) -> dict[str, str]:
        return {"xi-api-key": self.api_key}

    def asr_pcm(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        if not pcm_bytes:
            return ""
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        wav_buf.seek(0)

        files = {"file": ("audio.wav", wav_buf.read(), "audio/wav")}
        data = {
            "model_id": self.stt_model_id,
            "file_format": "pcm_s16le_16",
            "language_code": "zh",
        }
        resp = self._session.post(
            f"{self.base_url}/speech-to-text",
            headers=self._headers(),
            data=data,
            files=files,
            timeout=30,
        )
        self._raise_for_status(resp, "speech-to-text")
        data = resp.json()
        return data.get("text", "")

    def tts(self, text: str, voice_id: str | None = None) -> bytes:
        voice = voice_id or self.voice_id
        headers = self._headers()
        headers["accept"] = "audio/mpeg"
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "output_format": "mp3_44100_128",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.7,
            },
        }
        resp = self._session.post(
            f"{self.base_url}/text-to-speech/{voice}",
            headers=headers,
            json=payload,
            timeout=60,
        )
        self._raise_for_status(resp, "text-to-speech")
        return resp.content

    def _raise_for_status(self, resp: requests.Response, api_name: str) -> None:
        if resp.ok:
            return
        detail = ""
        try:
            payload = resp.json()
            if isinstance(payload, dict):
                if isinstance(payload.get("detail"), str):
                    detail = payload["detail"]
                elif isinstance(payload.get("detail"), dict):
                    detail = str(payload["detail"].get("message", payload["detail"]))
                else:
                    detail = str(payload)
            else:
                detail = str(payload)
        except Exception:
            detail = resp.text.strip()
        raise RuntimeError(
            f"ElevenLabs {api_name} failed ({resp.status_code}): {detail or 'unknown error'}"
        )
