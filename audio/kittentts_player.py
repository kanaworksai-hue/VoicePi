from __future__ import annotations

import io
import struct
from ctypes import util as _ctypes_util

import espeakng_loader as _espeak_loader
import numpy as np
from phonemizer.backend.espeak.wrapper import EspeakWrapper as _EspeakWrapper

# Prefer system espeak-ng if available; this avoids loader failures on some distros.
_sys_espeak = _ctypes_util.find_library("espeak-ng")
if _sys_espeak:
    _espeak_loader.get_library_path = lambda: _sys_espeak

# Older phonemizer wrappers may not expose set_data_path; Kitten imports expect it.
if not hasattr(_EspeakWrapper, "set_data_path"):
    _EspeakWrapper.set_data_path = classmethod(
        lambda cls, p: setattr(cls, "data_path", p)
    )

from kittentts import KittenTTS


class KittenTTSPlayer:
    def __init__(
        self,
        model_name: str = "KittenML/kitten-tts-nano-0.8-int8",
        voice: str = "expr-voice-2-f",
    ) -> None:
        self._model = KittenTTS(model_name=model_name)
        self._voice = voice

    def generate(self, text: str) -> bytes:
        audio_np = self._model.generate(text, voice=self._voice)
        return self._numpy_to_wav(audio_np, sample_rate=24000)

    @staticmethod
    def _numpy_to_wav(samples: np.ndarray, sample_rate: int) -> bytes:
        pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
        buf = io.BytesIO()
        num_samples = pcm.shape[0]
        data_size = num_samples * 2

        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")

        buf.write(b"fmt ")
        buf.write(
            struct.pack(
                "<IHHIIHH",
                16,  # fmt chunk size
                1,  # PCM format
                1,  # mono
                sample_rate,
                sample_rate * 2,  # byte rate
                2,  # block align
                16,  # bits per sample
            )
        )

        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(pcm.tobytes())
        return buf.getvalue()
