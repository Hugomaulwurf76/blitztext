#!/usr/bin/env bash
# Blitztext Cross-Platform — Linux Installer
# Getestet auf Debian 12 / Ubuntu 22.04+

set -e

echo "=== Blitztext - Linux Installation ==="
echo

# ── Schritt 1: Python suchen (versionsunabhaengig, mindestens 3.10) ─────────
PYTHON_EXE=""

version_ok() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}

# 1) Standardbefehl "python3" pruefen (zeigt meist auf die aktuellste Version)
if command -v python3 >/dev/null 2>&1; then
    exe="$(command -v python3)"
    if version_ok "$exe"; then
        PYTHON_EXE="$exe"
    fi
fi

# 2) Fallback: explizite Versionsnummern absuchen, neueste zuerst
if [ -z "$PYTHON_EXE" ]; then
    for v in 20 19 18 17 16 15 14 13 12 11 10; do
        candidate="python3.$v"
        if command -v "$candidate" >/dev/null 2>&1; then
            exe="$(command -v "$candidate")"
            if version_ok "$exe"; then
                PYTHON_EXE="$exe"
                break
            fi
        fi
    done
fi

if [ -z "$PYTHON_EXE" ]; then
    echo "Kein Python 3.10 oder neuer gefunden."
    echo
    echo "Bitte Python installieren:"
    echo "  sudo apt-get install python3 python3-pip python3-venv"
    echo
    echo "Danach diese Datei erneut ausführen."
    exit 1
fi

echo "Gefundenes Python: $PYTHON_EXE"
"$PYTHON_EXE" --version
echo

# ── Schritt 2: System-Pakete (portaudio, xdotool, wtype, pip, venv) ──────────
echo "[1/3] Installiere System-Pakete..."
NEEDED_PKGS=""
for pkg in portaudio19-dev xdotool wtype python3-pip python3-venv python3-tk; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        NEEDED_PKGS="$NEEDED_PKGS $pkg"
    fi
done

if [ -n "$NEEDED_PKGS" ]; then
    echo "  Pakete:$NEEDED_PKGS"
    sudo apt-get update -q
    sudo apt-get install -y $NEEDED_PKGS
else
    echo "  Alle System-Pakete bereits vorhanden."
fi
echo

# ── Schritt 3: venv anlegen für saubere Installation ─────────────────────────
VENV_DIR="$(cd "$(dirname "$0")" && pwd)/.venv"
echo "[2/3] Erstelle Python venv: $VENV_DIR"
if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_EXE" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"

# ── Schritt 4: Python-Pakete installieren ────────────────────────────────────
echo "  Installiere Python-Pakete..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install PyQt6 sounddevice soundfile numpy httpx keyring pynput

echo

# ── Schritt 5: start.sh erstellen ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "[3/3] Erstelle start.sh..."

cat > "$SCRIPT_DIR/start.sh" << EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$SCRIPT_DIR/main.py"
EOF
chmod +x "$SCRIPT_DIR/start.sh"

echo
echo "=== Installation abgeschlossen ==="
echo
echo "Starten: ./start.sh"
echo
echo "Optional (lokale Transkription ohne API-Key):"
echo "  $VENV_PYTHON -m pip install faster-whisper"
echo