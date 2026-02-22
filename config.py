import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent


@dataclass
class AppConfig:
    elevenlabs_api_key: str
    gemini_api_key: str
    gemini_model: str
    voice_id: str
    local_asr_model_path: Path
    keyword_max_seconds: float
    keyword_start_timeout: float
    keyword_end_silence_ms: int
    keyword_cycle_sleep_seconds: float
    keyword_vad_mode: int
    keyword_min_rms: float
    keyword_min_speech_frames: int
    conversation_max_seconds: float
    conversation_start_timeout: float
    conversation_end_silence_ms: int
    conversation_vad_mode: int
    conversation_min_rms: float
    conversation_min_speech_frames: int
    conversation_min_valid_ms: int
    conversation_max_misses: int
    wake_ack_audio_path: Path
    wake_ack_repeat: int
    wake_ack_gap_seconds: float
    wake_ack_min_lead_silence_seconds: float
    keywords: list[str]
    soul_path: Path
    identity_path: Path
    sprite_image_path: Path
    sprite_talk_image_path: Path | None
    sprite_frame_width: int
    sprite_frame_height: int
    sprite_frame_count: int
    sprite_fps: int
    sprite_scale: float
    tts_provider: str
    piper_model: str
    piper_speaker: int
    kitten_model_name: str
    kitten_voice: str


def _read_keywords(path: Path) -> list[str]:
    if not path.exists():
        return []
    keywords: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if item:
            keywords.append(item)
    return keywords


def load_config() -> AppConfig:
    load_dotenv()
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
    tts_provider = os.getenv("TTS_PROVIDER", "piper").strip().lower()
    if tts_provider not in {"elevenlabs", "kitten", "piper"}:
        raise ValueError(
            "TTS_PROVIDER must be one of: elevenlabs, kitten, piper "
            f"(got '{tts_provider}')"
        )
    voice_id = os.getenv("VOICE_ID", "").strip()
    local_asr_model_path = os.getenv(
        "LOCAL_ASR_MODEL_PATH",
        str(BASE_DIR / "models" / "vosk-model-small-en-us-0.15"),
    ).strip()
    keyword_max_seconds = float(os.getenv("KEYWORD_MAX_SECONDS", "3.2").strip())
    keyword_start_timeout = float(os.getenv("KEYWORD_START_TIMEOUT", "2.2").strip())
    keyword_end_silence_ms = int(os.getenv("KEYWORD_END_SILENCE_MS", "550").strip())
    keyword_cycle_sleep_seconds = float(
        os.getenv("KEYWORD_CYCLE_SLEEP_SECONDS", "0.25").strip()
    )
    keyword_vad_mode = int(os.getenv("KEYWORD_VAD_MODE", "1").strip())
    keyword_min_rms = float(os.getenv("KEYWORD_MIN_RMS", "140").strip())
    keyword_min_speech_frames = int(os.getenv("KEYWORD_MIN_SPEECH_FRAMES", "2").strip())
    conversation_max_seconds = float(os.getenv("CONVERSATION_MAX_SECONDS", "6.0").strip())
    conversation_start_timeout = float(os.getenv("CONVERSATION_START_TIMEOUT", "1.8").strip())
    conversation_end_silence_ms = int(os.getenv("CONVERSATION_END_SILENCE_MS", "700").strip())
    conversation_vad_mode = int(os.getenv("CONVERSATION_VAD_MODE", "3").strip())
    conversation_min_rms = float(os.getenv("CONVERSATION_MIN_RMS", "650").strip())
    conversation_min_speech_frames = int(os.getenv("CONVERSATION_MIN_SPEECH_FRAMES", "5").strip())
    conversation_min_valid_ms = int(os.getenv("CONVERSATION_MIN_VALID_MS", "700").strip())
    conversation_max_misses = int(os.getenv("CONVERSATION_MAX_MISSES", "2").strip())
    if conversation_max_misses < 1:
        raise ValueError("CONVERSATION_MAX_MISSES must be >= 1")
    wake_ack_audio_path = os.getenv(
        "WAKE_ACK_AUDIO_PATH", str(BASE_DIR / "assets" / "wake_ack.wav")
    ).strip()
    wake_ack_repeat = int(os.getenv("WAKE_ACK_REPEAT", "1").strip())
    wake_ack_gap_seconds = float(os.getenv("WAKE_ACK_GAP_SECONDS", "0.08").strip())
    wake_ack_min_lead_silence_seconds = float(
        os.getenv("WAKE_ACK_MIN_LEAD_SILENCE_SECONDS", "0.45").strip()
    )
    soul_path = os.getenv("SOUL_PATH", "").strip() or str(BASE_DIR / "soul.md")
    identity_path = os.getenv("IDENTITY_PATH", "").strip() or str(
        BASE_DIR / "identity.md"
    )

    piper_model = os.getenv("PIPER_MODEL", "en_US-lessac-medium").strip()
    piper_speaker = int(os.getenv("PIPER_SPEAKER", "0").strip())
    kitten_model_name = os.getenv(
        "KITTEN_MODEL_NAME", "KittenML/kitten-tts-nano-0.8-int8"
    ).strip()
    kitten_voice = os.getenv("KITTEN_VOICE", "expr-voice-2-f").strip()

    sprite_cfg_path = BASE_DIR / "config" / "sprite.json"
    sprite_cfg = json.loads(sprite_cfg_path.read_text(encoding="utf-8"))
    image_path = (BASE_DIR / sprite_cfg["image_path"]).resolve()
    talk_image_cfg = str(sprite_cfg.get("talk_image_path", "")).strip()
    talk_image_path = (BASE_DIR / talk_image_cfg).resolve() if talk_image_cfg else None

    keywords_path = BASE_DIR / "config" / "keywords.txt"
    keywords = _read_keywords(keywords_path)

    return AppConfig(
        elevenlabs_api_key=elevenlabs_api_key,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        voice_id=voice_id,
        local_asr_model_path=Path(local_asr_model_path).expanduser().resolve(),
        keyword_max_seconds=keyword_max_seconds,
        keyword_start_timeout=keyword_start_timeout,
        keyword_end_silence_ms=keyword_end_silence_ms,
        keyword_cycle_sleep_seconds=keyword_cycle_sleep_seconds,
        keyword_vad_mode=keyword_vad_mode,
        keyword_min_rms=keyword_min_rms,
        keyword_min_speech_frames=keyword_min_speech_frames,
        conversation_max_seconds=conversation_max_seconds,
        conversation_start_timeout=conversation_start_timeout,
        conversation_end_silence_ms=conversation_end_silence_ms,
        conversation_vad_mode=conversation_vad_mode,
        conversation_min_rms=conversation_min_rms,
        conversation_min_speech_frames=conversation_min_speech_frames,
        conversation_min_valid_ms=conversation_min_valid_ms,
        conversation_max_misses=conversation_max_misses,
        wake_ack_audio_path=Path(wake_ack_audio_path).expanduser().resolve(),
        wake_ack_repeat=wake_ack_repeat,
        wake_ack_gap_seconds=wake_ack_gap_seconds,
        wake_ack_min_lead_silence_seconds=wake_ack_min_lead_silence_seconds,
        keywords=keywords,
        soul_path=Path(soul_path).expanduser().resolve(),
        identity_path=Path(identity_path).expanduser().resolve(),
        sprite_image_path=image_path,
        sprite_talk_image_path=talk_image_path,
        sprite_frame_width=int(sprite_cfg["frame_width"]),
        sprite_frame_height=int(sprite_cfg["frame_height"]),
        sprite_frame_count=int(sprite_cfg["frame_count"]),
        sprite_fps=int(sprite_cfg["fps"]),
        sprite_scale=float(sprite_cfg.get("scale", 1.0)),
        tts_provider=tts_provider,
        piper_model=piper_model,
        piper_speaker=piper_speaker,
        kitten_model_name=kitten_model_name,
        kitten_voice=kitten_voice,
    )
