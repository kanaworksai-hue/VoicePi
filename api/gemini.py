from __future__ import annotations

import json
from typing import Iterable, Iterator

import requests


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-3-flash-preview") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._session = requests.Session()

    def generate(self, user_text: str, system_prompt: str) -> str:
        return self.generate_with_history(
            [{"role": "user", "text": user_text}], system_prompt
        )

    def generate_with_history(
        self, messages: list[dict[str, str]], system_prompt: str
    ) -> str:
        payload = self._build_payload(messages, system_prompt)
        errors: list[str] = []
        for model in self._model_candidates():
            try:
                data = self._generate_once(model, payload)
                return self._extract_text(data)
            except RuntimeError as exc:
                errors.append(str(exc))
                # If model not found, try next model candidate.
                if "not found for API version" in str(exc) or "is not found" in str(exc):
                    continue
                raise

        raise RuntimeError(
            "Gemini generateContent failed for all model candidates: "
            + " | ".join(errors)
        )

    def generate_stream(self, user_text: str, system_prompt: str) -> Iterator[str]:
        return self.generate_stream_with_history(
            [{"role": "user", "text": user_text}], system_prompt
        )

    def generate_stream_with_history(
        self, messages: list[dict[str, str]], system_prompt: str
    ) -> Iterator[str]:
        payload = self._build_payload(messages, system_prompt)
        errors: list[str] = []
        for model in self._model_candidates():
            try:
                yield from self._stream_once(model, payload)
                return
            except RuntimeError as exc:
                errors.append(str(exc))
                # If model not found, try next model candidate.
                if "not found for API version" in str(exc) or "is not found" in str(exc):
                    continue
                raise

        raise RuntimeError(
            "Gemini streamGenerateContent failed for all model candidates: "
            + " | ".join(errors)
        )

    def _generate_once(self, model: str, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        resp = self._session.post(
            f"{self.base_url}/models/{model}:generateContent",
            params={"key": self.api_key},
            headers=headers,
            json=payload,
            timeout=60,
        )
        if not resp.ok:
            detail = self._error_detail(resp)
            raise RuntimeError(
                f"Gemini generateContent failed for model={model} "
                f"({resp.status_code}): {detail}"
            )
        return resp.json()

    def _stream_once(self, model: str, payload: dict) -> Iterator[str]:
        headers = {"Content-Type": "application/json"}
        with self._session.post(
            f"{self.base_url}/models/{model}:streamGenerateContent",
            params={"key": self.api_key, "alt": "sse"},
            headers=headers,
            json=payload,
            timeout=(10, 180),
            stream=True,
        ) as resp:
            if not resp.ok:
                detail = self._error_detail(resp)
                raise RuntimeError(
                    f"Gemini streamGenerateContent failed for model={model} "
                    f"({resp.status_code}): {detail}"
                )

            full_text = ""
            for data_str in self._iter_sse_data(resp):
                if data_str == "[DONE]":
                    break
                try:
                    payload_item = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                text = self._extract_text(payload_item)
                if not text:
                    continue
                delta, full_text = self._extract_delta(text, full_text)
                if delta:
                    yield delta

    def _extract_text(self, data: dict) -> str:
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return ""
        out: list[str] = []
        for part in parts:
            text = part.get("text", "")
            if isinstance(text, str) and text:
                out.append(text)
        return "".join(out)

    def _model_candidates(self) -> list[str]:
        return self._unique(
            [
                self.model,
                "gemini-3-flash-preview",
                "gemini-2.5-flash",
                "gemini-flash-latest",
            ]
        )

    @staticmethod
    def _unique(items: Iterable[str]) -> list[str]:
        out: list[str] = []
        seen = set()
        for item in items:
            key = item.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    @staticmethod
    def _build_contents(messages: list[dict[str, str]]) -> list[dict]:
        contents: list[dict] = []
        for item in messages:
            role = str(item.get("role", "")).strip()
            text = str(item.get("text", "")).strip()
            if role not in {"user", "model"} or not text:
                continue
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": text}],
                }
            )
        return contents

    @classmethod
    def _build_payload(
        cls, messages: list[dict[str, str]], system_prompt: str
    ) -> dict:
        contents = cls._build_contents(messages)
        if not contents:
            raise ValueError(
                "messages must include at least one non-empty item with role user/model"
            )
        return {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]},
        }

    @staticmethod
    def _iter_sse_data(resp: requests.Response) -> Iterator[str]:
        data_lines: list[str] = []
        for line in resp.iter_lines(decode_unicode=True):
            if line is None:
                continue
            row = line.strip()
            if not row:
                if data_lines:
                    yield "\n".join(data_lines)
                    data_lines.clear()
                continue
            if row.startswith(":"):
                continue
            if row.startswith("data:"):
                data_lines.append(row[5:].strip())
        if data_lines:
            yield "\n".join(data_lines)

    @staticmethod
    def _extract_delta(text: str, accumulated: str) -> tuple[str, str]:
        if text.startswith(accumulated):
            delta = text[len(accumulated) :]
            return delta, text
        return text, accumulated + text

    @staticmethod
    def _error_detail(resp: requests.Response) -> str:
        try:
            payload = resp.json()
            err = payload.get("error", {})
            if isinstance(err, dict):
                message = err.get("message")
                if isinstance(message, str) and message:
                    return message
            return str(payload)
        except Exception:
            text = resp.text.strip()
            return text or "unknown error"
