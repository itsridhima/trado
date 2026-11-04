"""Groq Whisper speech-to-text (free tier). Audio is sent from memory, never saved to disk."""

import time

import httpx

from trado.stt.base import RateLimitError, SpeechToTextProvider, SttError

API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_MODEL = "whisper-large-v3-turbo"

# A hint that helps Whisper spell Indian market words correctly.
VOCAB_HINT = "Nifty, Sensex, SEBI, NSE, BSE, SIP, mutual fund, demat, F&O, IPO, P/E ratio."

MAX_ATTEMPTS = 3
MAX_WAIT_SECONDS = 20.0


class GroqWhisperProvider(SpeechToTextProvider):
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, language: str = ""):
        if not api_key:
            raise SttError(
                "GROQ_API_KEY is empty. Open your .env file and paste your Groq key after "
                "GROQ_API_KEY="
            )
        self._api_key = api_key
        self._model = model
        self._language = language

    def transcribe(self, wav_bytes: bytes) -> str:
        data = {
            "model": self._model,
            "response_format": "json",
            "temperature": "0",
            "prompt": VOCAB_HINT,
        }
        if self._language:
            data["language"] = self._language

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = httpx.post(
                    API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data=data,
                    files={"file": ("speech.wav", wav_bytes, "audio/wav")},
                    timeout=30.0,
                )
            except httpx.TimeoutException:
                raise SttError("Groq took too long to answer. Check your internet and try again.")
            except httpx.HTTPError:
                raise SttError("Could not reach Groq. Check your internet connection.")

            status = response.status_code
            if status == 200:
                return response.json().get("text", "").strip()

            if status == 429:
                wait = self._retry_delay(response, attempt)
                if attempt < MAX_ATTEMPTS and wait <= MAX_WAIT_SECONDS:
                    print(f"  (Groq says slow down; retrying in {wait:.0f}s...)")
                    time.sleep(wait)
                    continue
                raise RateLimitError(
                    "Groq's free limit was reached. Wait a minute and try again."
                )

            if status in (401, 403):
                raise SttError("Groq rejected your API key. Check GROQ_API_KEY in your .env file.")
            if status >= 500:
                raise SttError(f"Groq had a problem on its side (error {status}). Try again soon.")
            raise SttError(f"Groq could not transcribe this (error {status}).")

        raise SttError("Transcription failed after several tries.")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("retry-after", "")
        try:
            return max(1.0, float(header))
        except ValueError:
            return float(2**attempt)
