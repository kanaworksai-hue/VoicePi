# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: GTK application entry point and conversation orchestration.
- `audio/`: microphone capture, VAD, local keyword ASR, and playback.
- `api/`: external API clients (`elevenlabs.py`, `gemini.py`).
- `ui/`: window rendering and interaction (`sprite_window.py`, optional status UI).
- `config.py` + `config/`: runtime config loading, `sprite.json`, and `keywords.txt`.
- `assets/`: sprite sheets and local wake-ack audio files.
- `models/`: local Vosk model directory (for offline wake-word detection).

Keep modules focused: UI in `ui/`, audio pipeline in `audio/`, network calls in `api/`.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate`: create/enter virtualenv.
- `pip install -r requirements.txt`: install Python dependencies.
- `python app.py`: run the desktop pet.
- `GTK_A11Y=none python app.py`: avoid accessibility bus warning on minimal desktop setups.
- `VOICEPI_DEBUG_UI=1 python app.py`: run with visible debug window behavior.
- `python -m py_compile app.py api/*.py audio/*.py ui/*.py`: quick syntax check.

## Coding Style & Naming Conventions
- Python 3.13+, 4-space indentation, UTF-8.
- Use type hints consistently (`str | None`, `list[str]`, etc.).
- Naming:
  - modules/files: `snake_case.py`
  - classes: `PascalCase`
  - functions/variables: `snake_case`
  - constants/env names: `UPPER_SNAKE_CASE`
- Prefer small, single-purpose functions and explicit status messages for runtime state transitions.

## Testing Guidelines
- Current repository has no committed automated test suite.
- For new logic, add `pytest` tests under `tests/` with names like `test_mic_listener.py`.
- Focus first on deterministic units: text normalization, keyword matching, config parsing, API error handling.
- Before opening a PR, run syntax check and a manual smoke test (`python app.py`, wake word, STT/LLM/TTS roundtrip).

## Commit & Pull Request Guidelines
- No Git history is available in this workspace snapshot; use clear conventional messages, e.g.:
  - `feat(audio): tighten wake-word noise filtering`
  - `fix(ui): restore transparent sprite background`
- PRs should include:
  - purpose and scope
  - changed files/modules
  - manual validation steps and results
  - screenshots/video for UI behavior changes
  - updates to `.env.example` when new config keys are introduced.

## Security & Configuration Tips
- Never commit real API keys; keep secrets in `.env` only.
- Keep `.env.example` in sync with required variables.
- Validate model and asset paths locally before release (especially on Raspberry Pi deployments).
