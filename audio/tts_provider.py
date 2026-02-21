from __future__ import annotations

from typing import Protocol


class TTSProvider(Protocol):
    def generate(self, text: str) -> bytes:
        """Generate audio bytes from text."""
