from __future__ import annotations

import threading
import time
from typing import Literal

import gi
import numpy as np

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from api.elevenlabs import ElevenLabsClient
from api.gemini import GeminiClient
from audio.local_asr import LocalKeywordASR
from audio.mic_listener import MicListener
from audio.playback import play_audio_bytes, play_audio_file
from audio.recorder import VADRecorder
from audio.tts_factory import build_tts_provider
from audio.tts_provider import TTSProvider
from config import load_config
from ui.sprite_window import SpriteWindow

SYSTEM_PROMPT = (
    "You are a desktop pet assistant. "
    "Always reply in English only. Keep responses concise and natural for voice chat, "
    "usually 1-2 short sentences. Be helpful, but avoid long explanations unless asked."
)


class VoicePetApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.voicepi.pet")
        self._cfg = None
        self._window: SpriteWindow | None = None
        self._mic_listener: MicListener | None = None
        self._tts: TTSProvider | None = None
        self._tts_init_error: str | None = None
        self._conversation_lock = threading.Lock()
        self._last_status = ""

    def do_activate(self):
        cfg = load_config()
        self._cfg = cfg

        self._eleven = ElevenLabsClient(cfg.elevenlabs_api_key, cfg.voice_id)
        self._gemini = GeminiClient(cfg.gemini_api_key, model=cfg.gemini_model)
        try:
            self._tts = build_tts_provider(cfg, eleven_client=self._eleven)
            self._tts_init_error = None
        except Exception as exc:
            self._tts = None
            self._tts_init_error = str(exc)
        self._recorder = VADRecorder(
            vad_mode=cfg.conversation_vad_mode,
            min_rms=cfg.conversation_min_rms,
            min_speech_frames=cfg.conversation_min_speech_frames,
        )
        self._keyword_asr = None

        self._window = SpriteWindow(
            self,
            image_path=str(cfg.sprite_image_path),
            talk_image_path=(
                str(cfg.sprite_talk_image_path) if cfg.sprite_talk_image_path else None
            ),
            frame_width=cfg.sprite_frame_width,
            frame_height=cfg.sprite_frame_height,
            frame_count=cfg.sprite_frame_count,
            fps=cfg.sprite_fps,
            scale=cfg.sprite_scale,
        )
        self._window.present()
        if self._tts_init_error:
            self._set_status(f"TTS init error: {self._tts_init_error}")
        else:
            self._set_status(f"TTS ready: {cfg.tts_provider}")

        self._install_menu()

        def on_trigger(wake_text: str, keyword: str):
            # Pause listener in the wake thread to avoid re-entering capture
            # before the conversation handler gets scheduled.
            listener_pre_suspended = False
            if self._mic_listener is not None:
                self._mic_listener.suspend()
                listener_pre_suspended = True
            threading.Thread(
                target=self._handle_conversation,
                args=(wake_text, keyword, listener_pre_suspended),
                daemon=True,
            ).start()

        try:
            self._keyword_asr = LocalKeywordASR(
                model_path=cfg.local_asr_model_path,
                keywords=cfg.keywords,
            )
        except Exception as exc:
            self._set_status(f"Wake model error: {exc}")
            return

        self._set_status(f"Wake model ready: {cfg.local_asr_model_path.name}")
        self._mic_listener = MicListener(
            self._keyword_asr,
            cfg.keywords,
            on_trigger=on_trigger,
            on_status=self._set_status,
            keyword_max_seconds=cfg.keyword_max_seconds,
            keyword_start_timeout=cfg.keyword_start_timeout,
            keyword_end_silence_ms=cfg.keyword_end_silence_ms,
            keyword_cycle_sleep_seconds=cfg.keyword_cycle_sleep_seconds,
            keyword_vad_mode=cfg.keyword_vad_mode,
            keyword_min_rms=cfg.keyword_min_rms,
            keyword_min_speech_frames=cfg.keyword_min_speech_frames,
        )
        self._mic_listener.start()

    def _install_menu(self) -> None:
        menu = Gio.Menu()
        menu.append("Start Listening", "app.listen_on")
        menu.append("Stop Listening", "app.listen_off")
        menu.append("Quit", "app.quit")

        self._popover = Gtk.PopoverMenu.new_from_model(menu)

        action_on = Gio.SimpleAction.new("listen_on", None)
        action_on.connect("activate", self._on_listen_on)
        self.add_action(action_on)

        action_off = Gio.SimpleAction.new("listen_off", None)
        action_off.connect("activate", self._on_listen_off)
        self.add_action(action_off)

        action_quit = Gio.SimpleAction.new("quit", None)
        action_quit.connect("activate", self._on_quit)
        self.add_action(action_quit)

        if self._window is not None:
            self._window._drawing.add_controller(self._build_right_click_controller())

    def _build_right_click_controller(self) -> Gtk.GestureClick:
        click = Gtk.GestureClick.new()
        click.set_button(3)
        click.connect("pressed", self._on_right_click)
        return click

    def _on_right_click(self, gesture, n_press, x, y):
        if self._window is None:
            return
        self._popover.set_parent(self._window)
        self._popover.set_pointing_to(self._window.get_allocation())
        self._popover.popup()

    def _on_listen_on(self, action, param):
        if self._mic_listener:
            self._mic_listener.enable()
        self._set_status("Listening")

    def _on_listen_off(self, action, param):
        if self._mic_listener:
            self._mic_listener.disable()
        self._set_status("Paused")

    def _on_quit(self, action, param):
        if self._mic_listener:
            self._mic_listener.stop()
        self._set_status("Exiting")
        self.quit()

    def _handle_conversation(
        self, _wake_text: str, _keyword: str, listener_pre_suspended: bool = False
    ) -> None:
        if not self._conversation_lock.acquire(blocking=False):
            self._set_status("Busy")
            if listener_pre_suspended and self._mic_listener is not None:
                self._mic_listener.resume()
            return
        listener_suspended = listener_pre_suspended
        try:
            cfg = self._cfg
            if cfg is None:
                self._set_status("Config missing")
                return
            max_misses = max(1, cfg.conversation_max_misses)
            session_messages: list[dict[str, str]] = []
            miss_count = 0
            turn_index = 0
            if self._mic_listener is not None and not listener_suspended:
                self._mic_listener.suspend()
                listener_suspended = True
            ack_ok = False
            for idx in range(max(1, cfg.wake_ack_repeat)):
                ack_ok = (
                    play_audio_file(
                        cfg.wake_ack_audio_path,
                        min_lead_silence_seconds=cfg.wake_ack_min_lead_silence_seconds,
                    )
                    or ack_ok
                )
                if idx < max(1, cfg.wake_ack_repeat) - 1 and cfg.wake_ack_gap_seconds > 0:
                    time.sleep(cfg.wake_ack_gap_seconds)
            if ack_ok:
                self._set_status("Session started. Speak now.")
                time.sleep(0.18)
            else:
                self._set_status("Ack audio failed. Session started. Speak now.")

            while True:
                rec_start = time.perf_counter()
                pcm = self._recorder.record_until_silence(
                    max_seconds=cfg.conversation_max_seconds,
                    start_timeout=cfg.conversation_start_timeout,
                    end_silence_ms=cfg.conversation_end_silence_ms,
                )
                rec_ms = int((time.perf_counter() - rec_start) * 1000)
                if not pcm:
                    miss_count += 1
                    if self._record_miss(miss_count, max_misses):
                        break
                    continue

                duration_ms, rms = self._pcm_stats(pcm)
                if duration_ms < cfg.conversation_min_valid_ms or rms < cfg.conversation_min_rms:
                    miss_count += 1
                    if self._record_miss(miss_count, max_misses):
                        break
                    continue

                self._set_status(f"Captured {rec_ms}ms. STT...")
                stt_start = time.perf_counter()
                text = self._eleven.asr_pcm(pcm, sample_rate=16000)
                stt_ms = int((time.perf_counter() - stt_start) * 1000)
                text = (text or "").strip()
                if not text:
                    miss_count += 1
                    if self._record_miss(miss_count, max_misses):
                        break
                    continue

                miss_count = 0
                self._set_status(f"You: {text[:28]} (STT {stt_ms}ms)")
                session_messages.append({"role": "user", "text": text})

                llm_start = time.perf_counter()
                reply = self._gemini.generate_with_history(session_messages, SYSTEM_PROMPT)
                llm_ms = int((time.perf_counter() - llm_start) * 1000)
                reply = (reply or "").strip()
                if not reply:
                    self._set_status("No LLM reply. Session ended")
                    break
                session_messages.append({"role": "model", "text": reply})

                self._set_status(f"Reply ready (LLM {llm_ms}ms). TTS...")
                tts = self._tts
                if tts is None:
                    self._set_status("TTS unavailable. Session ended")
                    break
                tts_start = time.perf_counter()
                try:
                    audio = tts.generate(reply)
                except Exception as exc:
                    self._set_status(f"TTS error: {exc}")
                    break
                self._set_status("Playing...")
                self._set_animation_state("talk")
                try:
                    played = play_audio_bytes(audio)
                finally:
                    self._set_animation_state("idle")
                tts_ms = int((time.perf_counter() - tts_start) * 1000)
                if not played:
                    self._set_status(f"Playback failed ({tts_ms}ms). Session ended")
                    break
                turn_index += 1
                self._set_status(f"Turn {turn_index} done (TTS+play {tts_ms}ms). Speak now.")
        except Exception as exc:
            self._set_status(f"Error: {exc}")
        finally:
            self._set_animation_state("idle")
            if listener_suspended and self._mic_listener is not None:
                self._mic_listener.resume()
                self._set_status("Session ended. Listening")
            time.sleep(0.2)
            self._conversation_lock.release()

    def _record_miss(self, miss_count: int, max_misses: int) -> bool:
        if miss_count >= max_misses:
            self._set_status(f"No valid input ({miss_count}/{max_misses}), session ended")
            return True
        self._set_status(f"No valid input ({miss_count}/{max_misses})")
        return False

    def _set_status(self, text: str) -> None:
        if text == self._last_status:
            return
        self._last_status = text

        def apply_status() -> bool:
            if self._window is not None:
                self._window.set_status_text(text)
            print(f"[status] {text}", flush=True)
            return False

        GLib.idle_add(apply_status)

    def _set_animation_state(self, state: Literal["idle", "talk"]) -> None:
        def apply_state() -> bool:
            if self._window is not None:
                self._window.set_animation_state(state)
            return False

        GLib.idle_add(apply_state)

    @staticmethod
    def _pcm_stats(pcm_bytes: bytes) -> tuple[int, float]:
        if not pcm_bytes:
            return (0, 0.0)
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return (0, 0.0)
        duration_ms = int(samples.size / 16.0)
        rms = float(np.sqrt(np.mean(samples * samples)))
        return (duration_ms, rms)


def main() -> None:
    app = VoicePetApp()
    app.run()


if __name__ == "__main__":
    main()
