"""
LLM service for text rewriting workflows.
Supports: Groq, OpenAI, Anthropic (Claude), Ollama, custom endpoint.
"""

from typing import Optional
from .settings import (
    LLMProvider, WorkflowModelConfig,
    get_api_key, KEY_OPENAI, KEY_GROQ, KEY_ANTHROPIC, KEY_CUSTOM_LLM,
    TextImprovementSettings, DampfAblassenSettings, EmojiSettings,
)


class LLMError(Exception):
    pass


# ── Public API ────────────────────────────────────────────────────────────────

async def improve_text(text: str, settings: TextImprovementSettings) -> str:
    system = _build_improve_prompt(settings)
    return await _complete(text, system, settings.model)


async def dampf_ablassen(text: str, settings: DampfAblassenSettings) -> str:
    return await _complete(text, settings.system_prompt, settings.model, temperature=0.4)


async def add_emojis(text: str, settings: EmojiSettings) -> str:
    system = _build_emoji_prompt(settings.density)
    return await _complete(text, system, settings.model)


# ── Dispatch ──────────────────────────────────────────────────────────────────

async def _complete(
    text: str,
    system_prompt: str,
    cfg: WorkflowModelConfig,
    temperature: float = 0.3,
) -> str:
    provider = cfg.llm_provider
    if provider == LLMProvider.GROQ:
        return await _groq(text, system_prompt, cfg, temperature)
    elif provider == LLMProvider.OPENAI:
        return await _openai(text, system_prompt, cfg, temperature)
    elif provider == LLMProvider.ANTHROPIC:
        return await _anthropic(text, system_prompt, cfg, temperature)
    elif provider == LLMProvider.OLLAMA:
        return await _ollama(text, system_prompt, cfg, temperature)
    elif provider == LLMProvider.CUSTOM:
        return await _custom(text, system_prompt, cfg, temperature)
    else:
        raise LLMError(f"Unbekannter LLM-Anbieter: {provider}")


# ── Groq ──────────────────────────────────────────────────────────────────────

async def _groq(text, system, cfg: WorkflowModelConfig, temp: float) -> str:
    api_key = get_api_key(KEY_GROQ)
    if not api_key:
        raise LLMError("Groq API Key fehlt. Bitte in den Einstellungen hinterlegen.\nKostenlos registrieren: https://console.groq.com")
    return await _call_openai_compatible(
        url="https://api.groq.com/openai/v1/chat/completions",
        api_key=api_key,
        model=cfg.llm_model or "llama-3.1-8b-instant",
        text=text, system=system, temp=temp,
    )


# ── OpenAI ────────────────────────────────────────────────────────────────────

async def _openai(text, system, cfg: WorkflowModelConfig, temp: float) -> str:
    api_key = get_api_key(KEY_OPENAI)
    if not api_key:
        raise LLMError("OpenAI API Key fehlt. Bitte in den Einstellungen hinterlegen.")
    return await _call_openai_compatible(
        url="https://api.openai.com/v1/chat/completions",
        api_key=api_key,
        model=cfg.llm_model or "gpt-4o-mini",
        text=text, system=system, temp=temp,
    )


# ── Anthropic (Claude) ────────────────────────────────────────────────────────

async def _anthropic(text, system, cfg: WorkflowModelConfig, temp: float) -> str:
    api_key = get_api_key(KEY_ANTHROPIC)
    if not api_key:
        raise LLMError("Anthropic API Key fehlt. Bitte in den Einstellungen hinterlegen.\nhttps://console.anthropic.com")

    try:
        import httpx
    except ImportError:
        raise LLMError("httpx nicht installiert.")

    from .settings import load_settings
    s = load_settings()
    model = cfg.llm_model or s.anthropic_model or "claude-sonnet-4-5"

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": text}],
        "temperature": temp,
    }

    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        )

    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", {}).get("message") or resp.text[:200]
        except Exception:
            msg = resp.text[:200]
        raise LLMError(f"Anthropic Fehler {resp.status_code}: {msg}")

    try:
        return resp.json()["content"][0]["text"].strip()
    except (KeyError, IndexError):
        raise LLMError("Keine Antwort von Claude erhalten.")


# ── Ollama ────────────────────────────────────────────────────────────────────

async def _ollama(text, system, cfg: WorkflowModelConfig, temp: float) -> str:
    from .settings import load_settings
    s = load_settings()
    base  = (s.ollama_base_url or "http://localhost:11434").rstrip("/")
    model = cfg.llm_model or s.ollama_llm_model or "llama3.2"
    return await _call_openai_compatible(
        url=f"{base}/v1/chat/completions",
        api_key=None,
        model=model, text=text, system=system, temp=temp,
    )


# ── Custom endpoint ───────────────────────────────────────────────────────────

async def _custom(text, system, cfg: WorkflowModelConfig, temp: float) -> str:
    api_key = get_api_key(KEY_CUSTOM_LLM)
    url     = cfg.custom_llm_url
    if not url:
        raise LLMError("Kein eigener LLM-Endpunkt konfiguriert.")
    return await _call_openai_compatible(
        url=url, api_key=api_key,
        model=cfg.llm_model or "gpt-4o-mini",
        text=text, system=system, temp=temp,
    )


# ── Shared HTTP (OpenAI-compatible) ──────────────────────────────────────────

async def _call_openai_compatible(
    url: str, api_key: Optional[str], model: str,
    text: str, system: str, temp: float,
) -> str:
    try:
        import httpx
    except ImportError:
        raise LLMError("httpx nicht installiert.")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": text},
        ],
        "temperature": temp,
    }

    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", {}).get("message") or resp.text[:200]
        except Exception:
            msg = resp.text[:200]
        raise LLMError(f"Fehler {resp.status_code}: {msg}")

    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        raise LLMError("Keine Antwort vom LLM erhalten.")


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_improve_prompt(settings: TextImprovementSettings) -> str:
    if settings.system_prompt:
        prompt = settings.system_prompt
    else:
        tone_map = {
            "formal":  "Verwende einen formellen, professionellen Ton.",
            "neutral": "Verwende einen neutralen, klaren Ton.",
            "casual":  "Verwende einen lockeren, natürlichen Ton.",
        }
        prompt = (
            "Du bist ein Lektor und Schreibassistent. Verbessere den folgenden Text:\n"
            "- Korrigiere Rechtschreibung und Grammatik\n"
            "- Verbessere die Formulierung und den Lesefluss\n"
            "- Behalte die ursprüngliche Bedeutung bei\n"
            f"- {tone_map.get(settings.tone, tone_map['neutral'])}\n"
            "Gib NUR den verbesserten Text zurück, keine Erklärungen."
        )
    if settings.custom_terms:
        prompt += f"\n\nWichtig: Diese Begriffe exakt so schreiben: {', '.join(settings.custom_terms)}"
    if settings.context:
        prompt += f"\n\nKontext: {settings.context}"
    return prompt


def _build_emoji_prompt(density: str) -> str:
    density_map = {
        "wenig":  "Setze nur vereinzelt Emojis ein, maximal 1–2 pro Absatz.",
        "mittel": "Setze regelmäßig passende Emojis ein, etwa alle 1–2 Sätze.",
        "viel":   "Setze großzügig Emojis ein, gerne mehrere pro Satz.",
    }
    return (
        "Du erhältst ein gesprochenes Transkript. Gib den Text möglichst originalgetreu zurück, "
        f"aber füge passende Emojis ein. {density_map.get(density, density_map['mittel'])} "
        "Korrigiere offensichtliche Fehler. Gib NUR den Text mit Emojis zurück."
    )
