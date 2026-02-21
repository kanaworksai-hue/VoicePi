from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gtk, Pango


class StatusWindow:
    def __init__(self, app: Gtk.Application) -> None:
        self._app = app
        self._anchor: Gtk.Widget | None = None

        self._label = Gtk.Label(label="Ready")
        self._label.set_wrap(False)
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._label.set_xalign(0.0)
        self._label.set_margin_start(10)
        self._label.set_margin_end(10)
        self._label.set_margin_top(6)
        self._label.set_margin_bottom(6)
        self._label.add_css_class("voicepi-status-label")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self._label)

        self._popover = Gtk.Popover()
        self._popover.set_autohide(False)
        self._popover.set_has_arrow(False)
        self._popover.set_position(Gtk.PositionType.TOP)
        if hasattr(self._popover, "set_offset"):
            try:
                self._popover.set_offset(0, -8)
            except Exception:
                pass
        self._popover.set_child(box)
        self._popover.add_css_class("voicepi-status-popover")

        self._install_style()

    def _install_style(self) -> None:
        css = Gtk.CssProvider()
        css.load_from_data(
            b"""
            popover.voicepi-status-popover contents {
                background-color: rgba(0, 0, 0, 0.18);
                border-radius: 8px;
                border: 0;
                box-shadow: none;
            }
            label.voicepi-status-label {
                color: #ffffff;
                background-color: rgba(0, 0, 0, 0.72);
                border-radius: 8px;
                padding: 4px 8px;
            }
            """
        )
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def attach_to(self, anchor_widget: Gtk.Widget) -> None:
        self._anchor = anchor_widget
        self._popover.set_parent(anchor_widget)

    def present(self) -> None:
        if self._anchor is not None:
            self._popover.popup()

    def set_status_text(self, text: str) -> None:
        self._label.set_text(text)
        if self._anchor is not None:
            self._popover.popup()
