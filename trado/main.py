"""Slice 1: hold the hotkey, speak, release, and the transcribed text is printed."""

import threading

from trado.audio import Recorder
from trado.config import load_settings
from trado.hotkey import HoldToTalkHotkey
from trado.stt import SttError, create_provider


def main() -> None:
    settings = load_settings()

    try:
        provider = create_provider(settings)
        hotkey_parts = settings.hotkey
        recorder = Recorder()
    except (SttError, ValueError) as err:
        print(f"Setup problem: {err}")
        return

    busy = threading.Lock()  # one transcription at a time

    def transcribe_in_background(wav: bytes) -> None:
        with busy:
            print("Transcribing...")
            try:
                text = provider.transcribe(wav)
            except SttError as err:
                print(f"Sorry: {err}")
                return
            except Exception as err:  # never let one bad request kill the app
                print(f"Unexpected error ({type(err).__name__}). Please try again.")
                return
            print(f'You said: "{text}"' if text else "(I didn't catch any words.)")

    def on_press() -> None:
        try:
            recorder.start()
            print("Listening... (release the key when done)")
        except Exception as err:
            print(f"Could not open the microphone: {err}")

    def on_release() -> None:
        wav = recorder.stop()
        if wav is None:
            print("(Too short, hold the key while you speak.)")
            return
        threading.Thread(target=transcribe_in_background, args=(wav,), daemon=True).start()

    try:
        hotkey = HoldToTalkHotkey(hotkey_parts, on_press, on_release)
    except ValueError as err:
        print(f"Setup problem: {err}")
        return

    print("Trado (Slice 1: speech to text)")
    print(f"Hold [{hotkey_parts.upper()}] and speak. Release to transcribe. Press Ctrl+C to quit.")
    hotkey.start()
    try:
        hotkey.join()
    except KeyboardInterrupt:
        print("\nBye!")
        hotkey.stop()


if __name__ == "__main__":
    main()
