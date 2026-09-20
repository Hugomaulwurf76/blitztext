"""
Speech-to-Text service.
Supports: OpenAI Whisper API, Groq Whisper, AssemblyAI, local faster-whisper, custom endpoint.
"""

from pathlib import Path
from typing import Optional

from .settings import (
    STTProvider, WorkflowModelConfig,
    get_api_key, KEY_OPENAI, KEY_GROQ, KEY_ASSEMBLYAI, KEY_CUSTOM_STT,
)


class STTError(Exception):
    pass


async def transcribe(audio_path: Path, cfg: WorkflowModelConfig) -> str:
    """Dispatch to the correct STT backend based on cfg.stt_provider."""
    provider = cfg.stt_provider

    if provider == STTProvider.OPENAI:
        return await _transcribe_openai(audio_path, cfg)
    elif provider == STTProvider.GROQ:
        return await _transcribe_groq(audio_path, cfg)
    elif provider == STTProvider.ASSEMBLYAI:
        return await _transcribe_assemblyai(audio_path, cfg)
    elif provider == STTProvider.LOCAL:
        return await _transcribe_local(audio_path, cfg)
    elif provider == STTProvider.CUSTOM:
        return await _transcribe_custom(audio_path, cfg)
    else:
        raise STTError(f"Unbekannter STT-Anbieter: {provider}")


# ── OpenAI Whisper ────────────────────────────────────────────────────────────

async def _transcribe_openai(audio_path: Path, cfg: WorkflowModelConfig) -> str:
    api_key = get_api_key(KEY_OPENAI)
    if not api_key:
        raise STTError("OpenAI API Key fehlt. Bitte in den Einstellungen hinterlegen.")

    try:
        import httpx
    except ImportError:
        raise STTError("httpx nicht installiert. Bitte 'pip install httpx' ausführen.")

    model = cfg.stt_model or "whisper-1"
    lang  = cfg.language or ""

    async with httpx.AsyncClient(timeout=60) as client:
        with open(audio_path, "rb") as f:
            files  = {"file": (audio_path.name, f, "audio/wav")}
            data   = {"model": model, "response_format": "text"}
            if lang:
                data["language"] = lang

            resp = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                data=data,
            )

    if resp.status_code != 200:
        _raise_api_error("OpenAI", resp)

    return resp.text.strip()


# ── Groq Whisper ──────────────────────────────────────────────────────────────

async def _transcribe_groq(audio_path: Path, cfg: WorkflowModelConfig) -> str:
    api_key = get_api_key(KEY_GROQ)
    if not api_key:
        raise STTError("Groq API Key fehlt. Bitte in den Einstellungen hinterlegen.")

    try:
        import httpx
    except ImportError:
        raise STTError("httpx nicht installiert.")

    model = cfg.stt_model or "whisper-large-v3-turbo"
    lang  = cfg.language or ""

    async with httpx.AsyncClient(timeout=60) as client:
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}
            data  = {"model": model, "response_format": "text"}
            if lang:
                data["language"] = lang

            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                data=data,
            )

    if resp.status_code != 200:
        _raise_api_error("Groq", resp)

    return resp.text.strip()


# ── AssemblyAI ────────────────────────────────────────────────────────────────

async def _transcribe_assemblyai(audio_path: Path, cfg: WorkflowModelConfig) -> str:
    api_key = get_api_key(KEY_ASSEMBLYAI)
    if not api_key:
        raise STTError("AssemblyAI API Key fehlt. Bitte in den Einstellungen hinterlegen.")

    try:
        import httpx
    except ImportError:
        raise STTError("httpx nicht installiert.")

    headers = {"authorization": api_key, "content-type": "application/json"}

    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Upload audio
        with open(audio_path, "rb") as f:
            up = await client.post(
                "https://api.assemblyai.com/v2/upload",
                headers={"authorization": api_key},
                content=f.read(),
            )
        if up.status_code != 200:
            raise STTError(f"AssemblyAI Upload fehlgeschlagen: {up.status_code}")

        audio_url = up.json()["upload_url"]
        lang_code = cfg.language or None

        # 2. Request transcription
        payload = {"audio_url": audio_url}
        if lang_code:
            payload["language_code"] = lang_code

        tr = await client.post(
            "https://api.assemblyai.com/v2/transcript",
            json=payload,
            headers=headers,
        )
        transcript_id = tr.json()["id"]

        # 3. Poll
        import asyncio
        for _ in range(120):
            await asyncio.sleep(1)
            poll = await client.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers,
            )
            status = poll.json().get("status")
            if status == "completed":
                return poll.json().get("text", "").strip()
            if status == "error":
                raise STTError(f"AssemblyAI Fehler: {poll.json().get('error')}")

    raise STTError("AssemblyAI Timeout.")


# ── Local faster-whisper ──────────────────────────────────────────────────────

async def _transcribe_local(audio_path: Path, cfg: WorkflowModelConfig) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise STTError(
            "faster-whisper nicht installiert.\n"
            "Bitte 'pip install faster-whisper' ausführen."
        )

    import asyncio
    import concurrent.futures

    model_size = cfg.local_model_size or "base"
    language   = cfg.language or None

    def _run() -> str:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(audio_path), language=language)
        return " ".join(s.text for s in segments).strip()

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, _run)


# ── Custom endpoint ───────────────────────────────────────────────────────────

async def _transcribe_custom(audio_path: Path, cfg: WorkflowModelConfig) -> str:
    api_key = get_api_key(KEY_CUSTOM_STT)
    url     = cfg.custom_stt_url
    if not url:
        raise STTError("Kein eigener STT-Endpunkt konfiguriert.")

    try:
        import httpx
    except ImportError:
        raise STTError("httpx nicht installiert.")

    async with httpx.AsyncClient(timeout=60) as client:
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}
            data  = {"model": cfg.stt_model or "whisper-1", "response_format": "text"}
            if cfg.language:
                data["language"] = cfg.language

            hdrs = {}
            if api_key:
                hdrs["Authorization"] = f"Bearer {api_key}"

            resp = await client.post(url, headers=hdrs, files=files, data=data)

    if resp.status_code != 200:
        _raise_api_error("Custom STT", resp)

    return resp.text.strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _raise_api_error(provider: str, resp) -> None:
    try:
        msg = resp.json().get("error", {}).get("message") or resp.text[:200]
    except Exception:
        msg = resp.text[:200]
    raise STTError(f"{provider} Fehler {resp.status_code}: {msg}")


def clean_transcript(text: str) -> str:
    """Remove common Whisper hallucination artifacts."""
    hallucinations = {
        "Vielen Dank für Ihre Aufmerksamkeit.",
        "Danke für Ihre Aufmerksamkeit.",
        "Untertitel der Amara.org-Community",
        "Untertitel im Auftrag des ZDF",
        "Thank you for watching.",
        "Thanks for watching.",
        "Untertitelung des ZDF, 2020",
    }
    t = text.strip()
    if t in hallucinations:
        return ""
    return t


def is_likely_artifact(text: str, duration: float) -> bool:
    cleaned = clean_transcript(text)
    if not cleaned:
        return True
    if duration < 1.0 and len(cleaned.split()) < 2:
        return True
    return False
