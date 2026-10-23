"""
Autostart fuer Blitztext.

Windows: Eintrag unter HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run (keine Adminrechte).
Linux:   Desktop-Datei ~/.config/autostart/blitztext.desktop (XDG-Standard).
Andere Systeme: keine Funktion.

Zieldatei: blitztext/services/autostart.py
"""

import os
import platform
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Blitztext"
DESKTOP_FILE = "blitztext.desktop"

_MAIN = Path(__file__).resolve().parents[2] / "main.py"


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


# ── Windows ──────────────────────────────────────────────────────────────────

def _windows_command() -> str:
    """Installierte .exe oder im Entwicklungsbetrieb pythonw.exe main.py."""
    if _is_frozen():
        return f'"{sys.executable}"'
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    interpreter = pyw if pyw.exists() else py
    return f'"{interpreter}" "{_MAIN}"'


def _win_is_enabled() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def _win_set_enabled(enabled: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _windows_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass


# ── Linux ────────────────────────────────────────────────────────────────────

def _desktop_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / DESKTOP_FILE


def _quote(arg: str) -> str:
    """Desktop-Entry-Exec: Argument in Anfuehrungszeichen, Sonderzeichen escapen."""
    for ch in ("\\", '"', "`", "$"):
        arg = arg.replace(ch, "\\" + ch)
    return f'"{arg}"'


def _linux_exec() -> str:
    if _is_frozen():
        return _quote(sys.executable)
    return f"{_quote(sys.executable)} {_quote(str(_MAIN))}"


def _linux_is_enabled() -> bool:
    return _desktop_path().exists()


def _linux_set_enabled(enabled: bool) -> None:
    path = _desktop_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Blitztext\n"
            f"Exec={_linux_exec()}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


# ── Öffentliche Funktionen ───────────────────────────────────────────────────

def is_enabled() -> bool:
    """True, wenn der Autostart-Eintrag existiert."""
    system = platform.system()
    if system == "Windows":
        return _win_is_enabled()
    if system == "Linux":
        return _linux_is_enabled()
    return False


def set_enabled(enabled: bool) -> None:
    """Setzt oder entfernt den Autostart-Eintrag. Fehler werden nach oben gereicht."""
    system = platform.system()
    if system == "Windows":
        _win_set_enabled(enabled)
    elif system == "Linux":
        _linux_set_enabled(enabled)
