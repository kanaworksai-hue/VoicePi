from __future__ import annotations

from pathlib import Path

import config as config_module
import pytest


def test_load_config_uses_default_prompt_paths(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("SOUL_PATH", raising=False)
    monkeypatch.delenv("IDENTITY_PATH", raising=False)

    cfg = config_module.load_config()

    assert cfg.soul_path == (config_module.BASE_DIR / "soul.md").resolve()
    assert cfg.identity_path == (config_module.BASE_DIR / "identity.md").resolve()


def test_load_config_respects_prompt_path_overrides(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("SOUL_PATH", "custom/soul.md")
    monkeypatch.setenv("IDENTITY_PATH", "custom/identity.md")

    cfg = config_module.load_config()

    assert cfg.soul_path == Path("custom/soul.md").expanduser().resolve()
    assert cfg.identity_path == Path("custom/identity.md").expanduser().resolve()


def test_load_config_uses_default_tts_lead_silence(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("TTS_MIN_LEAD_SILENCE_SECONDS", raising=False)

    cfg = config_module.load_config()

    assert cfg.tts_min_lead_silence_seconds == 0.30


def test_load_config_uses_default_tts_warmup(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.delenv("TTS_PLAYBACK_WARMUP_SECONDS", raising=False)

    cfg = config_module.load_config()

    assert cfg.tts_playback_warmup_seconds == 0.12


def test_load_config_rejects_negative_tts_lead_silence(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("TTS_MIN_LEAD_SILENCE_SECONDS", "-0.01")

    with pytest.raises(ValueError, match="TTS_MIN_LEAD_SILENCE_SECONDS must be >= 0"):
        config_module.load_config()


def test_load_config_rejects_negative_tts_warmup(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda: None)
    monkeypatch.setenv("TTS_PLAYBACK_WARMUP_SECONDS", "-0.01")

    with pytest.raises(ValueError, match="TTS_PLAYBACK_WARMUP_SECONDS must be >= 0"):
        config_module.load_config()
