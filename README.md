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
- Python 3.10 oder neuer (wird beim Installieren automatisch geprüft, versionsunabhängig)
- Auf Linux: das Install-Skript richtet `portaudio19-dev`, `xdotool`/`wtype` etc. automatisch ein (per `sudo apt-get`)
- Auf Windows: keine zusätzlichen System-Pakete nötig

### Linux (Debian/Ubuntu)
```bash
git clone https://github.com/Hugomaulwurf76/blitztext.git
cd blitztext
chmod +x install_linux.sh
./install_linux.sh
./start.sh
```

`install_linux.sh` erkennt automatisch ein passendes Python (≥3.10), legt ein eigenes `.venv` an, installiert alle System- und Python-Abhängigkeiten und erzeugt `start.sh`.

### Windows 11
```cmd
git clone https://github.com/Hugomaulwurf76/blitztext.git
cd blitztext
install_windows.bat
start.bat
```

`install_windows.bat` sucht automatisch ein passendes Python (≥3.10, egal welche genaue Version), installiert alle Python-Pakete und erzeugt `start.bat`. Ist kein passendes Python vorhanden, verlinkt das Skript direkt zum Download.

### Lokale Transkription (kein API Key)
```bash
pip install faster-whisper
```
Dann in den Einstellungen → Workflows → STT-Anbieter: "Lokal (faster-whisper)" wählen.

---

## Erster Start

1. App starten: `start.bat` (Windows) bzw. `./start.sh` (Linux) doppelklicken/ausführen
2. Tray-Icon erscheint in der Taskleiste
3. Rechtsklick → Einstellungen → API-Zugänge → API Key eintragen
4. Rechtsklick → Blitztext → Aufnahme starten

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
install_windows.bat             Automatisches Setup für Windows
install_linux.sh                Automatisches Setup für Linux
blitztext/
  workflow.py                   Kernlogik aller 4 Workflows
  services/
    settings.py                 Konfiguration + Keyring + Modell-Vorschlagslisten
    recorder.py                 Audioaufnahme (sounddevice)
    stt.py                      STT-Anbieter (Groq/OpenAI/AssemblyAI/lokal/custom)
    llm.py                      LLM-Anbieter (Groq/OpenAI/Claude/Ollama/custom)
    hotkeys.py                  Globale Hotkeys (pynput)
    paste.py                    Clipboard + Auto-Paste
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
