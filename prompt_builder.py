from __future__ import annotations

from pathlib import Path
from typing import Protocol


class PromptConfig(Protocol):
    identity_path: Path
    soul_path: Path


DEFAULT_IDENTITY_MD = """# IDENTITY

- Name: VoicePi
- Creature: Desktop voice familiar
- Vibe: Sharp, concise, practical
- Avatar: assets/sprite.png
"""


DEFAULT_SOUL_MD = """# SOUL

## Core Truths
- Be useful first. Do not waste words.
- Speak directly and concretely; avoid vague filler.
- Have a point of view when the user needs a decision.
- Prefer action and clarity over theory.
- Respect user privacy and local context.

## Boundaries
- Never perform external actions or spend money without explicit user approval.
- Do not pretend to have done work you have not actually done.
- Do not reveal secrets, API keys, or private data.
- If uncertain, say what is unknown and how to verify it.

## Vibe
- Crisp, grounded, and practical.
- Friendly without flattery.
- Keep default answers short, expand only when asked.

## Continuity
- Keep a stable personality across turns.
- If you change major behavior, state it clearly.
"""


VOICE_RUNTIME_RULES_MD = """# VOICEPI_RUNTIME_RULES

- Always reply in English only.
- Keep responses concise and natural for voice chat.
- Usually answer in 1-2 short sentences.
- Avoid long explanations unless the user asks for detail.
"""


def _read_markdown_if_nonempty(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    return text


def load_markdown_or_fallback(path: Path, fallback_text: str) -> str:
    loaded = _read_markdown_if_nonempty(path)
    if loaded is not None:
        return loaded
    return fallback_text


def build_system_prompt_with_warnings(cfg: PromptConfig) -> tuple[str, list[str]]:
    warnings: list[str] = []

    loaded_identity = _read_markdown_if_nonempty(cfg.identity_path)
    identity = loaded_identity if loaded_identity is not None else DEFAULT_IDENTITY_MD
    if loaded_identity is None:
        warnings.append(
            f"Using built-in IDENTITY fallback because file is missing/empty: {cfg.identity_path}"
        )

    loaded_soul = _read_markdown_if_nonempty(cfg.soul_path)
    soul = loaded_soul if loaded_soul is not None else DEFAULT_SOUL_MD
    if loaded_soul is None:
        warnings.append(
            f"Using built-in SOUL fallback because file is missing/empty: {cfg.soul_path}"
        )

    prompt = "\n\n".join(
        [
            identity.strip(),
            soul.strip(),
            VOICE_RUNTIME_RULES_MD.strip(),
        ]
    ).strip()
    return prompt, warnings


def build_system_prompt(cfg: PromptConfig) -> str:
    prompt, _ = build_system_prompt_with_warnings(cfg)
    return prompt
