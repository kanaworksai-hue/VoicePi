from __future__ import annotations

from typing import Iterator, Protocol


class TTSProvider(Protocol):
    def generate(self, text: str) -> bytes:
        """Generate audio bytes from text."""


class StreamingTTSProvider(TTSProvider, Protocol):
    def generate_stream_pcm(self, text: str) -> Iterator[bytes]:
        """Generate mono PCM (16-bit little-endian) chunks from text."""
