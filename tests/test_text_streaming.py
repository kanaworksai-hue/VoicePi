from __future__ import annotations

from dataclasses import dataclass

from audio.text_streaming import SentenceChunker


@dataclass
class FakeClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value


def test_chunker_flushes_on_sentence_boundary() -> None:
    clock = FakeClock()
    chunker = SentenceChunker(max_chars=80, max_wait_ms=700, now_fn=clock.now)

    out = chunker.push("Hello world.")

    assert out == ["Hello world."]


def test_chunker_flushes_when_max_chars_reached() -> None:
    clock = FakeClock()
    chunker = SentenceChunker(max_chars=5, max_wait_ms=700, now_fn=clock.now)

    out = chunker.push("hello")

    assert out == ["hello"]


def test_chunker_flushes_when_wait_timeout_reached() -> None:
    clock = FakeClock()
    chunker = SentenceChunker(max_chars=50, max_wait_ms=500, now_fn=clock.now)

    assert chunker.push("hello") == []
    clock.value = 0.7

    out = chunker.push("")

    assert out == ["hello"]


def test_chunker_finish_returns_tail() -> None:
    clock = FakeClock()
    chunker = SentenceChunker(max_chars=80, max_wait_ms=700, now_fn=clock.now)

    assert chunker.push("unfinished") == []

    assert chunker.finish() == "unfinished"
