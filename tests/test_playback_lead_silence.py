from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from audio.playback import _prepare_file_with_min_lead_silence


def _write_quiet_lead_wav(path: Path, sample_rate: int = 16000) -> None:
    quiet = np.full((int(sample_rate * 0.20),), 0.003, dtype=np.float32)
    loud = np.full((int(sample_rate * 0.20),), 0.10, dtype=np.float32)
    sf.write(str(path), np.concatenate((quiet, loud)), sample_rate, subtype="PCM_16")


def test_prepare_file_force_prepend_adds_padding(tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    _write_quiet_lead_wav(src)

    out_path, prepared_path = _prepare_file_with_min_lead_silence(
        str(src), min_lead_silence_seconds=0.10, force_prepend=True
    )

    assert prepared_path is not None
    try:
        src_info = sf.info(str(src))
        out_info = sf.info(out_path)
        assert out_info.frames > src_info.frames
    finally:
        Path(prepared_path).unlink(missing_ok=True)


def test_prepare_file_without_force_can_skip_for_quiet_lead(tmp_path: Path) -> None:
    src = tmp_path / "src.wav"
    _write_quiet_lead_wav(src)

    out_path, prepared_path = _prepare_file_with_min_lead_silence(
        str(src), min_lead_silence_seconds=0.10, force_prepend=False
    )

    assert out_path == str(src)
    assert prepared_path is None
