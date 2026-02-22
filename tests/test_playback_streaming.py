from __future__ import annotations

import audio.playback as playback


def test_play_pcm16_stream_writes_chunks(monkeypatch) -> None:
    writes: list[bytes] = []

    class FakeSession:
        def __init__(self, sample_rate: int, channels: int = 1) -> None:
            self.sample_rate = sample_rate
            self.channels = channels

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            return None

        def write_pcm16(self, chunk: bytes) -> bool:
            writes.append(chunk)
            return True

    monkeypatch.setattr(playback, "StreamPlaybackSession", FakeSession)

    ok = playback.play_pcm16_stream([b"\x01\x00\x02\x00"], sample_rate=24000)

    assert ok
    assert writes == [b"\x01\x00\x02\x00"]


def test_play_pcm16_stream_returns_false_on_failure(monkeypatch) -> None:
    class FakeSession:
        def __init__(self, sample_rate: int, channels: int = 1) -> None:
            pass

        def __enter__(self):
            raise RuntimeError("boom")

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            return None

    monkeypatch.setattr(playback, "StreamPlaybackSession", FakeSession)

    ok = playback.play_pcm16_stream([b"\x01\x00\x02\x00"], sample_rate=24000)

    assert not ok
