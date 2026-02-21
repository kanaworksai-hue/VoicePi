from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

# Prefer PipeWire playback when available, but keep ALSA and sounddevice
# fallback paths for devices where one backend intermittently fails.
_PLAY_CMDS = [cmd for cmd in ("pw-play", "aplay") if shutil.which(cmd)]
_PLAY_RETRIES = 2
_PLAY_RETRY_DELAY_SECONDS = 0.06
_DEBUG_AUDIO = os.getenv("VOICEPI_DEBUG_AUDIO", "0").strip() == "1"


def _debug(msg: str) -> None:
    if _DEBUG_AUDIO:
        print(f"[audio] {msg}", flush=True)


def _fallback_play_with_sounddevice(filepath: str) -> bool:
    try:
        import sounddevice as sd

        data, samplerate = sf.read(filepath, dtype="float32")
        sd.play(data, samplerate)
        sd.wait()
        return True
    except Exception:
        return False


def _estimate_wav_seconds(filepath: str) -> float | None:
    try:
        info = sf.info(filepath)
    except Exception:
        return None
    if info.samplerate <= 0 or info.frames <= 0:
        return None
    return float(info.frames) / float(info.samplerate)


def _play_timeout_seconds(filepath: str) -> float | None:
    duration = _estimate_wav_seconds(filepath)
    if duration is None:
        return None
    # Allow backend startup and buffer drain time beyond raw audio duration.
    return max(12.0, duration * 1.6 + 4.0)


def _leading_silence_seconds(
    data: np.ndarray, sample_rate: int, threshold: float = 0.006
) -> float:
    if sample_rate <= 0 or data.size == 0:
        return 0.0
    if data.ndim == 1:
        levels = np.abs(data)
    else:
        levels = np.max(np.abs(data), axis=1)
    non_silent = np.flatnonzero(levels > threshold)
    if non_silent.size == 0:
        return float(levels.shape[0]) / float(sample_rate)
    return float(non_silent[0]) / float(sample_rate)


def _prepare_file_with_min_lead_silence(
    filepath: str, min_lead_silence_seconds: float
) -> tuple[str, str | None]:
    if min_lead_silence_seconds <= 0:
        return (filepath, None)
    try:
        data, sample_rate = sf.read(filepath, dtype="float32")
    except Exception:
        return (filepath, None)

    lead = _leading_silence_seconds(data, sample_rate)
    missing = min_lead_silence_seconds - lead
    if missing <= 0:
        _debug(
            "lead_silence ok "
            f"path={Path(filepath).name} lead={lead:.3f}s target={min_lead_silence_seconds:.3f}s"
        )
        return (filepath, None)

    pad_frames = int(round(missing * sample_rate))
    if pad_frames <= 0:
        return (filepath, None)
    if data.ndim == 1:
        pad = np.zeros((pad_frames,), dtype=np.float32)
    else:
        pad = np.zeros((pad_frames, data.shape[1]), dtype=np.float32)
    merged = np.concatenate((pad, data), axis=0)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        sf.write(tmp_path, merged, sample_rate, subtype="PCM_16", format="WAV")
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        return (filepath, None)
    _debug(
        "lead_silence padded "
        f"path={Path(filepath).name} lead={lead:.3f}s added={missing:.3f}s"
    )
    return (tmp_path, tmp_path)


def _cli_play(filepath: str, timeout_seconds: float | None = None) -> bool:
    for cmd in _PLAY_CMDS:
        for attempt in range(_PLAY_RETRIES):
            try:
                start = time.perf_counter()
                run_args = dict(
                    args=[cmd, filepath],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if timeout_seconds is not None:
                    run_args["timeout"] = timeout_seconds
                result = subprocess.run(
                    **run_args
                )
                elapsed = time.perf_counter() - start
                _debug(
                    "play "
                    f"cmd={cmd} attempt={attempt + 1}/{_PLAY_RETRIES} "
                    f"rc={result.returncode} elapsed={elapsed:.3f}s "
                    f"file={Path(filepath).name}"
                )
                if result.returncode == 0:
                    return True
            except subprocess.TimeoutExpired:
                # If one backend cannot finish within expected duration,
                # try the next backend instead of retrying the same one.
                _debug(
                    "play timeout "
                    f"cmd={cmd} timeout={timeout_seconds}s file={Path(filepath).name}"
                )
                break
            except Exception:
                _debug(
                    "play exception "
                    f"cmd={cmd} attempt={attempt + 1}/{_PLAY_RETRIES} file={Path(filepath).name}"
                )
                pass
            if attempt < _PLAY_RETRIES - 1:
                time.sleep(_PLAY_RETRY_DELAY_SECONDS)
    _debug(f"play fallback sounddevice file={Path(filepath).name}")
    return _fallback_play_with_sounddevice(filepath)


def play_audio_bytes(audio_bytes: bytes) -> bool:
    if not audio_bytes:
        return False
    try:
        data, samplerate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    except Exception:
        return False

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, data, samplerate, subtype="PCM_16", format="WAV")
        return _cli_play(tmp_path, timeout_seconds=_play_timeout_seconds(tmp_path))
    except Exception:
        return False
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def play_audio_file(
    path: str | Path, min_lead_silence_seconds: float = 0.0
) -> bool:
    audio_path = Path(path)
    if not audio_path.exists():
        return False
    filepath = str(audio_path)
    prepared_path = None
    try:
        filepath, prepared_path = _prepare_file_with_min_lead_silence(
            filepath, min_lead_silence_seconds
        )
        return _cli_play(filepath, timeout_seconds=_play_timeout_seconds(filepath))
    finally:
        if prepared_path:
            Path(prepared_path).unlink(missing_ok=True)
