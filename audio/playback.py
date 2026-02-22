from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Iterable

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


class StreamPlaybackSession:
    def __init__(self, sample_rate: int, channels: int = 1) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate must be > 0")
        if channels <= 0:
            raise ValueError("channels must be > 0")
        self._sample_rate = sample_rate
        self._channels = channels
        self._frame_bytes = channels * 2
        self._stream = None
        self._proc = None
        self._backend = ""
        self._leftover = b""

    def __enter__(self) -> StreamPlaybackSession:
        self.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def start(self) -> None:
        if self._stream is not None or self._proc is not None:
            return
        if shutil.which("pw-play"):
            self._start_pw_play()
            return
        self._start_sounddevice()

    def _start_sounddevice(self) -> None:
        import sounddevice as sd

        self._stream = sd.RawOutputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
        )
        self._stream.start()
        self._backend = "sounddevice"

    def _start_pw_play(self) -> None:
        args = [
            "pw-play",
            "--raw",
            "--rate",
            str(self._sample_rate),
            "--channels",
            str(self._channels),
            "--format",
            "s16",
            "--latency",
            "40ms",
            "-",
        ]
        self._proc = subprocess.Popen(
            args=args,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._backend = "pw-play"

    def write_pcm16(self, pcm_chunk: bytes) -> bool:
        if not pcm_chunk:
            return False
        if self._stream is None and self._proc is None:
            raise RuntimeError("stream is not started")
        payload = self._leftover + pcm_chunk
        if len(payload) < self._frame_bytes:
            self._leftover = payload
            return False
        valid_len = len(payload) - (len(payload) % self._frame_bytes)
        self._leftover = payload[valid_len:]
        if valid_len <= 0:
            return False
        data = payload[:valid_len]
        if self._backend == "pw-play":
            if self._proc is None or self._proc.stdin is None:
                raise RuntimeError("pw-play stream is not available")
            self._proc.stdin.write(data)
            self._proc.stdin.flush()
        else:
            self._stream.write(data)
        return True

    def close(self) -> None:
        if self._stream is None and self._proc is None:
            return
        try:
            if self._leftover:
                pad = b"\x00" * (self._frame_bytes - len(self._leftover))
                padded = self._leftover + pad
                if self._backend == "pw-play":
                    if self._proc is not None and self._proc.stdin is not None:
                        self._proc.stdin.write(padded)
                        self._proc.stdin.flush()
                else:
                    self._stream.write(padded)
        finally:
            if self._backend == "pw-play":
                proc = self._proc
                if proc is not None:
                    if proc.stdin is not None:
                        proc.stdin.close()
                    try:
                        proc.wait(timeout=4.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=1.0)
                self._proc = None
                self._leftover = b""
                self._backend = ""
                return
            if self._stream is not None:
                try:
                    self._stream.stop()
                finally:
                    self._stream.close()
            self._stream = None
            self._leftover = b""
            self._backend = ""


def play_pcm16_stream(chunks: Iterable[bytes], sample_rate: int, channels: int = 1) -> bool:
    wrote_any = False
    try:
        with StreamPlaybackSession(sample_rate=sample_rate, channels=channels) as session:
            for chunk in chunks:
                wrote_any = session.write_pcm16(chunk) or wrote_any
    except Exception:
        return False
    return wrote_any


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
    filepath: str,
    min_lead_silence_seconds: float,
    force_prepend: bool = False,
) -> tuple[str, str | None]:
    if min_lead_silence_seconds <= 0:
        return (filepath, None)
    try:
        data, sample_rate = sf.read(filepath, dtype="float32")
    except Exception:
        return (filepath, None)
    lead = _leading_silence_seconds(data, sample_rate)
    if force_prepend:
        missing = min_lead_silence_seconds
    else:
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
        f"path={Path(filepath).name} lead={lead:.3f}s added={missing:.3f}s force={int(force_prepend)}"
    )
    return (tmp_path, tmp_path)


def _warmup_backend(
    cmd: str, sample_rate: int, channels: int, warmup_seconds: float
) -> None:
    if warmup_seconds <= 0 or sample_rate <= 0 or channels <= 0:
        return
    frames = int(round(sample_rate * warmup_seconds))
    if frames <= 0:
        return
    if channels == 1:
        data = np.zeros((frames,), dtype=np.float32)
    else:
        data = np.zeros((frames, channels), dtype=np.float32)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, data, sample_rate, subtype="PCM_16", format="WAV")
        timeout = max(2.0, warmup_seconds * 8.0 + 1.0)
        result = subprocess.run(
            args=[cmd, tmp_path],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        _debug(
            "warmup "
            f"cmd={cmd} rc={result.returncode} seconds={warmup_seconds:.3f} "
            f"rate={sample_rate} ch={channels}"
        )
    except Exception:
        _debug(
            "warmup exception "
            f"cmd={cmd} seconds={warmup_seconds:.3f} rate={sample_rate} ch={channels}"
        )
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def _wav_format(filepath: str) -> tuple[int, int] | None:
    try:
        info = sf.info(filepath)
    except Exception:
        return None
    if info.samplerate <= 0 or info.channels <= 0:
        return None
    return (int(info.samplerate), int(info.channels))


def _cli_play(
    filepath: str,
    timeout_seconds: float | None = None,
    warmup_seconds: float = 0.0,
) -> bool:
    wav_format = _wav_format(filepath) if warmup_seconds > 0 else None
    for cmd in _PLAY_CMDS:
        if wav_format is not None:
            _warmup_backend(
                cmd,
                sample_rate=wav_format[0],
                channels=wav_format[1],
                warmup_seconds=warmup_seconds,
            )
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


def play_audio_bytes(
    audio_bytes: bytes,
    min_lead_silence_seconds: float = 0.0,
    warmup_seconds: float = 0.0,
) -> bool:
    if not audio_bytes:
        return False
    try:
        data, samplerate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    except Exception:
        return False

    tmp_path = None
    prepared_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, data, samplerate, subtype="PCM_16", format="WAV")
        play_path = tmp_path
        play_path, prepared_path = _prepare_file_with_min_lead_silence(
            play_path,
            min_lead_silence_seconds,
            force_prepend=True,
        )
        return _cli_play(
            play_path,
            timeout_seconds=_play_timeout_seconds(play_path),
            warmup_seconds=warmup_seconds,
        )
    except Exception:
        return False
    finally:
        if prepared_path:
            Path(prepared_path).unlink(missing_ok=True)
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
