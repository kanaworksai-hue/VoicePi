# VoicePi Desktop Pet

## Features
- Transparent, borderless, draggable GTK 4 sprite window
- Local wake-word detection with Vosk before cloud calls
- ElevenLabs STT + Gemini + TTS (ElevenLabs / Kitten / Piper)
- Continuous multi-turn conversation after wake (shared session context)
- Right-click menu to start or stop listening

## Requirements
- Raspberry Pi OS (or another Linux desktop with GTK 4 support)
- Python 3.13+
- Microphone + speaker
- Internet access for Gemini and ElevenLabs APIs

## Install (Raspberry Pi OS)
```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-gi gir1.2-gtk-4.0 python3-gi-cairo \
  libgirepository1.0-dev libcairo2-dev pkg-config \
  portaudio19-dev libsndfile1 wget unzip

# Optional, only needed for Kitten TTS on some systems
sudo apt install -y espeak-ng

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration
1. Copy `.env.example` to `.env`.
```bash
cp .env.example .env
```
2. Set required keys in `.env`:
- `ELEVENLABS_API_KEY` (required for conversation STT in current app)
- `GEMINI_API_KEY` (required for LLM responses)
3. Choose TTS provider with `TTS_PROVIDER`:
- `piper` or `kitten` do not require `VOICE_ID`
- `elevenlabs` requires both `ELEVENLABS_API_KEY` and `VOICE_ID`
4. Download and extract the English Vosk model into `models/`:
```bash
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
cd ..
```
5. If your model is in a different location, set `LOCAL_ASR_MODEL_PATH` in `.env`.
6. Put your sprite sheet at `assets/sprite.png`.
7. Edit `config/sprite.json`:
- Set frame size/count/fps/scale for `image_path`
- Optional: set `talk_image_path` for speaking animation (same frame layout as idle)
8. Edit `config/keywords.txt` (one wake keyword per line).
9. Optional: set `WAKE_ACK_AUDIO_PATH` to a local WAV played right after wake detection.

## TTS Providers
- `TTS_PROVIDER=elevenlabs`: uses `ELEVENLABS_API_KEY` + `VOICE_ID`
- `TTS_PROVIDER=kitten`: uses `KITTEN_MODEL_NAME` + `KITTEN_VOICE`
- `TTS_PROVIDER=piper`: uses `PIPER_MODEL` + `PIPER_SPEAKER`

## Run
```bash
source .venv/bin/activate
python app.py
```

If your desktop session prints accessibility bus warnings:
```bash
GTK_A11Y=none python app.py
```

## Quick Check
```bash
python -m py_compile app.py api/*.py audio/*.py ui/*.py config.py
```

## Notes
- Right-click the window for: Start Listening / Stop Listening / Quit.
- Wake-word detection is local (Vosk); conversation STT is ElevenLabs.
- After wake, conversation keeps listening turn-by-turn until missed captures reach `CONVERSATION_MAX_MISSES`.
- Playback falls back across `pw-play`, `aplay`, and `sounddevice`.
- Tune recording behavior with `KEYWORD_*` and `CONVERSATION_*` variables.
