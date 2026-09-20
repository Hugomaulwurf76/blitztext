"""
Globale Hotkeys via pynput — unterstuetzt Hold- und Toggle-Modus pro Workflow.

Hold:   Alle Tasten der Kombi gedrueckt  -> on_press  (Aufnahme start)
        Eine Taste der Kombi losgelassen -> on_release (Aufnahme stop + verarbeiten)
Toggle: Kombi einmal vollstaendig gedrueckt -> on_toggle (start/stop wechselnd)

Funktioniert auf Windows zuverlaessig. Auf Linux X11 ebenfalls; unter Wayland
eingeschraenkt (pynput-Limitierung).
"""

import threading
from typing import Callable, Optional

try:
    from pynput import keyboard as _kb
    PYNPUT_AVAILABLE = True
except Exception:
    PYNPUT_AVAILABLE = False


# ── Tastennamen -> pynput ─────────────────────────────────────────────────────

def _normalize(part: str) -> str:
    p = part.strip().lower()
    aliases = {
        "control": "ctrl",
        "option": "alt",
        "win": "cmd",
        "super": "cmd",
        "meta": "cmd",
        "return": "enter",
        "esc": "escape",
    }
    return aliases.get(p, p)


# Modifier-Mengen fuer Vergleich
_MODIFIER_KEYS = {
    "ctrl":  {_kb.Key.ctrl, _kb.Key.ctrl_l, _kb.Key.ctrl_r} if PYNPUT_AVAILABLE else set(),
    "shift": {_kb.Key.shift, _kb.Key.shift_l, _kb.Key.shift_r} if PYNPUT_AVAILABLE else set(),
    "alt":   {_kb.Key.alt, _kb.Key.alt_l, _kb.Key.alt_r, getattr(_kb.Key, "alt_gr", None)} if PYNPUT_AVAILABLE else set(),
    "cmd":   {_kb.Key.cmd, getattr(_kb.Key, "cmd_l", None), getattr(_kb.Key, "cmd_r", None)} if PYNPUT_AVAILABLE else set(),
}


def _parse_combo(combo: str):
    """Zerlegt 'ctrl+shift+r' in (set_of_modifier_names, normal_key_char)."""
    mods = set()
    key_char = None
    for raw in combo.split("+"):
        p = _normalize(raw)
        if p in ("ctrl", "shift", "alt", "cmd"):
            mods.add(p)
        else:
            key_char = p
    return mods, key_char


# ── Einzelner Hotkey-Zustand ──────────────────────────────────────────────────

class _HotkeyBinding:
    def __init__(self, combo, mode, on_press, on_release, on_toggle):
        self.mods, self.key_char = _parse_combo(combo)
        self.mode = mode  # "hold" | "toggle"
        self.on_press = on_press
        self.on_release = on_release
        self.on_toggle = on_toggle
        self.active = False        # ist die Kombi gerade vollstaendig gedrueckt?
        self.toggle_state = False  # fuer toggle: laeuft gerade eine Aufnahme?


# ── Service ───────────────────────────────────────────────────────────────────

class HotkeyService:
    def __init__(self):
        self._listener: Optional[object] = None
        self._bindings: list[_HotkeyBinding] = []
        self._pressed_mods = set()   # aktuell gedrueckte Modifier-Namen
        self._pressed_keys = set()   # aktuell gedrueckte normale Tasten (chars)
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return PYNPUT_AVAILABLE

    def register(self, combo: str, mode: str,
                 on_press: Optional[Callable] = None,
                 on_release: Optional[Callable] = None,
                 on_toggle: Optional[Callable] = None) -> None:
        if not PYNPUT_AVAILABLE or not combo:
            return
        self._bindings.append(
            _HotkeyBinding(combo, mode, on_press, on_release, on_toggle)
        )

    def start(self) -> None:
        if not PYNPUT_AVAILABLE or self._listener or not self._bindings:
            return
        self._listener = _kb.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    # ── interne Tasten-Verarbeitung ───────────────────────────────────────────

    def _mod_name(self, key) -> Optional[str]:
        for name, keyset in _MODIFIER_KEYS.items():
            if key in keyset:
                return name
        return None

    def _key_char(self, key) -> Optional[str]:
        # normale Taste -> Zeichen
        try:
            if hasattr(key, "char") and key.char:
                c = key.char
                # Control-Character (z.B. Ctrl+R -> '\x12') zurueck zum Buchstaben
                if len(c) == 1 and 1 <= ord(c) <= 26:
                    return chr(ord(c) + ord('a') - 1)
                return c.lower()
        except Exception:
            pass
        # Virtual-Key-Code (z.B. Ctrl+Alt+B unter Windows -> KeyCode.from_vk(66))
        try:
            vk = getattr(key, "vk", None)
            if vk is not None:
                # A-Z = 65-90
                if 65 <= vk <= 90:
                    return chr(vk + 32)  # -> 'a'..'z'
                # 0-9 = 48-57
                if 48 <= vk <= 57:
                    return chr(vk)
                # F1-F24 = 112-135
                if 112 <= vk <= 135:
                    return f"f{vk - 111}"
                # Leertaste
                if vk == 32:
                    return "space"
        except Exception:
            pass
        # Funktionstasten etc.
        if hasattr(key, "name"):
            return key.name.lower()
        return None

    def _on_key_press(self, key):
        with self._lock:
            mod = self._mod_name(key)
            if mod:
                self._pressed_mods.add(mod)
            else:
                ch = self._key_char(key)
                if ch:
                    self._pressed_keys.add(ch)
            self._evaluate()

    def _on_key_release(self, key):
        with self._lock:
            mod = self._mod_name(key)
            ch = self._key_char(key) if not mod else None

            # Vor dem Entfernen pruefen: war eine Hold-Kombi aktiv und wird jetzt gebrochen?
            for b in self._bindings:
                if b.mode == "hold" and b.active:
                    breaking = (mod in b.mods) or (ch is not None and ch == b.key_char)
                    if breaking:
                        b.active = False
                        if b.on_release:
                            self._fire(b.on_release)

            if mod and mod in self._pressed_mods:
                self._pressed_mods.discard(mod)
            if ch and ch in self._pressed_keys:
                self._pressed_keys.discard(ch)

    def _evaluate(self):
        """Pruefen ob eine Kombi gerade vollstaendig gedrueckt ist."""
        for b in self._bindings:
            combo_down = b.mods.issubset(self._pressed_mods) and (
                b.key_char in self._pressed_keys
            )
            if combo_down and not b.active:
                b.active = True
                if b.mode == "hold":
                    if b.on_press:
                        self._fire(b.on_press)
                elif b.mode == "toggle":
                    b.toggle_state = not b.toggle_state
                    if b.on_toggle:
                        self._fire(b.on_toggle, b.toggle_state)
            elif not combo_down and b.active and b.mode == "toggle":
                # Toggle: active zuruecksetzen sobald Kombi losgelassen,
                # damit erneutes Druecken wieder ausloest
                b.active = False

    def _fire(self, callback, *args):
        # Callback nicht im Listener-Thread blockieren lassen
        try:
            callback(*args)
        except Exception as e:
            print(f"[HotkeyService] callback error: {e}")
