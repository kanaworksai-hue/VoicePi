from __future__ import annotations

import threading
import time
from typing import Callable

from audio.local_asr import LocalKeywordASR
from audio.recorder import VADRecorder


class MicListener:
    def __init__(
        self,
        local_asr: LocalKeywordASR,
        keywords: list[str],
        on_trigger: Callable[[str, str], None],
        on_status: Callable[[str], None] | None = None,
        keyword_max_seconds: float = 2.8,
        keyword_start_timeout: float = 1.6,
        keyword_end_silence_ms: int = 550,
        keyword_cycle_sleep_seconds: float = 0.25,
        keyword_vad_mode: int = 3,
        keyword_min_rms: float = 650.0,
        keyword_min_speech_frames: int = 5,
    ) -> None:
        self._local_asr = local_asr
        self._keywords = [k.strip() for k in keywords if k.strip()]
        self._on_trigger = on_trigger
        self._on_status = on_status
        self._keyword_max_seconds = keyword_max_seconds
        self._keyword_start_timeout = keyword_start_timeout
        self._keyword_end_silence_ms = keyword_end_silence_ms
        self._keyword_cycle_sleep_seconds = keyword_cycle_sleep_seconds
        self._recorder = VADRecorder(
            vad_mode=keyword_vad_mode,
            min_rms=keyword_min_rms,
            min_speech_frames=keyword_min_speech_frames,
        )
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._enabled = False
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            self._enabled = True
            self._ensure_thread()
            self._status("Listening")

    def stop(self) -> None:
        with self._lock:
            self._enabled = False
            self._stop_event.set()
            self._status("Stopped")

    def enable(self) -> None:
        self._enabled = True
        self._ensure_thread()
        self._status("Listening")

    def disable(self) -> None:
        self._enabled = False
        self._status("Paused")

    def suspend(self) -> None:
        self._enabled = False

    def resume(self) -> None:
        self._enabled = True
        self._ensure_thread()

    def is_enabled(self) -> bool:
        return self._enabled

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self._enabled:
                time.sleep(0.05)
                continue

            try:
                pcm = self._recorder.record_until_silence(
                    max_seconds=self._keyword_max_seconds,
                    start_timeout=self._keyword_start_timeout,
                    end_silence_ms=self._keyword_end_silence_ms,
                )
                if not pcm:
                    time.sleep(self._keyword_cycle_sleep_seconds)
                    continue

                text = self._local_asr.transcribe_pcm(pcm, sample_rate=16000)
            except Exception as exc:
                self._status(f"Wake error: {exc}")
                time.sleep(max(0.3, self._keyword_cycle_sleep_seconds))
                continue

            if not text:
                # No speech recognised — stay quiet, don't spam status.
                time.sleep(self._keyword_cycle_sleep_seconds)
                continue

            normalized = self._normalize_text(text)
            matched = ""
            for keyword in self._keywords:
                if self._normalize_text(keyword) in normalized:
                    matched = keyword
                    self._status(f"Wake word: {keyword}")
                    self._on_trigger(text, keyword)
                    time.sleep(0.5)
                    break
            if not matched:
                self._status(f"Heard: '{text}' (no match)")
            time.sleep(self._keyword_cycle_sleep_seconds)

    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _status(self, msg: str) -> None:
        if self._on_status:
            self._on_status(msg)

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = text.casefold().strip().replace(" ", "")
        for punct in ",.!?;:\"'()[]{}":
            normalized = normalized.replace(punct, "")
        return normalized
