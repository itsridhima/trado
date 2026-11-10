"""The built-in Windows voice (SAPI). Free, offline, nothing to download."""

import queue
import threading

from trado.tts.base import Speaker, TtsError

_SPEAK_ASYNC = 1  # return at once; sentences queue up and play in order
_PURGE = 2  # throw away anything queued or playing
_IS_SPEAKING = 2  # SAPI "running state" while talking


def list_voices() -> list[str]:
    """Names of the voices installed on this PC."""
    try:
        import comtypes.client

        voices = comtypes.client.CreateObject("SAPI.SpVoice").GetVoices()
        return [voices.Item(i).GetDescription() for i in range(voices.Count)]
    except Exception as err:
        raise TtsError(f"Couldn't read the Windows voices ({type(err).__name__}).")


class WindowsSpeaker(Speaker):
    """Talks through a Windows voice. All voice calls happen on one background thread,
    because Windows voice objects must stay on the thread that created them."""

    def __init__(self, voice: str = "", rate: int = 1):
        self._voice_wanted = voice
        self._rate = rate
        self._commands: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._error: str | None = None
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(timeout=10)
        if self._error:
            raise TtsError(self._error)

    def say(self, text: str) -> None:
        if text.strip():
            self._commands.put(("say", text))

    def stop(self) -> None:
        try:
            while True:  # forget sentences that haven't started yet
                self._commands.get_nowait()
        except queue.Empty:
            pass
        self._commands.put(("stop", ""))

    def is_speaking(self) -> bool:
        reply: queue.Queue = queue.Queue(maxsize=1)
        self._commands.put(("status", reply))
        try:
            return bool(reply.get(timeout=0.3))
        except queue.Empty:
            return False

    def _run(self) -> None:
        try:
            import comtypes
            import comtypes.client

            comtypes.CoInitialize()
            voice = comtypes.client.CreateObject("SAPI.SpVoice")
            self._choose_voice(voice)
            voice.Rate = self._rate
        except TtsError as err:
            self._error = str(err)
            self._ready.set()
            return
        except Exception as err:
            self._error = f"Couldn't start the Windows voice ({type(err).__name__})."
            self._ready.set()
            return
        self._ready.set()

        while True:
            command, text = self._commands.get()
            try:
                if command == "say":
                    voice.Speak(text, _SPEAK_ASYNC)
                elif command == "status":
                    text.put(voice.Status.RunningState == _IS_SPEAKING)  # "text" holds the reply box here
                else:  # "stop"
                    voice.Speak("", _SPEAK_ASYNC | _PURGE)
            except Exception:
                pass  # a failed sentence should never crash the app

    def _choose_voice(self, voice) -> None:
        if not self._voice_wanted:
            return
        voices = voice.GetVoices()
        names = [voices.Item(i).GetDescription() for i in range(voices.Count)]
        for index, name in enumerate(names):
            if self._voice_wanted.lower() in name.lower():
                voice.Voice = voices.Item(index)
                return
        raise TtsError(
            f"No Windows voice matches '{self._voice_wanted}'. Installed voices: {', '.join(names)}. "
            "Check TRADO_VOICE in your .env."
        )
