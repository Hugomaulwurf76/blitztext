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

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from blitztext import __version__
from blitztext.ui.tray import BlitztextTrayApp


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
