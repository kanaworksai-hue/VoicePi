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


def test_pw_play_wait_timeout_scales_with_remaining_audio(monkeypatch) -> None:
    session = playback.StreamPlaybackSession(sample_rate=24000, channels=1)
    session._started_at = 10.0
    session._written_frames = 12 * 24000

    monkeypatch.setattr(playback.time, "perf_counter", lambda: 15.0)

    timeout = session._pw_play_wait_timeout_seconds()

    # 12s written - 5s elapsed = 7s remaining; timeout adds 8s margin.
    assert timeout == 15.0


def test_pw_play_wait_timeout_uses_minimum_without_timing() -> None:
    session = playback.StreamPlaybackSession(sample_rate=24000, channels=1)

    timeout = session._pw_play_wait_timeout_seconds()

    assert timeout == 6.0
