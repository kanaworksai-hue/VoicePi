from __future__ import annotations

import time
from typing import Callable

_SENTENCE_ENDINGS = {".", "!", "?", "。", "！", "？", "\n"}


def _first_sentence_cut(text: str) -> int | None:
    for idx, char in enumerate(text):
        if char in _SENTENCE_ENDINGS:
            return idx + 1
    return None


class SentenceChunker:
    def __init__(
        self,
        max_chars: int,
        max_wait_ms: int,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be >= 1")
        if max_wait_ms < 0:
            raise ValueError("max_wait_ms must be >= 0")
        self._max_chars = max_chars
        self._max_wait_ms = max_wait_ms
        self._now = now_fn or time.perf_counter
        self._buffer = ""
        self._last_flush = self._now()

    def push(self, text_delta: str) -> list[str]:
        if text_delta:
            self._buffer += text_delta

        flushed = self._drain_sentences()
        if self._should_force_flush():
            forced = self._consume_buffer()
            if forced:
                flushed.append(forced)
                self._last_flush = self._now()
        return flushed

    def finish(self) -> str:
        tail = self._consume_buffer()
        if tail:
            self._last_flush = self._now()
        return tail

    def _drain_sentences(self) -> list[str]:
        out: list[str] = []
        while True:
            cut = _first_sentence_cut(self._buffer)
            if cut is None:
                break
            part = self._buffer[:cut].strip()
            self._buffer = self._buffer[cut:]
            if part:
                out.append(part)
                self._last_flush = self._now()
        return out

    def _should_force_flush(self) -> bool:
        candidate = self._buffer.strip()
        if not candidate:
            return False
        if len(candidate) >= self._max_chars:
            return True
        elapsed_ms = (self._now() - self._last_flush) * 1000.0
        return elapsed_ms >= float(self._max_wait_ms)

    def _consume_buffer(self) -> str:
        chunk = self._buffer.strip()
        self._buffer = ""
        return chunk
