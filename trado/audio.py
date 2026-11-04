"""Microphone recording. Audio lives only in memory; nothing is written to disk."""

import io
import threading
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000  # 16 kHz mono is what Whisper uses internally
MAX_SECONDS = 60  # safety cap so a stuck key can't record forever
MIN_SECONDS = 0.4  # shorter than this is treated as an accidental tap


class Recorder:
    def __init__(self) -> None:
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._frames = 0

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._chunks = []
            self._frames = 0
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=self._on_audio
            )
            self._stream.start()

    def _on_audio(self, indata, frames, time_info, status) -> None:
        if self._frames < MAX_SECONDS * SAMPLE_RATE:
            self._chunks.append(indata.copy())
            self._frames += frames

    def stop(self) -> bytes | None:
        """Stop recording. Returns WAV bytes, or None if it was too short."""
        with self._lock:
            stream, self._stream = self._stream, None
        if stream is None:
            return None
        stream.stop()
        stream.close()

        if not self._chunks or self._frames < MIN_SECONDS * SAMPLE_RATE:
            return None
        samples = np.concatenate(self._chunks)
        self._chunks = []

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(samples.tobytes())
        return buffer.getvalue()
