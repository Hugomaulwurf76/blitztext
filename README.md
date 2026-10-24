# Blitztext Cross-Platform

**Speech-to-text desktop app for Windows 11 and Linux Debian.**

A Python/PyQt6 fork of the concept from [cmagnussen/blitztext-app](https://github.com/cmagnussen/blitztext-app) (macOS original, MIT license).

> Bring your own API key — no backend, no telemetry, no warranty.

---

## Was die App macht

| Workflow | Hotkey (Standard) | Beschreibung |
|---|---|---|
| 🎙 **Blitztext** | `Ctrl+Alt+W` | Sprache → Text (nur Transkription) |
| ✨ **Blitztext+** | `Ctrl+Alt+B` | Sprache → Transkription → Text verbessert |
| 🔥 **Blitztext $%&!** | `Ctrl+Alt+F` | Frustrierte Sprache → ruhige Nachricht |
| 😊 **Blitztext :)** | `Ctrl+Alt+J` | Sprache → Text mit passenden Emojis |

---

## Unterstützte Anbieter

### Transkription (STT)
| Anbieter | Was du brauchst |
|---|---|
| **Groq Whisper** *(Standard, kostenlos)* | Groq API Key |
| **OpenAI Whisper API** | OpenAI API Key |
| **AssemblyAI** | AssemblyAI API Key |
| **Lokal (faster-whisper)** | `pip install faster-whisper`, kein Key nötig |
| **Eigener Endpunkt** | OpenAI-kompatibler Endpunkt |

### LLM (Textverarbeitung)
| Anbieter | Was du brauchst |
|---|---|
| **Groq** *(Standard, kostenlos)* | Groq API Key |
| **OpenAI** | OpenAI API Key |
| **Claude (Anthropic)** | Anthropic API Key |
| **Ollama** (lokal, selbst gehostet) | Ollama läuft auf localhost:11434 |
| **Eigener Endpunkt** | OpenAI-kompatibler Endpunkt |

Jeden Workflow kannst du **unabhängig** konfigurieren — z.B. Blitztext mit Groq-Whisper, Blitztext+ mit lokalem Ollama.

> ⚠️ Bei Groq: Modellauswahl in den Einstellungen ist eine editierbare Vorschlagsliste. Groq deprecatet Modelle regelmäßig — falls ein Modell mit „404 does not exist" fehlschlägt, ein anderes aus der Liste wählen bzw. auf console.groq.com/docs/models nachsehen, welches aktuell auf deinem Tarif (Free/Developer vs. Enterprise) verfügbar ist.

---

## Installation

### Voraussetzungen
- Für das Setup unter Windows: nichts. Das Setup bringt alles mit.
- Für Entwicklung aus dem Quellcode: Python 3.10 oder neuer
- Auf Linux: das Install-Skript richtet `portaudio19-dev`, `xdotool`/`wtype` etc. automatisch ein (per `sudo apt-get`)

### Windows 11 (fertiges Setup)
1. `BlitztextSetup-1.0.6.exe` aus den Releases herunterladen und ausführen.
2. Windows fragt nach Administratorrechten. Die Installation erfolgt immer für alle Benutzer nach `C:\Program Files\Blitztext`.
3. Der Assistent legt einen Startmenü-Eintrag an, optional auch eine Desktop-Verknüpfung.
4. Autostart mit Windows: Einstellungen → Erweitert → „Mit Windows starten“.

### Windows 11 (aus dem Quellcode)
```cmd
git clone https://github.com/Hugomaulwurf76/blitztext.git
cd blitztext
install_windows.bat
start.bat
```

`install_windows.bat` installiert die Python-Pakete in das gefundene Python und erzeugt `start.bat`. Ist kein passendes Python vorhanden, verlinkt das Skript direkt zum Download.

### Linux (Debian/Ubuntu, fertiges Paket)
`blitztext_1.0.6_amd64.deb` aus den Releases herunterladen und installieren:
```bash
sudo apt install ./blitztext_1.0.6_amd64.deb
```
Danach im Anwendungsmenü „Blitztext“ starten. Deinstallation: `sudo apt remove blitztext`.

### Windows-Setup selbst bauen (Entwickler)
Im Ordner `BlitztextEXE`:
1. `build_exe.bat` ausführen. Es installiert die Build-Pakete, erzeugt `Blitztext.ico` aus dem Tray-Icon und baut `dist\Blitztext\Blitztext.exe` mit PyInstaller.
2. `Blitztext.iss` mit dem [Inno Setup Compiler](https://jrsoftware.org/isdl.php) öffnen und kompilieren. Das Ergebnis liegt in `output\BlitztextSetup-1.0.6.exe`.

### Linux (Debian/Ubuntu)
```bash
git clone https://github.com/Hugomaulwurf76/blitztext.git
cd blitztext
chmod +x install_linux.sh
./install_linux.sh
./start.sh
```

`install_linux.sh` erkennt automatisch ein passendes Python (≥3.10), legt ein eigenes `.venv` an, installiert alle System- und Python-Abhängigkeiten und erzeugt `start.sh`.

Autostart beim Anmelden: Einstellungen → Erweitert → „Beim Anmelden starten“. Das legt `~/.config/autostart/blitztext.desktop` an und entfernt die Datei wieder, wenn du die Option ausschaltest.

### Lokale Transkription (kein API Key)
```bash
pip install faster-whisper
```
Dann in den Einstellungen → Workflows → STT-Anbieter: "Lokal (faster-whisper)" wählen.

---

## Erster Start

1. App starten: Startmenü bzw. Desktop-Verknüpfung (Windows), `./start.sh` (Linux)
2. Tray-Icon erscheint in der Taskleiste. Windows 11 legt neue Tray-Icons oft im Überlauf (`^`) ab. Unter „Einstellungen → Personalisierung → Taskleiste → Andere Taskleistensymbole“ lässt es sich dauerhaft einblenden.
3. Rechtsklick → Einstellungen → API-Zugänge → API Key eintragen
4. Rechtsklick → Blitztext → Aufnahme starten

Unter Linux öffnet ein Linksklick auf das Tray-Icon kein Popup (Wayland-Einschränkung). Dort nutzt du den Rechtsklick.

---

## Konfiguration

Einstellungen werden gespeichert in:
- **Linux:** `~/.config/blitztext/settings.json`
- **Windows:** `%APPDATA%\blitztext\settings.json`

API Keys werden im System-Keyring gespeichert (sicher, nicht im Klartext) — nicht in der `settings.json`.

---

## Projektstruktur

```
main.py                         Einstiegspunkt
install_windows.bat             Quellcode-Setup für Windows (Entwickler)
install_linux.sh                Automatisches Setup für Linux
requirements.txt                Python-Abhängigkeiten (pyautogui/pywin32 nur unter Windows)
BlitztextEXE/
  build_exe.bat                 baut dist\Blitztext\Blitztext.exe (Entwickler)
  make_icon.py                  erzeugt Blitztext.ico aus dem Tray-Icon
  Blitztext.spec                PyInstaller-Konfiguration
  Blitztext.iss                 Inno-Setup-Skript für BlitztextSetup-x.y.z.exe
blitztext/
  workflow.py                   Kernlogik aller 4 Workflows
  services/
    settings.py                 Konfiguration + Keyring + Modell-Vorschlagslisten
    recorder.py                 Audioaufnahme (sounddevice)
    stt.py                      STT-Anbieter (Groq/OpenAI/AssemblyAI/lokal/custom)
    llm.py                      LLM-Anbieter (Groq/OpenAI/Claude/Ollama/custom)
    hotkeys.py                  Globale Hotkeys (pynput)
    paste.py                    Clipboard + Auto-Paste
    autostart.py                Autostart mit Windows (Registry-Eintrag, Windows)
  ui/
    tray.py                     System-Tray + Menü
    workflow_window.py          Aufnahme-UI mit Waveform
    settings_window.py          Einstellungs-UI
```

---

## Datenfluss

```
Online (Groq/OpenAI/Claude):  Dein PC → gewählter API-Anbieter
Lokal (Ollama/faster-whisper): Dein PC → läuft komplett auf deiner eigenen Hardware
```

Kein eigenes Backend. Audio und Text gehen direkt vom PC zum gewählten Anbieter.

---

## Lizenz

MIT License — abgeleitet vom Original [cmagnussen/blitztext-app](https://github.com/cmagnussen/blitztext-app).
