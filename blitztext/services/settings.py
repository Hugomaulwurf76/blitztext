"""
Settings management — API keys via keyring, preferences via JSON config file.
Supports multiple STT and LLM providers; defaults are Groq Whisper + Groq LLM.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import keyring

SERVICE_NAME = "Blitztext"

# ── Keyring keys ─────────────────────────────────────────────────────────────
KEY_OPENAI      = "openai_api_key"
KEY_GROQ        = "groq_api_key"
KEY_ANTHROPIC   = "anthropic_api_key"
KEY_ASSEMBLYAI  = "assemblyai_api_key"
KEY_CUSTOM_STT  = "custom_stt_api_key"
KEY_CUSTOM_LLM  = "custom_llm_api_key"


def _config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    p = base / "blitztext"
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


# ── Provider enums ────────────────────────────────────────────────────────────

class STTProvider:
    GROQ       = "groq_whisper"
    OPENAI     = "openai_whisper"
    ASSEMBLYAI = "assemblyai"
    LOCAL      = "local_whisper"
    CUSTOM     = "custom"

    ALL = [GROQ, OPENAI, ASSEMBLYAI, LOCAL, CUSTOM]

    DISPLAY = {
        GROQ:       "Groq Whisper (kostenlos, Standard)",
        OPENAI:     "OpenAI Whisper API",
        ASSEMBLYAI: "AssemblyAI",
        LOCAL:      "Lokal (faster-whisper)",
        CUSTOM:     "Eigener Endpunkt",
    }


class LLMProvider:
    GROQ      = "groq"
    OPENAI    = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA    = "ollama"
    CUSTOM    = "custom"

    ALL = [GROQ, OPENAI, ANTHROPIC, OLLAMA, CUSTOM]

    DISPLAY = {
        GROQ:      "Groq (kostenlos, Standard)",
        OPENAI:    "OpenAI",
        ANTHROPIC: "Claude (Anthropic)",
        OLLAMA:    "Ollama (lokal)",
        CUSTOM:    "Eigener Endpunkt",
    }


# ── Bekannte LLM-Modelle je Anbieter (Stand: 09/2026) ──────────────────────────
# Wird als Vorschlagsliste in den Einstellungen verwendet (editierbare Auswahlliste,
# eigene Modellnamen bleiben weiterhin möglich).

LLM_MODEL_PRESETS = {
    # Achtung: llama-3.1-8b-instant und llama-3.3-70b-versatile wurden von Groq
    # auf Enterprise/Contact-Sales umgestellt und sind mit einem normalen
    # kostenlosen/Developer-Key NICHT mehr erreichbar (404). Entfernt.
    LLMProvider.GROQ: [
        "openai/gpt-oss-120b",       # empfohlen, Developer-Tier, bestaetigt funktionsfaehig
        "openai/gpt-oss-20b",        # schneller/guenstiger, Developer-Tier
        "qwen/qwen3.8-27b",          # Preview, Developer-Tier
    ],
    LLMProvider.OPENAI: [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-5.6-sol",
        "gpt-6-astra",
        "gpt-4.1",
        "gpt-4o-mini",
    ],
    LLMProvider.ANTHROPIC: [
        "claude-sonnet-5",
        "claude-opus-5",
        "claude-haiku-4-5-20251001",
        "claude-fable-5-1",
    ],
    # Ollama = selbst gehostetes LLM. Erfordert eine laufende, lokale
    # Ollama-Installation (siehe ollama_base_url, Standard: localhost:11434) -
    # dort muss das jeweilige Modell vorher per "ollama pull <name>"
    # heruntergeladen worden sein. Ohne laufende Ollama-Instanz nutzlos.
    LLMProvider.OLLAMA: [
        "llama3.1",       # weiterhin Standard-Empfehlung fuer allgemeinen Chat
        "qwen3.6",        # aktuelle Qwen-Generation, staerkstes dichtes Modell lokal
        "gpt-oss:20b",    # OpenAIs offenes Modell, laeuft lokal
        "gemma4",         # aktuelle Gemma-Generation, Vision + Tools
        "mistral-nemo",   # Nachfolger von mistral 7b
    ],
    LLMProvider.CUSTOM: [],
}


# ── Model configs ─────────────────────────────────────────────────────────────

@dataclass
class WorkflowModelConfig:
    stt_provider: str  = STTProvider.GROQ
    stt_model: str     = "whisper-large-v3-turbo"
    llm_provider: str  = LLMProvider.GROQ
    llm_model: str     = "openai/gpt-oss-120b"
    custom_stt_url: str = ""
    custom_llm_url: str = ""
    local_model_size: str = "base"
    language: str = "de"


@dataclass
class DampfAblassenSettings:
    system_prompt: str = (
        "Du erhältst ein emotional gesprochenes Transkript. "
        "Erkenne zuerst das eigentliche Ziel, Anliegen und den wahren Frust der Person. "
        "Formuliere daraus eine klare, respektvolle und wirksame Nachricht, mit der die Person "
        "ihr Ziel eher erreicht. Bewahre relevante Fakten, konkrete Probleme, Grenzen, "
        "Erwartungen und die nötige Dringlichkeit. Entferne Beleidigungen, Drohungen, Sarkasmus, "
        "Unterstellungen und unnötige Eskalation. Wenn mehrere Vorwürfe genannt werden, verdichte "
        "sie auf die entscheidenden Kernpunkte. Der Ton soll ruhig, menschlich, bestimmt und "
        "lösungsorientiert sein. Gib NUR die fertige Nachricht zurück."
    )
    model: WorkflowModelConfig = field(default_factory=WorkflowModelConfig)


@dataclass
class TextImprovementSettings:
    system_prompt: str  = ""
    context: str        = ""
    tone: str           = "neutral"
    custom_terms: list  = field(default_factory=list)
    model: WorkflowModelConfig = field(default_factory=WorkflowModelConfig)


@dataclass
class EmojiSettings:
    density: str = "mittel"
    model: WorkflowModelConfig = field(default_factory=WorkflowModelConfig)


@dataclass
class HotkeyConfig:
    transcription:    str = "ctrl+alt+w"
    text_improvement: str = "ctrl+alt+b"
    dampf_ablassen:   str = "ctrl+alt+f"
    emoji_text:       str = "ctrl+alt+j"
    transcription_mode:    str = "hold"
    text_improvement_mode: str = "toggle"
    dampf_ablassen_mode:   str = "hold"
    emoji_text_mode:       str = "hold"
    enabled: bool = True


@dataclass
class AppSettings:
    hotkeys:             HotkeyConfig           = field(default_factory=HotkeyConfig)
    transcription_model: WorkflowModelConfig    = field(default_factory=WorkflowModelConfig)
    text_improvement:    TextImprovementSettings = field(default_factory=TextImprovementSettings)
    dampf_ablassen:      DampfAblassenSettings   = field(default_factory=DampfAblassenSettings)
    emoji:               EmojiSettings           = field(default_factory=EmojiSettings)
    launch_at_login:     bool                    = False
    auto_paste:          bool                    = True
    has_seen_onboarding: bool                    = False
    groq_stt_model:      str                     = "whisper-large-v3-turbo"
    groq_llm_model:      str                     = "openai/gpt-oss-120b"
    anthropic_model:     str                     = "claude-sonnet-5"
    ollama_base_url:     str                     = "http://localhost:11434"
    ollama_llm_model:    str                     = "llama3.2"
    custom_stt_url:      str                     = ""
    custom_llm_url:      str                     = ""
    audio_input_device:  Optional[int]           = None   # None = System-Default


# ── Load / Save ───────────────────────────────────────────────────────────────

def _nested_update(target: dict, source: dict) -> dict:
    for k, v in source.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            _nested_update(target[k], v)
        else:
            target[k] = v
    return target


def load_settings() -> AppSettings:
    path = _config_path()
    defaults = asdict(AppSettings())
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            merged = _nested_update(defaults, saved)
            return _dict_to_settings(merged)
        except Exception:
            pass
    return AppSettings()


def save_settings(s: AppSettings) -> None:
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(s), f, indent=2, ensure_ascii=False)


def _dict_to_settings(d: dict) -> AppSettings:
    s = AppSettings()

    def wmc(sub: dict) -> WorkflowModelConfig:
        c = WorkflowModelConfig()
        for k in vars(c):
            if k in sub:
                setattr(c, k, sub[k])
        return c

    if "hotkeys" in d:
        h = d["hotkeys"]
        s.hotkeys = HotkeyConfig(
            transcription=h.get("transcription", s.hotkeys.transcription),
            text_improvement=h.get("text_improvement", s.hotkeys.text_improvement),
            dampf_ablassen=h.get("dampf_ablassen", s.hotkeys.dampf_ablassen),
            emoji_text=h.get("emoji_text", s.hotkeys.emoji_text),
            transcription_mode=h.get("transcription_mode", s.hotkeys.transcription_mode),
            text_improvement_mode=h.get("text_improvement_mode", s.hotkeys.text_improvement_mode),
            dampf_ablassen_mode=h.get("dampf_ablassen_mode", s.hotkeys.dampf_ablassen_mode),
            emoji_text_mode=h.get("emoji_text_mode", s.hotkeys.emoji_text_mode),
            enabled=h.get("enabled", s.hotkeys.enabled),
        )
    if "transcription_model" in d:
        s.transcription_model = wmc(d["transcription_model"])
    if "text_improvement" in d:
        ti = d["text_improvement"]
        s.text_improvement = TextImprovementSettings(
            system_prompt=ti.get("system_prompt", ""),
            context=ti.get("context", ""),
            tone=ti.get("tone", "neutral"),
            custom_terms=ti.get("custom_terms", []),
            model=wmc(ti.get("model", {})),
        )
    if "dampf_ablassen" in d:
        da = d["dampf_ablassen"]
        s.dampf_ablassen = DampfAblassenSettings(
            system_prompt=da.get("system_prompt", s.dampf_ablassen.system_prompt),
            model=wmc(da.get("model", {})),
        )
    if "emoji" in d:
        em = d["emoji"]
        s.emoji = EmojiSettings(
            density=em.get("density", "mittel"),
            model=wmc(em.get("model", {})),
        )
    for attr in ("launch_at_login", "auto_paste", "has_seen_onboarding",
                 "groq_stt_model", "groq_llm_model", "anthropic_model",
                 "ollama_base_url", "ollama_llm_model",
                 "custom_stt_url", "custom_llm_url", "audio_input_device"):
        if attr in d:
            setattr(s, attr, d[attr])

    return s


# ── API key helpers ───────────────────────────────────────────────────────────

def get_api_key(name: str) -> Optional[str]:
    try:
        v = keyring.get_password(SERVICE_NAME, name)
        return v if v else None
    except Exception:
        return None


def set_api_key(name: str, value: str) -> None:
    keyring.set_password(SERVICE_NAME, name, value)


def delete_api_key(name: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, name)
    except Exception:
        pass


def masked(key: Optional[str]) -> str:
    if not key:
        return "—"
    if len(key) <= 8:
        return "••••••••"
    return key[:4] + "•" * (len(key) - 8) + key[-4:]
