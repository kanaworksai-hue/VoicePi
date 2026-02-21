from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.elevenlabs import ElevenLabsClient
    from audio.tts_provider import TTSProvider
    from config import AppConfig

VALID_TTS_PROVIDERS = ("elevenlabs", "kitten", "piper")


def build_tts_provider(
    cfg: AppConfig, eleven_client: ElevenLabsClient | None = None
) -> TTSProvider:
    provider = cfg.tts_provider.strip().lower()

    if provider == "piper":
        from audio.piper_tts import PiperTTSPlayer

        return PiperTTSPlayer(model=cfg.piper_model, speaker=cfg.piper_speaker)

    if provider == "kitten":
        from audio.kittentts_player import KittenTTSPlayer

        return KittenTTSPlayer(
            model_name=cfg.kitten_model_name,
            voice=cfg.kitten_voice,
        )

    if provider == "elevenlabs":
        from api.elevenlabs import ElevenLabsClient
        from audio.providers.eleven_tts import ElevenLabsTTSProvider

        if not cfg.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY is required when TTS_PROVIDER=elevenlabs")
        if not cfg.voice_id:
            raise ValueError("VOICE_ID is required when TTS_PROVIDER=elevenlabs")
        client = eleven_client or ElevenLabsClient(cfg.elevenlabs_api_key, cfg.voice_id)
        return ElevenLabsTTSProvider(client=client, voice_id=cfg.voice_id)

    raise ValueError(
        f"Unsupported TTS provider '{cfg.tts_provider}'. "
        f"Expected one of: {', '.join(VALID_TTS_PROVIDERS)}"
    )
