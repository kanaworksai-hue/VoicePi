from __future__ import annotations

import queue
import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
import webrtcvad


@dataclass
class AudioChunk:
    pcm_bytes: bytes
    timestamp: float


class VADRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        vad_mode: int = 2,
        min_rms: float = 300.0,
        min_speech_frames: int = 3,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.vad = webrtcvad.Vad(vad_mode)
        self.min_rms = min_rms
        self.min_speech_frames = max(1, int(min_speech_frames))
        self._frame_size = int(sample_rate * frame_ms / 1000)

    def _pcm_from_float(self, data: np.ndarray) -> bytes:
        data = np.clip(data, -1.0, 1.0)
        ints = (data * 32767).astype(np.int16)
        return ints.tobytes()

    def _rms(self, pcm_bytes: bytes) -> float:
        if not pcm_bytes:
            return 0.0
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples * samples)))

    def record_until_silence(
        self,
        max_seconds: float = 8.0,
        start_timeout: float = 3.0,
        end_silence_ms: int = 800,
    ) -> bytes:
        q: queue.Queue[AudioChunk] = queue.Queue()
        stop_event = threading.Event()

        def callback(indata, frames, time_info, status):
            if status:
                pass
            pcm = self._pcm_from_float(indata[:, 0])
            q.put(AudioChunk(pcm_bytes=pcm, timestamp=time.time()))

        stream = sd.InputStream(
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self._frame_size,
            dtype="float32",
            callback=callback,
        )

        collected: list[bytes] = []
        pending_voice: deque[bytes] = deque(maxlen=self.min_speech_frames)
        speech_started = False
        last_voice_time = None
        start_time = time.time()

        with stream:
            while not stop_event.is_set():
                now = time.time()
                if now - start_time > max_seconds:
                    break

                try:
                    chunk = q.get(timeout=0.1)
                except queue.Empty:
                    continue

                vad_hit = self.vad.is_speech(chunk.pcm_bytes, self.sample_rate)
                is_speech = vad_hit and self._rms(chunk.pcm_bytes) >= self.min_rms

                if is_speech:
                    pending_voice.append(chunk.pcm_bytes)
                    if speech_started:
                        last_voice_time = now
                        collected.append(chunk.pcm_bytes)
                    elif len(pending_voice) >= self.min_speech_frames:
                        speech_started = True
                        last_voice_time = now
                        collected.extend(list(pending_voice))
                        pending_voice.clear()
                else:
                    pending_voice.clear()
                    if speech_started:
                        collected.append(chunk.pcm_bytes)

                if not speech_started and now - start_time > start_timeout:
                    break

                if speech_started and last_voice_time is not None:
                    if (now - last_voice_time) * 1000 >= end_silence_ms:
                        break

        return b"".join(collected)

    def record_fixed(self, seconds: float = 5.0) -> bytes:
        frames = int(self.sample_rate * seconds)
        data = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="float32")
        sd.wait()
        return self._pcm_from_float(data[:, 0])
