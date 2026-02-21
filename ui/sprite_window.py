from __future__ import annotations

import os
from typing import Literal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk, GdkPixbuf, Pango


class SpriteWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        app: Gtk.Application,
        image_path: str,
        frame_width: int,
        frame_height: int,
        frame_count: int,
        fps: int,
        scale: float,
        talk_image_path: str | None = None,
    ) -> None:
        super().__init__(application=app)
        self._debug_drag = os.getenv("VOICEPI_DEBUG_DRAG", "").strip() == "1"
        debug_ui = os.getenv("VOICEPI_DEBUG_UI", "").strip() == "1"
        force_decorated = os.getenv("VOICEPI_FORCE_DECORATED", "").strip() == "1"
        self.set_decorated(force_decorated or debug_ui)
        self.set_resizable(debug_ui is True)
        self.set_title("VoicePet")

        force_opaque = os.getenv("VOICEPI_FORCE_OPAQUE", "").strip() == "1"
        if not force_opaque:
            self._install_transparent_style()

        self._frame_width = frame_width
        self._frame_height = frame_height
        self._frame_count = frame_count
        self._fps = max(1, fps)
        self._scale = scale
        self._current_frame = 0
        self._animation_state: Literal["idle", "talk"] = "idle"

        self._idle_frames = self._load_frames(image_path)
        self._talk_frames = self._load_frames(talk_image_path)
        if talk_image_path and not self._talk_frames:
            print(
                "[sprite] talk animation unavailable, fallback to idle",
                flush=True,
            )
        self._active_frames = self._idle_frames

        self._drawing = Gtk.DrawingArea()
        self._drawing.set_content_width(int(frame_width * scale))
        self._drawing.set_content_height(int(frame_height * scale))
        self._drawing.set_size_request(int(frame_width * scale), int(frame_height * scale))
        self._drawing.set_draw_func(self._on_draw)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_wrap(False)
        self._status_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._status_label.set_xalign(0.5)
        self._status_label.set_valign(Gtk.Align.END)
        self._status_label.set_margin_bottom(4)
        self._status_label.add_css_class("voicepi-status-label")

        overlay = Gtk.Overlay()
        overlay.set_child(self._drawing)
        overlay.add_overlay(self._status_label)

        self.set_child(overlay)

        self._install_drag()
        self._install_debug_style()

        self.set_default_size(
            int(frame_width * scale), int(frame_height * scale)
        )
        self.set_size_request(int(frame_width * scale), int(frame_height * scale))
        if debug_ui:
            self.set_default_size(400, 400)
            if hasattr(self, "set_keep_above"):
                try:
                    self.set_keep_above(True)
                except Exception:
                    pass

        GLib.timeout_add(int(1000 / self._fps), self._on_tick)

    def _load_frames(self, image_path: str | None) -> list[GdkPixbuf.Pixbuf]:
        if not image_path:
            return []

        try:
            sheet = GdkPixbuf.Pixbuf.new_from_file(image_path)
        except Exception as exc:
            print(f"[sprite] failed to load '{image_path}': {exc}", flush=True)
            return []
        if sheet is None:
            return []

        frames: list[GdkPixbuf.Pixbuf] = []
        cols = max(1, sheet.get_width() // self._frame_width)
        for idx in range(self._frame_count):
            row = idx // cols
            col = idx % cols
            x = col * self._frame_width
            y = row * self._frame_height
            if x + self._frame_width > sheet.get_width():
                break
            if y + self._frame_height > sheet.get_height():
                break
            frame = sheet.new_subpixbuf(x, y, self._frame_width, self._frame_height)
            frames.append(frame)
        return frames

    def _on_tick(self) -> bool:
        if self._active_frames:
            self._current_frame = (self._current_frame + 1) % len(self._active_frames)
            self._drawing.queue_draw()
        return True

    def _on_draw(self, area, cr, width, height):
        if not self._active_frames:
            cr.set_source_rgba(1, 0, 0, 0.4)
            cr.paint()
            return
        frame = self._active_frames[self._current_frame]
        cr.save()
        cr.scale(self._scale, self._scale)
        Gdk.cairo_set_source_pixbuf(cr, frame, 0, 0)
        cr.paint()
        cr.restore()

    def set_animation_state(self, state: Literal["idle", "talk"]) -> None:
        if state not in ("idle", "talk"):
            state = "idle"
        if self._animation_state == state:
            return

        if state == "talk" and self._talk_frames:
            self._active_frames = self._talk_frames
        else:
            self._active_frames = self._idle_frames
        self._animation_state = state
        self._current_frame = 0
        self._drawing.queue_draw()

    def _install_drag(self) -> None:
        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_press_move)
        self.add_controller(click)

    def _install_debug_style(self) -> None:
        if os.getenv("VOICEPI_DEBUG_UI", "").strip() != "1":
            return
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            window {
                background-color: rgba(255, 255, 255, 0.65);
                border: 2px solid rgba(255, 0, 0, 0.8);
            }
            """
        )
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _install_transparent_style(self) -> None:
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            window {
                background-color: rgba(0, 0, 0, 0.0);
            }
            label.voicepi-status-label {
                color: #ffffff;
                background-color: rgba(0, 0, 0, 0.65);
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
            }
            """
        )
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _on_press_move(self, gesture, n_press, x, y):
        surface = self.get_surface()
        if surface is None:
            self._drag_debug("no surface")
            return
        if not hasattr(surface, "begin_move"):
            self._drag_debug("surface has no begin_move")
            return

        device = gesture.get_current_event_device()
        if device is None:
            self._drag_debug("no event device")
            return

        button = gesture.get_current_button()
        timestamp = gesture.get_current_event_time()
        if timestamp <= 0:
            timestamp = Gtk.get_current_event_time()

        try:
            surface.begin_move(device, button, float(x), float(y), timestamp)  # type: ignore[attr-defined]
            self._drag_debug(f"begin_move ok button={button} x={x:.1f} y={y:.1f} ts={timestamp}")
        except Exception as exc:
            self._drag_debug(f"begin_move failed: {exc}")
            return

    def _drag_debug(self, msg: str) -> None:
        if self._debug_drag:
            print(f"[drag] {msg}", flush=True)

    def set_status_text(self, text: str) -> None:
        self._status_label.set_text(text)
