# VoicePi Release Checklist

Use this checklist before changing visibility, creating a release tag, or sharing the repository.

## 1. Security And Secrets
- [ ] Confirm `.env` is not tracked: `git ls-files | grep -x ".env"` returns nothing.
- [ ] Confirm no keys/tokens in tracked files (including commit history).
- [ ] Confirm `.env.example` contains placeholders only (no real credentials).
- [ ] Confirm local-only paths and machine-specific values are not required in docs.

## 2. Repository Hygiene
- [ ] `.gitignore` includes local/cache/build files (`.venv/`, `__pycache__/`, `.cache/`, `models/`, `.claude/`).
- [ ] `README.md` has complete install, config, run, and troubleshooting basics.
- [ ] `LICENSE` exists and is correct for intended open-source use.
- [ ] Remove unused large files that do not belong in source control.

## 3. Functional Verification
- [ ] Syntax check passes: `python -m py_compile app.py api/*.py audio/*.py ui/*.py config.py`.
- [ ] Manual smoke test passes:
- [ ] Launch app (`python app.py`).
- [ ] Wake word is detected.
- [ ] STT -> LLM -> TTS roundtrip works.
- [ ] Sprite switches to `talk` during playback and returns to `idle`.

## 4. Documentation Accuracy
- [ ] TTS provider behavior in docs matches code behavior.
- [ ] Required API keys are clearly marked as required.
- [ ] Optional settings are clearly marked as optional.
- [ ] Example commands are copy-paste runnable.

## 5. GitHub Release Prep
- [ ] Default branch is up to date and clean.
- [ ] Create an annotated tag for the release (`vX.Y.Z`).
- [ ] Draft release notes with key changes and known limitations.
- [ ] Add screenshots/GIF for UI updates if relevant.

## 6. Post-Release Monitoring
- [ ] Watch Issues for install/runtime breakages.
- [ ] Track dependency/API changes (Gemini, ElevenLabs, TTS backends).
- [ ] Schedule updates for docs when setup steps change.
