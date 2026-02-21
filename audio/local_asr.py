from __future__ import annotations

import json
import os
from pathlib import Path

from vosk import KaldiRecognizer, Model, SetLogLevel


class LocalKeywordASR:
    def __init__(self, model_path: Path, keywords: list[str] | None = None) -> None:
        if not model_path.exists():
            raise FileNotFoundError(f"Vosk model not found: {model_path}")

        SetLogLevel(-1)
        self._model = Model(str(model_path))
        use_grammar = os.getenv("LOCAL_ASR_USE_GRAMMAR", "").strip() == "1"
        self._grammar = self._build_grammar(keywords or []) if use_grammar else None
        self._warm_up()

    def transcribe_pcm(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        if not pcm_bytes:
            return ""

        recognizer = self._new_recognizer(sample_rate)
        recognizer.AcceptWaveform(pcm_bytes)
        result = json.loads(recognizer.FinalResult())
        return str(result.get("text", "")).strip()

    def _new_recognizer(self, sample_rate: int) -> KaldiRecognizer:
        if self._grammar is None:
            recognizer = KaldiRecognizer(self._model, float(sample_rate))
        else:
            recognizer = KaldiRecognizer(self._model, float(sample_rate), self._grammar)
        recognizer.SetWords(False)
        return recognizer

    def _warm_up(self) -> None:
        # Warm up decoder to reduce first recognition latency.
        try:
            recognizer = self._new_recognizer(16000)
            recognizer.AcceptWaveform(b"\x00\x00" * 1600)
            recognizer.FinalResult()
        except Exception:
            pass

    @staticmethod
    def _build_grammar(keywords: list[str]) -> str | None:
        items = [k.strip() for k in keywords if k.strip()]
        if not items:
            return None

        # Add [unk] so recognizer can still handle non-keyword speech.
        grammar_list = []
        seen = set()
        for item in items + ["[unk]"]:
            if item not in seen:
                seen.add(item)
                grammar_list.append(item)
        return json.dumps(grammar_list, ensure_ascii=False)
