# Blitztext Cross-Platform

**Speech-to-text desktop app for Windows 11 and Linux Debian.**

A Python/PyQt6 fork of the concept from [cmagnussen/blitztext-app](https://github.com/cmagnussen/blitztext-app) (macOS original, MIT license).

> Bring your own API key — no backend, no telemetry, no warranty.

---

## Was die App macht

| Workflow | Hotkey (Standard) | Beschreibung |
|---|---|---|
| 🎙 **Blitztext** | `Ctrl+Shift+R` | Sprache → Text (nur Transkription) |
| ✨ **Blitztext+** | `Ctrl+Shift+T` | Sprache → Transkription → Text verbessert |
| 🔥 **Blitztext $%&!** | `Ctrl+Shift+D` | Frustrierte Sprache → ruhige Nachricht |
| 😊 **Blitztext :)** | `Ctrl+Shift+E` | Sprache → Text mit passenden Emojis |

---

## Unterstützte Anbieter

### Transkription (STT)
| Anbieter | Was du brauchst |
|---|---|
| **OpenAI Whisper API** *(Standard)* | OpenAI API Key |
| **Groq Whisper** (schnell & günstig) | Groq API Key |
| **AssemblyAI** | AssemblyAI API Key |
| **Lokal (faster-whisper)** | `pip install faster-whisper`, kein Key nötig |
| **Eigener Endpunkt** | OpenAI-kompatibler Endpunkt |

### LLM (Textverarbeitung)
| Anbieter | Was du brauchst |
|---|---|
| **OpenAI GPT-4o-mini** *(Standard)* | OpenAI API Key |
| **Groq** | Groq API Key |
| **Ollama** (lokal) | Ollama läuft auf localhost:11434 |
| **Eigener Endpunkt** | OpenAI-kompatibler Endpunkt |

Jeden Workflow kannst du **unabhängig** konfigurieren — z.B. Blitztext mit Groq-Whisper, Blitztext+ mit lokalem Ollama.

---

## Installation

### Voraussetzungen
- Python 3.10+
- Auf Linux: `portaudio19-dev` für Audioaufnahme
- Auf Windows: keine zusätzlichen System-Pakete nötig

### Linux (Debian/Ubuntu)
```bash
sudo apt-get install portaudio19-dev
git clone https://github.com/DEIN_USER/blitztext-cross.git
cd blitztext-cross
pip install -r requirements.txt
python main.py
```

### Windows 11
```cmd
git clone https://github.com/DEIN_USER/blitztext-cross.git
cd blitztext-cross
pip install -r requirements.txt
python main.py
```

### Globale Hotkeys aktivieren

**Linux X11:**
```bash
pip install pynput
# xdotool für Auto-Paste:
sudo apt-get install xdotool
```

**Linux Wayland:**
```bash
pip install pynput
sudo apt-get install ydotool
```

**Windows:**
```cmd
pip install pynput pyautogui
```

### Lokale Transkription (kein API Key)
```bash
pip install faster-whisper
```
Dann in den Einstellungen → Workflows → STT-Anbieter: "Lokal (faster-whisper)" wählen.

---

## Erster Start

1. App starten: `python main.py`
2. Tray-Icon erscheint in der Taskleiste
3. Rechtsklick → Einstellungen → API-Zugänge → OpenAI API Key eintragen
4. Rechtsklick → Blitztext → Aufnahme starten

---

## Konfiguration

Einstellungen werden gespeichert in:
- **Linux:** `~/.config/blitztext/settings.json`
- **Windows:** `%APPDATA%\blitztext\settings.json`

API Keys werden im System-Keyring gespeichert (sicher, nicht im Klartext).

---

## Projektstruktur

```
main.py                         Einstiegspunkt
blitztext/
  workflow.py                   Kernlogik aller 4 Workflows
  services/
    settings.py                 Konfiguration + Keyring
    recorder.py                 Audioaufnahme (sounddevice)
    stt.py                      STT-Anbieter (OpenAI/Groq/AssemblyAI/lokal/custom)
    llm.py                      LLM-Anbieter (OpenAI/Groq/Ollama/custom)
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
Online (OpenAI):    Dein PC → OpenAI Whisper API → OpenAI GPT API
Online (Groq):      Dein PC → Groq API
Lokal:              Dein PC → faster-whisper → Ollama
```

Kein eigenes Backend. Audio und Text gehen direkt vom PC zum gewählten Anbieter.

---

## Lizenz

MIT License — abgeleitet vom Original [cmagnussen/blitztext-app](https://github.com/cmagnussen/blitztext-app).
