"""
Workflow window — the popup that appears when a workflow is triggered.
Shows recording state, waveform animation, status text and result.
"""

import asyncio
import threading
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame, QSizePolicy, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPalette

from ..workflow import WorkflowKind, WorkflowRunner, Phase


# ── Waveform widget ───────────────────────────────────────────────────────────

class WaveformWidget(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color  = QColor(color)
        self._level  = 0.0
        self._active = False
        self._bars   = [0.0] * 20
        self._timer  = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedHeight(40)
        self.setMinimumWidth(200)

    def set_active(self, active: bool, level: float = 0.0) -> None:
        self._active = active
        self._level  = level
        if active and not self._timer.isActive():
            self._timer.start(50)
        elif not active:
            self._timer.stop()
            self._bars = [0.0] * len(self._bars)
            self.update()

    def _tick(self) -> None:
        import random
        self._bars.pop(0)
        if self._active:
            base = max(0.05, self._level)
            self._bars.append(base * (0.5 + random.random() * 0.5))
        else:
            self._bars.append(0.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        n = len(self._bars)
        bar_w = max(2, (w - n * 2) // n)
        spacing = 2

        for i, level in enumerate(self._bars):
            bar_h = max(3, int(level * h * 0.9))
            x = i * (bar_w + spacing)
            y = (h - bar_h) // 2
            color = QColor(self._color)
            color.setAlphaF(0.3 + level * 0.7)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, bar_w, bar_h, 2, 2)

        painter.end()


# ── Workflow window ───────────────────────────────────────────────────────────

class WorkflowWindow(QWidget):
    def __init__(self, kind: WorkflowKind, meta: dict, runner: WorkflowRunner, parent=None):
        super().__init__(parent)
        self.kind   = kind
        self.meta   = meta
        self.runner = runner
        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._poll_level)

        self._setup_ui()
        self._setup_window()

    def _setup_window(self) -> None:
        self.setWindowTitle(self.meta["label"])
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setFixedWidth(400)
        self.setMinimumHeight(200)

    def _setup_ui(self) -> None:
        color = self.meta["color"]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        icon_label = QLabel(self.meta["icon"])
        icon_label.setFont(QFont("Segoe UI Emoji", 22))
        header.addWidget(icon_label)

        title_layout = QVBoxLayout()
        title = QLabel(self.meta["label"])
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        subtitle = QLabel(self.meta["subtitle"])
        subtitle.setStyleSheet("color: #888; font-size: 11px;")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header.addLayout(title_layout)
        header.addStretch()
        layout.addLayout(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {color}; background: {color}; max-height: 2px;")
        layout.addWidget(sep)

        # Waveform
        self.waveform = WaveformWidget(color)
        layout.addWidget(self.waveform)

        # Status label
        self.status_label = QLabel("Bereit")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 13px; color: #555;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Result text area (hidden initially)
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setMaximumHeight(150)
        self.result_area.setVisible(False)
        self.result_area.setStyleSheet(
            "background: #f8f9fa; border: 1px solid #e0e0e0; "
            "border-radius: 6px; padding: 8px; font-size: 13px;"
        )
        layout.addWidget(self.result_area)

        # Buttons
        btn_layout = QHBoxLayout()

        self.record_btn = QPushButton("🎙  Aufnahme starten")
        self.record_btn.setFixedHeight(40)
        self.record_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border-radius: 8px; "
            f"font-size: 13px; font-weight: bold; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {color}; opacity: 0.9; }}"
            f"QPushButton:pressed {{ opacity: 0.8; }}"
        )
        self.record_btn.clicked.connect(self._toggle_recording)
        btn_layout.addWidget(self.record_btn)

        self.copy_btn = QPushButton("📋  Kopieren")
        self.copy_btn.setFixedHeight(40)
        self.copy_btn.setVisible(False)
        self.copy_btn.setStyleSheet(
            "QPushButton { background: #f0f0f0; color: #333; border-radius: 8px; "
            "font-size: 13px; padding: 0 16px; }"
            "QPushButton:hover { background: #e0e0e0; }"
        )
        self.copy_btn.clicked.connect(self._copy_result)
        btn_layout.addWidget(self.copy_btn)

        layout.addLayout(btn_layout)

        # Cancel / close
        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.setFlat(True)
        self.cancel_btn.setStyleSheet("color: #888; font-size: 12px;")
        self.cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self.cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.adjustSize()

    # ── Recording toggle ──────────────────────────────────────────────────────

    def _toggle_recording(self) -> None:
        phase = self.runner.phase
        if phase == Phase.IDLE or phase == Phase.DONE or phase == Phase.ERROR:
            self.runner.reset()
            self._start_recording()
        elif phase == Phase.RECORDING:
            self._stop_recording()

    def _start_recording(self) -> None:
        # Patch runner to use our async loop
        original_run_async = self.runner._run_async

        def patched_run_async(audio_path, duration):
            from ..ui.tray import AsyncRunner
            # Try to get the async runner from parent tray
            _run_in_thread(self.runner._process(audio_path, duration))

        def _run_in_thread(coro):
            def target():
                asyncio.run(coro)
            t = threading.Thread(target=target, daemon=True)
            t.start()

        self.runner._run_async = patched_run_async
        self.runner.start_recording()
        self._level_timer.start(50)

    def _stop_recording(self) -> None:
        self._level_timer.stop()
        self.waveform.set_active(False)
        self.runner.stop_recording()

    # ── Externe Steuerung (von Hotkeys) ────────────────────────────────────────

    def start_recording_external(self) -> None:
        """Von Hotkey aufgerufen — startet Aufnahme falls nicht schon laufend."""
        phase = self.runner.phase
        if phase in (Phase.IDLE, Phase.DONE, Phase.ERROR):
            self.runner.reset()
            self._start_recording()

    def stop_recording_external(self) -> None:
        """Von Hotkey aufgerufen — stoppt Aufnahme falls laufend."""
        if self.runner.phase == Phase.RECORDING:
            self._stop_recording()

    def _poll_level(self) -> None:
        if self.runner.is_recording:
            self.waveform.set_active(True, self.runner.audio_level)

    # ── Phase updates (called from tray signal) ───────────────────────────────

    def update_phase(self, phase: Phase, message: str) -> None:
        self.status_label.setText(message)

        if phase == Phase.IDLE:
            self._set_idle()
        elif phase == Phase.RECORDING:
            self.record_btn.setText("⏹  Aufnahme stoppen")
            self.record_btn.setStyleSheet(
                "QPushButton { background: #e74c3c; color: white; border-radius: 8px; "
                "font-size: 13px; font-weight: bold; padding: 0 16px; }"
            )
            self.result_area.setVisible(False)
            self.copy_btn.setVisible(False)
        elif phase in (Phase.TRANSCRIBING, Phase.REWRITING):
            self.record_btn.setEnabled(False)
            self.record_btn.setText("⏳  Verarbeitung …")
        elif phase == Phase.DONE:
            self._set_done(message)
        elif phase == Phase.ERROR:
            self._set_error(message)

    def _set_idle(self) -> None:
        self.record_btn.setText("🎙  Aufnahme starten")
        self.record_btn.setEnabled(True)
        color = self.meta["color"]
        self.record_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border-radius: 8px; "
            f"font-size: 13px; font-weight: bold; padding: 0 16px; }}"
        )
        self.status_label.setText("Bereit")
        self.status_label.setStyleSheet("font-size: 13px; color: #555;")

    def _set_done(self, text: str) -> None:
        self.record_btn.setText("🎙  Neue Aufnahme")
        self.record_btn.setEnabled(True)
        color = self.meta["color"]
        self.record_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border-radius: 8px; "
            f"font-size: 13px; font-weight: bold; padding: 0 16px; }}"
        )
        self.result_area.setPlainText(text)
        self.result_area.setVisible(True)
        self.copy_btn.setVisible(True)
        self.adjustSize()

        # Clipboard + Auto-Paste im UI-Hauptthread (COM/Qt-sicher)
        from ..services import paste as paste_svc
        paste_svc.copy_to_clipboard(text)

        if self.runner.settings.auto_paste:
            self.status_label.setText("✅  Wird eingefügt …")
            self.status_label.setStyleSheet("font-size: 13px; color: #27ae60; font-weight: bold;")
            # Kurz warten, Fenster schließen, dann ins Zielfenster einfügen
            self._pending_paste_text = text
            QTimer.singleShot(150, self._do_paste)
        else:
            self.status_label.setText("✅  In Zwischenablage kopiert")
            self.status_label.setStyleSheet("font-size: 13px; color: #27ae60; font-weight: bold;")

    def _do_paste(self) -> None:
        from ..services import paste as paste_svc
        # Fenster verstecken, damit der Fokus ans vorherige Fenster zurueckfaellt
        self.hide()
        QApplication.processEvents()
        # Kurz warten bis Windows den Fokus zurueckgegeben hat, dann einfuegen
        QTimer.singleShot(180, self._do_paste_after_hide)

    def _do_paste_after_hide(self) -> None:
        from ..services import paste as paste_svc
        paste_svc.paste_to_focused_window(self._pending_paste_text)
        # Fenster bleibt versteckt — nach erfolgreichem Einfuegen komplett schliessen
        QTimer.singleShot(100, self.close)

    def _set_error(self, message: str) -> None:
        self.record_btn.setText("🎙  Erneut versuchen")
        self.record_btn.setEnabled(True)
        color = self.meta["color"]
        self.record_btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border-radius: 8px; "
            f"font-size: 13px; font-weight: bold; padding: 0 16px; }}"
        )
        self.status_label.setText(f"❌  {message}")
        self.status_label.setStyleSheet("font-size: 13px; color: #e74c3c;")

    def _copy_result(self) -> None:
        from PyQt6.QtWidgets import QApplication
        text = self.result_area.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.copy_btn.setText("✅  Kopiert!")
            QTimer.singleShot(2000, lambda: self.copy_btn.setText("📋  Kopieren"))

    def _cancel(self) -> None:
        self.runner.cancel()
        self._level_timer.stop()
        self.waveform.set_active(False)
        self.close()

    def closeEvent(self, event) -> None:
        self.runner.cancel()
        self._level_timer.stop()
        super().closeEvent(event)
