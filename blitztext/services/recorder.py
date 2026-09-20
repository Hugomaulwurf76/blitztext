"""
Audio recording via sounddevice — cross-platform (Win11 + Linux).
Records to a temporary WAV file, returns the path when done.
"""

import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


SAMPLE_RATE = 16000   # Whisper works best at 16 kHz
CHANNELS    = 1


def list_input_devices() -> list[dict]:
    """Gibt eine Liste der verfuegbaren Aufnahme-Geraete zurueck."""
    devices = []
    try:
        all_devs = sd.query_devices()
        default_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else None
        for idx, d in enumerate(all_devs):
            if d.get("max_input_channels", 0) > 0:
                devices.append({
                    "index": idx,
                    "name": d.get("name", f"Device {idx}"),
                    "hostapi": d.get("hostapi", -1),
                    "channels": d.get("max_input_channels", 0),
                    "default": (idx == default_in),
                })
    except Exception:
        pass
    return devices


class AudioRecorder:
    def __init__(self, device: Optional[int] = None):
        self._device = device
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._thread: Optional[threading.Thread] = None
        self._stream: Optional[sd.InputStream] = None
        self._tmp_path: Optional[Path] = None
        self._start_time: Optional[float] = None
        self._duration: float = 0.0
        self.error: Optional[str] = None
        self._level: float = 0.0
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def audio_level(self) -> float:
        """RMS level 0..1 for waveform visualisation."""
        return self._level

    @property
    def duration(self) -> float:
        return self._duration

    def start(self) -> None:
        if self._recording:
            return
        self.error = None
        self._frames = []
        self._start_time = time.monotonic()

        # Natuerliche Samplerate des Geraets ermitteln — manche USB-Mikros
        # (z.B. Razer Seiren) unterstuetzen nur 44.1/48 kHz.
        device_rate = SAMPLE_RATE
        try:
            if self._device is not None:
                info = sd.query_devices(self._device)
                device_rate = int(info.get("default_samplerate") or SAMPLE_RATE)
            else:
                info = sd.query_devices(kind="input")
                device_rate = int(info.get("default_samplerate") or SAMPLE_RATE)
        except Exception:
            pass

        self._device_rate = device_rate

        try:
            self._stream = sd.InputStream(
                samplerate=device_rate,
                channels=CHANNELS,
                dtype="float32",
                callback=self._callback,
                blocksize=1024,
                device=self._device,
            )
            self._stream.start()
            self._recording = True
        except Exception as exc:
            self.error = str(exc)
            self._recording = False

    def stop(self) -> Optional[Path]:
        """Stop recording, write WAV, return temp file path (or None on error)."""
        if not self._recording:
            return None
        self._recording = False
        self._duration = time.monotonic() - (self._start_time or 0)
        self._level = 0.0

        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
        except Exception:
            pass

        if not self._frames:
            self.error = "Keine Audiodaten aufgenommen."
            return None

        audio = np.concatenate(self._frames, axis=0)

        # Auf SAMPLE_RATE (16 kHz) resampeln falls noetig.
        # Einfaches Linear-Resampling reicht fuer Sprache.
        device_rate = getattr(self, "_device_rate", SAMPLE_RATE)
        if device_rate != SAMPLE_RATE:
            n_in = audio.shape[0]
            n_out = int(round(n_in * SAMPLE_RATE / device_rate))
            if n_out > 0:
                x_old = np.linspace(0, 1, n_in, endpoint=False)
                x_new = np.linspace(0, 1, n_out, endpoint=False)
                # mono ist 1D oder (n,1)
                if audio.ndim == 2:
                    audio = audio[:, 0]
                audio = np.interp(x_new, x_old, audio).astype(np.float32)

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        self._tmp_path = Path(tmp.name)

        try:
            sf.write(str(self._tmp_path), audio, SAMPLE_RATE)
            return self._tmp_path
        except Exception as exc:
            self.error = str(exc)
            return None

    def discard(self) -> None:
        self._recording = False
        self._frames = []
        self._level = 0.0
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._tmp_path and self._tmp_path.exists():
            try:
                self._tmp_path.unlink()
            except Exception:
                pass
        self._tmp_path = None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        data = indata.copy()
        with self._lock:
            self._frames.append(data)
        rms = float(np.sqrt(np.mean(data ** 2)))
        self._level = min(rms * 10, 1.0)   # crude normalisation


def is_too_short(duration: float, min_seconds: float = 0.4) -> bool:
    return duration < min_seconds
