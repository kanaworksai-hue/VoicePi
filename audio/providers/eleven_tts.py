from __future__ import annotations

from typing import Iterator

from api.elevenlabs import ElevenLabsClient


class ElevenLabsTTSProvider:
    def __init__(self, client: ElevenLabsClient, voice_id: str) -> None:
        self._client = client
        self._voice_id = voice_id

    def generate(self, text: str) -> bytes:
        if not text:
            return b""
        return self._client.tts(text, voice_id=self._voice_id)

    def generate_stream_pcm(self, text: str) -> Iterator[bytes]:
        if not text:
            return
        yield from self._client.tts_stream_pcm(text, voice_id=self._voice_id)
