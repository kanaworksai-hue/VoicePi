from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf

import audio.playback as playback


def _write_wav(path: Path, sample_rate: int = 16000) -> None:
    data = np.zeros((sample_rate // 4,), dtype=np.float32)
    sf.write(str(path), data, sample_rate, subtype="PCM_16")


def test_cli_play_with_warmup_runs_two_play_commands(
    tmp_path: Path, monkeypatch
) -> None:
    wav = tmp_path / "sample.wav"
    _write_wav(wav)

    calls: list[list[str]] = []

    def fake_run(**kwargs):
        calls.append(list(kwargs["args"]))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(playback, "_PLAY_CMDS", ["fake-play"])
    monkeypatch.setattr(playback.subprocess, "run", fake_run)

    ok = playback._cli_play(str(wav), timeout_seconds=5.0, warmup_seconds=0.05)

    assert ok
    assert len(calls) == 2
    assert calls[0][0] == "fake-play"
    assert calls[1] == ["fake-play", str(wav)]
    assert calls[0][1] != str(wav)


def test_cli_play_without_warmup_runs_main_play_only(
    tmp_path: Path, monkeypatch
) -> None:
    wav = tmp_path / "sample.wav"
    _write_wav(wav)

    calls: list[list[str]] = []

    def fake_run(**kwargs):
        calls.append(list(kwargs["args"]))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(playback, "_PLAY_CMDS", ["fake-play"])
    monkeypatch.setattr(playback.subprocess, "run", fake_run)

    ok = playback._cli_play(str(wav), timeout_seconds=5.0, warmup_seconds=0.0)

    assert ok
    assert calls == [["fake-play", str(wav)]]
