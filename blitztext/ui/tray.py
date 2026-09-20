"""
System tray icon + menu.
This is the root of the UI — everything else is opened from here.
"""

import asyncio
import sys
import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu,
)
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject

from ..services.settings import load_settings, save_settings, AppSettings
from ..services.paste import save_focus
from ..workflow import WorkflowKind, WorkflowRunner, Phase
from .workflow_window import WorkflowWindow
from .settings_window import SettingsWindow


# ── Async bridge: run asyncio in a background thread ─────────────────────────

class AsyncRunner(QObject):
    """Runs an asyncio event loop in a daemon thread so Qt workflows can await."""

    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self.loop)


# ── Tray icon (generated programmatically — no image file needed) ─────────────

def _make_icon(recording: bool = False) -> QIcon:
    """
    Tray-Icon: stilisiertes Mikrofon mit gelbem Blitz davor.
    Bei Aufnahme wechselt die Mikro-Farbe zu Rot.
    """
    from PyQt6.QtGui import QPen, QPainterPath

    size = 64
    pix  = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Kraeftiges Blau auf beiden Themes gut sichtbar; Aufnahme = Rot
    mic_color = QColor("#e74c3c") if recording else QColor("#3498db")
    bolt_color = QColor("#f1c40f")
    bolt_outline = QColor("#e67e22")

    # ── Mikrofon-Kapsel ────────────────────────────────────────────────────
    cx = size // 2
    cap_w, cap_h = 22, 32
    cap_x, cap_y = cx - cap_w // 2, 8
    painter.setBrush(mic_color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(cap_x, cap_y, cap_w, cap_h, 11, 11)

    # ── Buegel ─────────────────────────────────────────────────────────────
    pen = QPen(mic_color, 4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    arc_x, arc_y, arc_w, arc_h = cx - 18, 24, 36, 28
    painter.drawArc(arc_x, arc_y, arc_w, arc_h, 0, -180 * 16)

    # ── Staender ───────────────────────────────────────────────────────────
    painter.drawLine(cx, 38, cx, 52)

    # ── Fuss ───────────────────────────────────────────────────────────────
    painter.drawLine(cx - 10, 56, cx + 10, 56)

    # ── Blitz davor ────────────────────────────────────────────────────────
    path = QPainterPath()
    bx = cx + 4
    path.moveTo(bx + 0, 6)
    path.lineTo(bx - 7, 28)
    path.lineTo(bx - 1, 28)
    path.lineTo(bx - 6, 50)
    path.lineTo(bx + 7, 22)
    path.lineTo(bx + 1, 22)
    path.closeSubpath()

    painter.setBrush(bolt_color)
    pen = QPen(bolt_outline, 1.5)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    painter.setPen(pen)
    painter.drawPath(path)

    painter.end()
    return QIcon(pix)


# ── Workflow metadata ─────────────────────────────────────────────────────────

WORKFLOWS = [
    {
        "kind":     WorkflowKind.TRANSCRIPTION,
        "label":    "Blitztext",
        "subtitle": "Sprache rein. Text raus.",
        "icon":     "🎙",
        "color":    "#4a90d9",
    },
    {
        "kind":     WorkflowKind.TEXT_IMPROVE,
        "label":    "Blitztext+",
        "subtitle": "Geschrieben sprechen.",
        "icon":     "✨",
        "color":    "#9b59b6",
    },
    {
        "kind":     WorkflowKind.DAMPF_ABLASSEN,
        "label":    "Blitztext $%&!",
        "subtitle": "Frust rein. Entspannt raus.",
        "icon":     "🔥",
        "color":    "#e67e22",
    },
    {
        "kind":     WorkflowKind.EMOJI_TEXT,
        "label":    "Blitztext :)",
        "subtitle": "Text rein. Emojis dazu.",
        "icon":     "😊",
        "color":    "#27ae60",
    },
]


# ── Main tray app ─────────────────────────────────────────────────────────────

class BlitztextTrayApp(QSystemTrayIcon):
    # Qt signals for thread-safe UI updates
    _phase_signal = pyqtSignal(object, str, str)   # (kind, phase_name, message)
    # Hotkey signals (feuern aus pynput-Thread, landen im Qt-Hauptthread)
    _hk_start_signal = pyqtSignal(object)   # (kind) — Aufnahme starten
    _hk_stop_signal  = pyqtSignal(object)   # (kind) — Aufnahme stoppen

    def __init__(self, app: QApplication):
        super().__init__(_make_icon(), app)
        self.app = app
        self.settings: AppSettings = load_settings()
        self._async = AsyncRunner()

        self._workflow_windows: dict = {}
        self._active_runner: Optional[WorkflowRunner] = None
        self._hotkey_service = None

        self.setToolTip("Blitztext")
        self._build_menu()
        self._phase_signal.connect(self._on_phase_update)
        self._hk_start_signal.connect(self._hotkey_start)
        self._hk_stop_signal.connect(self._hotkey_stop)

        self._setup_hotkeys()

        # Show notification on first run
        if not self.settings.has_seen_onboarding:
            self.showMessage(
                "Blitztext bereit",
                "Klicke auf das Tray-Icon oder nutze die Hotkeys.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            self.settings.has_seen_onboarding = True
            save_settings(self.settings)

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        menu = QMenu()

        for wf in WORKFLOWS:
            action = QAction(f"{wf['icon']}  {wf['label']}  —  {wf['subtitle']}", self.app)
            action.setData(wf["kind"])
            action.triggered.connect(lambda checked, w=wf: self._open_workflow(w))
            menu.addAction(action)

        menu.addSeparator()

        settings_action = QAction("⚙  Einstellungen", self.app)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("Beenden", self.app)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        # Linksklick-Popup nur unter Windows — auf Linux/Wayland verbietet das
        # Compositor-Protokoll grabbing popups ohne Transient Parent. Dort
        # nutzt der User Rechtsklick (kommt vom System als Context-Event).
        import platform
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if platform.system() == "Windows":
                self.contextMenu().popup(self.geometry().center())

    # ── Hotkeys ─────────────────────────────────────────────────────────────────

    def _setup_hotkeys(self) -> None:
        from ..services.hotkeys import HotkeyService
        if self._hotkey_service:
            self._hotkey_service.stop()
            self._hotkey_service = None

        hk = self.settings.hotkeys
        if not hk.enabled:
            return

        svc = HotkeyService()
        if not svc.is_available():
            return

        # (combo, mode, kind)
        mapping = [
            (hk.transcription,    hk.transcription_mode,    WorkflowKind.TRANSCRIPTION),
            (hk.text_improvement, hk.text_improvement_mode, WorkflowKind.TEXT_IMPROVE),
            (hk.dampf_ablassen,   hk.dampf_ablassen_mode,   WorkflowKind.DAMPF_ABLASSEN),
            (hk.emoji_text,       hk.emoji_text_mode,       WorkflowKind.EMOJI_TEXT),
        ]

        for combo, mode, kind in mapping:
            if not combo:
                continue
            if mode == "hold":
                svc.register(
                    combo, "hold",
                    on_press=lambda k=kind: self._hk_start_signal.emit(k),
                    on_release=lambda k=kind: self._hk_stop_signal.emit(k),
                )
            else:  # toggle
                svc.register(
                    combo, "toggle",
                    on_toggle=lambda state, k=kind: (
                        self._hk_start_signal.emit(k) if state
                        else self._hk_stop_signal.emit(k)
                    ),
                )

        svc.start()
        self._hotkey_service = svc

    def _meta_for(self, kind) -> dict:
        for wf in WORKFLOWS:
            if wf["kind"] == kind:
                return wf
        return WORKFLOWS[0]

    def _hotkey_start(self, kind) -> None:
        """Hotkey gedrueckt — Fenster oeffnen (falls noetig) + Aufnahme starten."""
        wf = self._meta_for(kind)
        win = self._workflow_windows.get(kind)
        if win is None or not win.isVisible():
            self._open_workflow(wf, auto_record=True)
        else:
            win.start_recording_external()

    def _hotkey_stop(self, kind) -> None:
        """Hotkey losgelassen / Toggle aus — Aufnahme stoppen + verarbeiten."""
        win = self._workflow_windows.get(kind)
        if win:
            win.stop_recording_external()

    # ── Open workflow window ──────────────────────────────────────────────────

    def _open_workflow(self, wf: dict, auto_record: bool = False) -> None:
        kind = wf["kind"]

        # Reload settings fresh before opening
        self.settings = load_settings()

        runner = WorkflowRunner(
            kind=kind,
            settings=self.settings,
            on_phase=lambda phase, msg: self._phase_signal.emit(kind, phase.value, msg),
            on_output=None,  # window handles output display
        )
        # Inject async loop
        runner._async_runner = self._async

        win = WorkflowWindow(
            kind=kind,
            meta=wf,
            runner=runner,
            parent=None,
        )
        save_focus()
        self._workflow_windows[kind] = win
        win.show()
        win.raise_()
        win.activateWindow()

        if auto_record:
            # kurz warten bis Fenster da ist, dann Aufnahme starten
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, win.start_recording_external)

    def _on_phase_update(self, kind, phase_name: str, message: str) -> None:
        win = self._workflow_windows.get(kind)
        if win:
            try:
                phase = Phase(phase_name)
                win.update_phase(phase, message)
            except ValueError:
                pass
        # Update tray icon
        recording = phase_name == Phase.RECORDING.value
        self.setIcon(_make_icon(recording))

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        win = SettingsWindow(self.settings, parent=None)
        win.settings_saved.connect(self._on_settings_saved)
        win.show()
        win.raise_()
        win.activateWindow()

    def _on_settings_saved(self, new_settings: AppSettings) -> None:
        self.settings = new_settings
        save_settings(new_settings)
        # Hotkeys mit neuen Einstellungen neu aufsetzen
        self._setup_hotkeys()
