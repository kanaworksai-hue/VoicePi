from __future__ import annotations

import io
import struct
from pathlib import Path

from piper import PiperVoice, SynthesisConfig


class PiperTTSPlayer:
    def __init__(self, model: str = "en_US-lessac-medium", speaker: int = 0) -> None:
        model_path = self._resolve_model(model)
        self._voice = PiperVoice.load(str(model_path))
        self._syn_config = SynthesisConfig(speaker_id=speaker if speaker else None)

    def generate(self, text: str) -> bytes:
        """Generate WAV bytes from *text* using Piper TTS."""
        pcm_parts: list[bytes] = []
        for chunk in self._voice.synthesize(text, self._syn_config):
            pcm_parts.append(chunk.audio_int16_bytes)
        pcm = b"".join(pcm_parts)
        return self._pcm_to_wav(pcm, self._voice.config.sample_rate)

    @staticmethod
    def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
        """Wrap raw 16-bit mono PCM in a WAV container."""
        buf = io.BytesIO()
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + len(pcm)))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        buf.write(b"data")
        buf.write(struct.pack("<I", len(pcm)))
        buf.write(pcm)
        return buf.getvalue()

    @staticmethod
    def _resolve_model(name: str) -> Path:
        """Return the path to a Piper .onnx model, downloading if needed."""
        # If user gave an explicit path that exists, use it directly.
        explicit = Path(name).expanduser()
        if explicit.suffix == ".onnx" and explicit.exists():
            return explicit

        # Otherwise treat *name* as a Piper model shorthand and look for it
        # in the standard download directories.
        data_dir = Path.home() / ".local" / "share" / "piper"
        candidates = [
            data_dir / f"{name}.onnx",
            data_dir / name / f"{name}.onnx",
        ]
        for p in candidates:
            if p.exists():
                return p

        # Auto-download via piper.download_voices.
        try:
            from piper.download_voices import download_voice

            data_dir.mkdir(parents=True, exist_ok=True)
            download_voice(name, data_dir)
            model_path = data_dir / f"{name}.onnx"
            if model_path.exists():
                return model_path
            raise FileNotFoundError(f"Download succeeded but model file not found at {model_path}")
        except Exception as exc:
            raise FileNotFoundError(
                f"Piper model '{name}' not found and auto-download failed: {exc}"
            ) from exc
