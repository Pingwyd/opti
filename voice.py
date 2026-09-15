"""
Voice input: microphone capture and local transcription.

Optional dependencies (see requirements-voice.txt):
  sounddevice, numpy, faster-whisper

The app starts normally when these packages are not installed; voice features
report a friendly error only when the user enables voice input.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
CHANNELS = 1

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via tests with mocks
    np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False

try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except ImportError:  # pragma: no cover
    sd = None  # type: ignore[assignment]
    SOUNDDEVICE_AVAILABLE = False

try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
except ImportError:  # pragma: no cover
    WhisperModel = None  # type: ignore[assignment,misc]
    FASTER_WHISPER_AVAILABLE = False


def voice_deps_available() -> bool:
    """True when capture and local transcription dependencies are importable."""
    return NUMPY_AVAILABLE and SOUNDDEVICE_AVAILABLE and FASTER_WHISPER_AVAILABLE


def voice_capture_available() -> bool:
    """True when microphone capture dependencies are importable."""
    return NUMPY_AVAILABLE and SOUNDDEVICE_AVAILABLE


def missing_voice_deps_message() -> str:
    if voice_deps_available():
        return ""
    missing: list[str] = []
    if not NUMPY_AVAILABLE:
        missing.append("numpy")
    if not SOUNDDEVICE_AVAILABLE:
        missing.append("sounddevice")
    if not FASTER_WHISPER_AVAILABLE:
        missing.append("faster-whisper")
    joined = ", ".join(missing)
    return (
        f"Voice input requires optional packages: {joined}. "
        "Install with: pip install -r requirements-voice.txt"
    )


def compute_rms(samples: Any) -> float:
    """Return RMS amplitude for a mono float32 audio chunk (0.0–1.0 scale)."""
    if samples is None:
        return 0.0
    arr = np.asarray(samples, dtype=np.float32) if NUMPY_AVAILABLE else samples
    if getattr(arr, "size", 0) == 0:
        return 0.0
    squared = arr.astype(np.float64) ** 2
    mean_sq = float(np.mean(squared))
    return float(np.sqrt(mean_sq))


CancelCallback = Callable[[], bool]
ProgressCallback = Callable[[int, int], None]
LevelCallback = Callable[[float], None]


class AudioRecorder:
    """Capture mono float32 audio from the default microphone via sounddevice."""

    def __init__(
        self,
        *,
        sample_rate: int = SAMPLE_RATE,
        on_level: LevelCallback | None = None,
    ) -> None:
        if not voice_capture_available():
            raise RuntimeError(missing_voice_deps_message())
        self._sample_rate = sample_rate
        self._on_level = on_level
        self._chunks: list[Any] = []
        self._stream: Any | None = None
        self._lock = threading.Lock()

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def _audio_callback(self, indata: Any, _frames: int, _time: Any, status: Any) -> None:
        if status:
            log.debug("sounddevice status: %s", status)
        chunk = np.array(indata[:, 0], dtype=np.float32, copy=True)
        with self._lock:
            self._chunks.append(chunk)
        if self._on_level is not None:
            try:
                self._on_level(compute_rms(chunk))
            except Exception:
                log.debug("Level callback failed", exc_info=True)

    def start(self) -> None:
        if self._stream is not None:
            return
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=CHANNELS,
            dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> Any:
        if self._stream is None:
            return np.array([], dtype=np.float32)
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
        with self._lock:
            if not self._chunks:
                return np.array([], dtype=np.float32)
            return np.concatenate(self._chunks)

    def is_recording(self) -> bool:
        return self._stream is not None


class VoiceTranscriber:
    """Load a faster-whisper model and transcribe mono float32 audio."""

    def __init__(
        self,
        model_size: str = "base",
        *,
        on_download_progress: ProgressCallback | None = None,
        cancel_check: CancelCallback | None = None,
    ) -> None:
        if not FASTER_WHISPER_AVAILABLE:
            raise RuntimeError(missing_voice_deps_message())
        self._model_size = model_size
        self._on_download_progress = on_download_progress
        self._cancel_check = cancel_check
        self._model: Any | None = None
        self._model_lock = threading.Lock()

    def _check_cancelled(self) -> None:
        if self._cancel_check is not None and self._cancel_check():
            raise InterruptedError("Transcription cancelled")

    @property
    def model_size(self) -> str:
        return self._model_size

    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self) -> None:
        self._check_cancelled()
        if self._model is not None:
            return
        with self._model_lock:
            self._check_cancelled()
            if self._model is not None:
                return
            self._report_progress(0, 100)
            try:
                self._model = self._create_model()
            except Exception:
                self._report_progress(0, 0)
                raise
            self._report_progress(100, 100)

    def _report_progress(self, current: int, total: int) -> None:
        if self._on_download_progress is not None:
            try:
                self._on_download_progress(current, total)
            except Exception:
                log.debug("Download progress callback failed", exc_info=True)

    def _create_model(self) -> Any:
        assert WhisperModel is not None
        self._check_cancelled()
        self._report_progress(25, 100)
        model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        self._check_cancelled()
        self._report_progress(100, 100)
        return model

    def transcribe(self, audio: Any, *, sample_rate: int = SAMPLE_RATE) -> str:
        if not NUMPY_AVAILABLE:
            raise RuntimeError(missing_voice_deps_message())
        samples = np.asarray(audio, dtype=np.float32)
        if samples.size == 0:
            return ""
        self._check_cancelled()
        self.load_model()
        self._check_cancelled()
        assert self._model is not None
        segments, _info = self._model.transcribe(
            samples,
            language="en",
            vad_filter=True,
        )
        parts: list[str] = []
        for segment in segments:
            self._check_cancelled()
            text = str(getattr(segment, "text", "") or "").strip()
            if text:
                parts.append(text)
        return " ".join(parts).strip()

    def transcribe_bytes(self, audio: bytes, *, sample_rate: int = SAMPLE_RATE) -> str:
        if not NUMPY_AVAILABLE:
            raise RuntimeError(missing_voice_deps_message())
        samples = np.frombuffer(audio, dtype=np.float32)
        return self.transcribe(samples, sample_rate=sample_rate)
