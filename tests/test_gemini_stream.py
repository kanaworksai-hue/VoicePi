from __future__ import annotations

from api.gemini import GeminiClient


class _FakeResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def iter_lines(self, decode_unicode: bool = True):
        for line in self._lines:
            yield line


def test_extract_delta_handles_prefix_updates() -> None:
    delta, full = GeminiClient._extract_delta("Hel", "")
    assert delta == "Hel"
    assert full == "Hel"

    delta, full = GeminiClient._extract_delta("Hello", full)
    assert delta == "lo"
    assert full == "Hello"


def test_extract_delta_handles_non_prefix_fragments() -> None:
    delta, full = GeminiClient._extract_delta(" world", "Hello")

    assert delta == " world"
    assert full == "Hello world"


def test_iter_sse_data_collects_events() -> None:
    resp = _FakeResponse(
        [
            "data: {\"a\":1}",
            "",
            ":keep-alive",
            "data: {\"b\":2}",
            "data: {\"c\":3}",
            "",
        ]
    )

    out = list(GeminiClient._iter_sse_data(resp))

    assert out == ['{"a":1}', '{"b":2}\n{"c":3}']


def test_extract_finish_reason_reads_first_candidate() -> None:
    payload = {"candidates": [{"finishReason": "MAX_TOKENS"}]}

    reason = GeminiClient._extract_finish_reason(payload)

    assert reason == "MAX_TOKENS"
