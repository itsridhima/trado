"""Microphone recording. Audio lives only in memory; nothing is written to disk."""

import io
import threading
import time
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000  # 16 kHz mono is what Whisper uses internally
MAX_SECONDS = 60  # safety cap so a stuck key can't record forever
MIN_SECONDS = 0.4  # shorter than this is treated as an accidental tap
TAIL_SECONDS = 0.35  # keep recording a moment after release so the last word isn't cut off

QUIET_PEAK = 0.03  # below this the mic is too quiet for good transcription
LOUD_PEAK = 0.98  # at this the sound is clipped (distorted)
SILENT_PEAK = 0.02  # below this it is basically silence; speech models then invent words like "Thank you."


def is_too_quiet(peak: float) -> bool:
    return peak < SILENT_PEAK


def list_input_devices() -> list[tuple[int, str]]:
    return [(i, d["name"]) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]


def resolve_device(choice: str) -> int | None:
    """'' -> Windows default. A number -> that device index. Text -> first input device containing it."""
    if not choice:
        return None
    inputs = list_input_devices()
    if choice.isdigit():
        index = int(choice)
        if any(i == index for i, _ in inputs):
            return index
        raise ValueError(f"No microphone with number {index}. Run: python -m trado --mics")
    for index, name in inputs:
        if choice.lower() in name.lower():
            return index
    raise ValueError(f"No microphone matching '{choice}'. Run: python -m trado --mics")


class Recorder:
    def __init__(self, device: str = "") -> None:
        self._device = resolve_device(device)
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._frames = 0
        self.last_seconds = 0.0
        self.last_peak = 0.0  # loudest point, 0.0 to 1.0

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._chunks = []
            self._frames = 0
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                device=self._device, callback=self._on_audio,
            )
            self._stream.start()

    def _on_audio(self, indata, frames, time_info, status) -> None:
        if self._frames < MAX_SECONDS * SAMPLE_RATE:
            self._chunks.append(indata.copy())
            self._frames += frames

    def stop(self) -> bytes | None:
        """Stop recording. Returns WAV bytes, or None if it was too short."""
        time.sleep(TAIL_SECONDS)
        with self._lock:
            stream, self._stream = self._stream, None
        if stream is None:
            return None
        stream.stop()
        stream.close()

        if not self._chunks:
            return None
        samples = np.concatenate(self._chunks)
        self._chunks = []
        self.last_seconds = len(samples) / SAMPLE_RATE
        self.last_peak = float(np.abs(samples.astype(np.int32)).max()) / 32768.0
        if self.last_seconds < MIN_SECONDS + TAIL_SECONDS:
            return None

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(samples.tobytes())
        return buffer.getvalue()

    def volume_note(self) -> str:
        if self.last_peak < QUIET_PEAK:
            return "very quiet - speak closer to the mic or raise the mic volume in Windows"
        if self.last_peak > LOUD_PEAK:
            return "too loud (distorted) - lower the mic volume or speak a bit further away"
        return "volume OK"
