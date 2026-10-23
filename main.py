"""
Blitztext Cross-Platform
Speech-to-text app for Windows 11 and Linux Debian
MIT License — Fork of the concept from cmagnussen/blitztext-app (macOS)
"""

import sys
import os
import platform

# Ensure the package is importable when running from root
sys.path.insert(0, os.path.dirname(__file__))

import traceback

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from blitztext import __version__
from blitztext.services.settings import _config_path
from blitztext.ui.tray import BlitztextTrayApp


def _show_unhandled(exc_type, exc, tb) -> None:
    """Zeigt unbehandelte Fehler als Fenster und schreibt sie in error.log,
    statt dass das Programm ohne Meldung beendet wird."""
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(_config_path().parent / "error.log", "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass
    try:
        QMessageBox.critical(None, "Blitztext – Fehler", text)
    except Exception:
        pass


def _set_windows_app_id() -> None:
    """Setzt eine eigene AppUserModelID, damit Windows die App als Blitztext erkennt
    und nicht als python.exe / pythonw.exe in der Taskleiste anzeigt."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        myappid = "Blitztext.CrossPlatform.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass


def main():
    _set_windows_app_id()

    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    sys.excepthook = _show_unhandled

    app = QApplication(sys.argv)
    app.setApplicationName("Blitztext")
    app.setApplicationDisplayName("Blitztext")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Blitztext")
    app.setDesktopFileName("blitztext")
    # Keep running even if all windows are closed (tray app)
    app.setQuitOnLastWindowClosed(False)

    tray = BlitztextTrayApp(app)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
