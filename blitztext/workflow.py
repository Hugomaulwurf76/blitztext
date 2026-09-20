"""
Workflow runner.
Each workflow runs in the same pattern:
  1. Start recording
  2. Stop recording
  3. Transcribe (STT)
  4. Optionally rewrite (LLM)
  5. Output text → clipboard / auto-paste
"""

import asyncio
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

from .services.recorder import AudioRecorder, is_too_short
from .services import stt, llm, paste
from .services.settings import (
    AppSettings,
    WorkflowModelConfig,
)


class WorkflowKind(Enum):
    TRANSCRIPTION  = auto()   # raw transcription only
    TEXT_IMPROVE   = auto()   # transcribe → improve
    DAMPF_ABLASSEN = auto()   # transcribe → calm down
    EMOJI_TEXT     = auto()   # transcribe → add emojis


class Phase(Enum):
    IDLE         = "idle"
    RECORDING    = "recording"
    TRANSCRIBING = "transcribing"
    REWRITING    = "rewriting"
    DONE         = "done"
    ERROR        = "error"


# Callbacks the UI can subscribe to
PhaseCallback  = Callable[[Phase, str], None]   # (phase, message)
OutputCallback = Callable[[str], None]          # (result_text)


class WorkflowRunner:
    """
    Manages recording state and async processing for a single workflow kind.
    Thread-safe: recording runs in the calling thread; async work runs in a
    Qt-owned asyncio event loop.
    """

    def __init__(
        self,
        kind: WorkflowKind,
        settings: AppSettings,
        on_phase: Optional[PhaseCallback] = None,
        on_output: Optional[OutputCallback] = None,
    ):
        self.kind = kind
        self.settings = settings
        self.on_phase = on_phase
        self.on_output = on_output

        self._recorder = AudioRecorder()
        self._task: Optional[asyncio.Task] = None
        self._phase = Phase.IDLE

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def is_recording(self) -> bool:
        return self._recorder.is_recording

    @property
    def audio_level(self) -> float:
        return self._recorder.audio_level

    # ── Recording control ─────────────────────────────────────────────────────

    def start_recording(self) -> None:
        if self._phase != Phase.IDLE:
            return
        # Recorder bei jedem Start frisch erzeugen — vermeidet Zustandsprobleme
        # aus vorheriger Aufnahme (z.B. zurueckgebliebener Stream, alte frames).
        self._recorder = AudioRecorder(device=self.settings.audio_input_device)
        self._recorder.start()
        if self._recorder.error:
            self._set_phase(Phase.ERROR, self._recorder.error)
        else:
            self._set_phase(Phase.RECORDING, "Aufnahme läuft …")

    def stop_recording(self) -> None:
        if self._phase != Phase.RECORDING:
            return

        audio_path = self._recorder.stop()
        duration   = self._recorder.duration

        if audio_path is None:
            self._set_phase(Phase.ERROR, self._recorder.error or "Aufnahme fehlgeschlagen.")
            return

        if is_too_short(duration):
            audio_path.unlink(missing_ok=True)
            self._set_phase(Phase.ERROR, "Aufnahme zu kurz — bitte länger sprechen.")
            return

        self._run_async(audio_path, duration)

    def cancel(self) -> None:
        if self._task:
            self._task.cancel()
        self._recorder.discard()
        self._set_phase(Phase.IDLE, "")

    def reset(self) -> None:
        self.cancel()

    # ── Async processing ──────────────────────────────────────────────────────

    def _run_async(self, audio_path: Path, duration: float) -> None:
        """Schedule async processing. Requires a running asyncio event loop."""
        try:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._process(audio_path, duration))
        except RuntimeError:
            # No running loop — create one in a thread
            import threading
            def _run():
                asyncio.run(self._process(audio_path, duration))
            threading.Thread(target=_run, daemon=True).start()

    async def _process(self, audio_path: Path, duration: float) -> None:
        try:
            # ── Step 1: Transcribe ────────────────────────────────────────────
            self._set_phase(Phase.TRANSCRIBING, "Wird transkribiert …")
            cfg = self._get_stt_config()
            text = await stt.transcribe(audio_path, cfg)

            try:
                audio_path.unlink(missing_ok=True)
            except Exception:
                pass

            text = stt.clean_transcript(text)
            if stt.is_likely_artifact(text, duration):
                self._set_phase(Phase.ERROR, "Keine Sprache erkannt.")
                return

            # ── Step 2: Optional LLM pass ─────────────────────────────────────
            if self.kind == WorkflowKind.TEXT_IMPROVE:
                self._set_phase(Phase.REWRITING, "Text wird verbessert …")
                text = await llm.improve_text(text, self.settings.text_improvement)

            elif self.kind == WorkflowKind.DAMPF_ABLASSEN:
                self._set_phase(Phase.REWRITING, "Wird umformuliert …")
                text = await llm.dampf_ablassen(text, self.settings.dampf_ablassen)

            elif self.kind == WorkflowKind.EMOJI_TEXT:
                self._set_phase(Phase.REWRITING, "Emojis werden eingefügt …")
                text = await llm.add_emojis(text, self.settings.emoji)

            # ── Step 3: Output ─────────────────────────────────────────────────
            # Clipboard + Paste passieren im UI-Hauptthread (siehe workflow_window),
            # da Qt-Clipboard und Windows-COM nur dort sicher funktionieren.
            self._set_phase(Phase.DONE, text)
            if self.on_output:
                self.on_output(text)

        except asyncio.CancelledError:
            self._set_phase(Phase.IDLE, "")
        except Exception as exc:
            self._set_phase(Phase.ERROR, str(exc))

    # ── Config helpers ────────────────────────────────────────────────────────

    def _get_stt_config(self) -> WorkflowModelConfig:
        if self.kind == WorkflowKind.TRANSCRIPTION:
            return self.settings.transcription_model
        elif self.kind == WorkflowKind.TEXT_IMPROVE:
            return self.settings.text_improvement.model
        elif self.kind == WorkflowKind.DAMPF_ABLASSEN:
            return self.settings.dampf_ablassen.model
        elif self.kind == WorkflowKind.EMOJI_TEXT:
            return self.settings.emoji.model
        return self.settings.transcription_model

    # ── Phase helper ──────────────────────────────────────────────────────────

    def _set_phase(self, phase: Phase, message: str) -> None:
        self._phase = phase
        if self.on_phase:
            self.on_phase(phase, message)
