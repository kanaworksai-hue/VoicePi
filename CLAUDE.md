# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

VoicePi is a desktop pet for Raspberry Pi: a transparent, draggable GTK 4 sprite window with voice interaction. It listens for a local wake word via Vosk ASR, then does a cloud roundtrip (ElevenLabs STT -> Gemini LLM -> TTS) and plays back the spoken reply.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run
python app.py
GTK_A11Y=none python app.py          # suppress accessibility bus warnings on headless/minimal desktops
VOICEPI_DEBUG_UI=1 python app.py     # visible window decorations + debug border

# Quick syntax check (no test suite exists)
python -m py_compile app.py api/*.py audio/*.py ui/*.py
```

## Architecture

The conversation flow is a single pipeline orchestrated in `app.py` -> `VoicePetApp._handle_conversation`:

1. **Wake-word detection** (`audio/mic_listener.py` -> `audio/local_asr.py`): `MicListener` runs a background thread that continuously records short clips via `VADRecorder`, feeds PCM to Vosk (`LocalKeywordASR`), and fuzzy-matches against keywords from `config/keywords.txt`. On match, it fires `on_trigger`.

2. **Conversation turn** (`app.py`): suspends the mic listener, plays an optional local acknowledgement WAV (`assets/wake_ack.wav`), records user speech with `VADRecorder`, sends PCM -> ElevenLabs STT, sends text -> Gemini LLM, sends reply -> TTS, then plays audio via `aplay` (preferred on Pi) or `sounddevice`.

3. **UI** (`ui/sprite_window.py`): `SpriteWindow` loads a sprite sheet, animates frames at configured FPS, handles left-click drag, and shows a right-click context menu (start/stop listening, quit).

Key modules:
- `config.py`: loads settings from `.env` + `config/sprite.json` + `config/keywords.txt` into `AppConfig`.
- `audio/recorder.py`: `VADRecorder` wraps `sounddevice` + `webrtcvad` for voice-activity-triggered recording with configurable RMS/VAD thresholds.
- `audio/playback.py`: tries `pw-play`/`aplay`, then falls back to `sounddevice`.
- `api/elevenlabs.py`: STT and TTS via REST.
- `api/gemini.py`: Gemini `generateContent` call with model fallback chain.

## Configuration

All runtime tuning is done in `.env` (loaded by `python-dotenv`).
- `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`, `VOICE_ID`: required secrets
- `KEYWORD_*`: wake-word recording window, VAD sensitivity, noise filtering
- `CONVERSATION_*`: post-wake speech capture window and minimum thresholds
- `WAKE_ACK_*`: acknowledgement audio repeat/gap
- `LOCAL_ASR_MODEL_PATH`: path to the Vosk model directory
- `GEMINI_MODEL`: model name (default `gemini-3-flash-preview`)

## Coding Conventions

- Python 3.13+, type hints throughout (`str | None`, not `Optional`)
- 4-space indent, `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- Audio pipeline is 16 kHz mono PCM (`int16`) internally
- Conversation lock prevents overlapping turns; mic listener uses suspend/resume during conversation
- GTK UI updates must go through `GLib.idle_add()`
