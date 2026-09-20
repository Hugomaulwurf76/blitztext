"""
Clipboard + auto-paste.

Windows-Strategie: Das Blitztext-Fenster nimmt keinen Fokus (WindowDoesNotAcceptFocus),
daher bleibt das Zielfenster fokussiert. Zusaetzlich wird per AttachThreadInput die
Fokus-Sperre umgangen und Ctrl+V via keybd_event (echte Eingabe-Events) gesendet.
"""

import platform
import subprocess
import time
import ctypes

from PyQt6.QtWidgets import QApplication


def copy_to_clipboard(text: str) -> None:
    cb = QApplication.clipboard()
    if cb:
        cb.setText(text)


# ── Fokus-Speicher ────────────────────────────────────────────────────────────

_saved_hwnd = None


def save_focus() -> None:
    """Vor dem Oeffnen des Blitztext-Fensters aufrufen — speichert aktives Fenster."""
    global _saved_hwnd
    system = platform.system()
    if system == "Windows":
        try:
            import win32gui
            _saved_hwnd = win32gui.GetForegroundWindow()
        except ImportError:
            _saved_hwnd = None
    elif system == "Linux":
        # Aktive X11-Fenster-ID merken (fuer xdotool windowactivate)
        try:
            import os
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=2,
            )
            win_id = result.stdout.strip()
            if win_id:
                os.environ["_BLITZTEXT_PREV_WIN"] = win_id
        except Exception:
            pass


def paste_to_focused_window(text: str) -> bool:
    copy_to_clipboard(text)
    system = platform.system()
    try:
        if system == "Windows":
            return _paste_windows()
        elif system == "Linux":
            return _paste_linux()
        return False
    except Exception:
        return False


# ── Windows: AttachThreadInput + keybd_event ──────────────────────────────────

def _paste_windows() -> bool:
    user32 = ctypes.windll.user32

    # Fokus wurde durch hide() des Blitztext-Fensters bereits ans Zielfenster
    # zurueckgegeben. Nur noch Ctrl+V als echte Eingabe-Events senden.
    try:
        VK_CONTROL = 0x11
        VK_V       = 0x56
        KEYEVENTF_KEYUP = 0x0002

        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        pass

    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "v")
        return True
    except ImportError:
        return False


# ── Linux ─────────────────────────────────────────────────────────────────────

def _paste_linux() -> bool:
    """
    Fallback-Kette fuer Linux:
      - Unter X11: xdotool (klassisch)
      - Unter Wayland: wtype (wlroots/KDE/Sway/Hyprland) -> ydotool (GNOME)
    """
    import os
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    is_wayland = (session_type == "wayland")

    if is_wayland:
        # 1. wtype — funktioniert auf KDE, Sway, Hyprland und allen wlroots-basierten
        if _try_run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"]):
            return True
        # 2. wtype mit anderer Syntax (aeltere Versionen)
        if _try_run(["wtype", "-M", "ctrl", "-P", "v", "-p", "v", "-m", "ctrl"]):
            return True
        # 3. ydotool — GNOME Wayland Fallback
        if _try_run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]):
            return True
        # 4. xdotool als letzter Versuch (klappt unter XWayland fuer X11-Apps)
        return _paste_via_xdotool()
    else:
        # X11 — primaer xdotool
        if _paste_via_xdotool():
            return True
        # Fallback wtype falls vorhanden
        return _try_run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"])


def _paste_via_xdotool() -> bool:
    try:
        import os
        win_id = os.environ.get("_BLITZTEXT_PREV_WIN")
        if win_id:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", win_id],
                capture_output=True, timeout=3,
            )
            time.sleep(0.1)
        result = subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
            capture_output=True, timeout=3,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _try_run(cmd: list) -> bool:
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=3)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
