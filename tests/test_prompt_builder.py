from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from prompt_builder import (
    build_system_prompt,
    build_system_prompt_with_warnings,
    load_markdown_or_fallback,
)


@dataclass
class DummyPromptConfig:
    identity_path: Path
    soul_path: Path


def test_load_markdown_or_fallback_missing_file_uses_fallback(tmp_path: Path) -> None:
    fallback = "# FALLBACK"
    missing = tmp_path / "missing.md"
    assert load_markdown_or_fallback(missing, fallback) == fallback


def test_load_markdown_or_fallback_empty_file_uses_fallback(tmp_path: Path) -> None:
    fallback = "# FALLBACK"
    empty = tmp_path / "empty.md"
    empty.write_text(" \n\t\n", encoding="utf-8")
    assert load_markdown_or_fallback(empty, fallback) == fallback


def test_load_markdown_or_fallback_preserves_utf8(tmp_path: Path) -> None:
    text = "# IDENTITY\n- Name: Cafe\u0301 Assistant\n"
    path = tmp_path / "identity.md"
    path.write_text(text, encoding="utf-8")
    assert load_markdown_or_fallback(path, "fallback") == text


def test_build_system_prompt_uses_file_content_in_order(tmp_path: Path) -> None:
    identity_path = tmp_path / "identity.md"
    soul_path = tmp_path / "soul.md"
    identity_path.write_text("# IDENTITY\n- Name: Unit\n", encoding="utf-8")
    soul_path.write_text("# SOUL\n## Core Truths\n- Test\n", encoding="utf-8")
    cfg = DummyPromptConfig(identity_path=identity_path, soul_path=soul_path)

    prompt = build_system_prompt(cfg)

    assert prompt.index("# IDENTITY") < prompt.index("# SOUL")
    assert "# VOICEPI_RUNTIME_RULES" in prompt


def test_build_system_prompt_with_warnings_reports_fallbacks(tmp_path: Path) -> None:
    cfg = DummyPromptConfig(
        identity_path=tmp_path / "identity_missing.md",
        soul_path=tmp_path / "soul_missing.md",
    )

    prompt, warnings = build_system_prompt_with_warnings(cfg)

    assert len(warnings) == 2
    assert "IDENTITY fallback" in warnings[0]
    assert "SOUL fallback" in warnings[1]
    assert "# IDENTITY" in prompt
    assert "# SOUL" in prompt
