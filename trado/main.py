"""Hold the hotkey, speak, release: Trado transcribes, looks at your screen, answers in text and out loud."""

import sys
import threading

from trado.audio import Recorder, is_too_quiet, list_input_devices
from trado.config import load_settings
from trado.hotkey import HoldToTalkHotkey
from trado.llm import LlmError, create_llm_provider
from trado.screen import capture_screen_jpeg, make_dpi_aware
from trado.stt import SttError, create_provider
from trado.tts import NullSpeaker, TtsError, create_speaker
from trado.tts.text import SentenceSplitter, clean_for_speech


def _beep() -> None:
    """A tiny 'ready, you can talk' sound, so you don't start speaking before the mic is open."""
    try:
        import winsound

        winsound.Beep(1000, 70)
    except Exception:
        pass


def main() -> None:
    if "--mics" in sys.argv:
        print("Microphones Trado can use (put the number or part of the name in TRADO_MIC_DEVICE):")
        for index, name in list_input_devices():
            print(f"  {index}: {name}")
        return
    if "--voices" in sys.argv:
        from trado.tts.windows_sapi import list_voices

        print("Voices Trado can use (put part of the name in TRADO_VOICE):")
        for name in list_voices():
            print(f"  {name}")
        return

    make_dpi_aware()
    settings = load_settings()

    try:
        stt = create_provider(settings)
        llm = create_llm_provider(settings)
        recorder = Recorder(settings.mic_device)
        hotkey_spec = settings.hotkey
    except (SttError, LlmError, ValueError) as err:
        print(f"Setup problem: {err}")
        return

    try:
        speaker = create_speaker(settings)
    except TtsError as err:
        print(f"Voice problem: {err}\n  Carrying on with text only.")
        speaker = NullSpeaker()

    # Each press of the hotkey starts a new "turn". Work belonging to an older turn
    # quietly stops itself, which is how pressing the key interrupts Trado.
    turn_lock = threading.Lock()
    current_turn = [0]
    working = [False]  # True while an answer is being fetched or written
    interrupting = [False]  # True if the last key press interrupted Trado

    def is_current(turn: int) -> bool:
        return turn == current_turn[0]

    def handle_question(wav: bytes, turn: int, seconds: float, peak: float, note: str) -> None:
        working[0] = True
        try:
            print(f"  (recorded {seconds:.1f}s, {note})")
            if is_too_quiet(peak):
                print("(I barely heard anything, so I didn't send it. Speak closer to the mic or raise its volume.)")
                return
            print("Transcribing...")
            try:
                question = stt.transcribe(wav)
            except SttError as err:
                if is_current(turn):
                    print(f"Sorry: {err}")
                return
            if not is_current(turn):
                return
            if settings.debug:
                confidence = getattr(stt, "last_confidence", None)
                if confidence is not None:
                    print(f"  [debug] speech confidence {confidence:.2f} (closer to 0 is better; below -1.0 is rejected)")
            if not question:
                print("(I didn't catch any words.)")
                return
            print(f'You said: "{question}"')

            image = None
            if settings.send_screen:
                try:
                    image = capture_screen_jpeg()  # kept in memory only
                except Exception as err:
                    print(f"(Couldn't capture the screen: {type(err).__name__}. Answering without it.)")

            print("Thinking...")
            started = False
            splitter = SentenceSplitter()

            def speak(sentences: list[str]) -> None:
                for sentence in sentences:
                    spoken = clean_for_speech(sentence)
                    if spoken and is_current(turn):
                        speaker.say(spoken)

            try:
                for piece in llm.stream_answer(question, image):
                    if not is_current(turn):
                        return  # you pressed the key again: stop quietly
                    if not started:
                        print("Trado: ", end="", flush=True)
                        started = True
                    print(piece, end="", flush=True)
                    speak(splitter.feed(piece))
                speak(splitter.flush())
                print()
            except LlmError as err:
                if is_current(turn):
                    print(f"\nSorry: {err}" if started else f"Sorry: {err}")
        except Exception as err:  # never let one bad request kill the app
            if is_current(turn):
                print(f"\nUnexpected error ({type(err).__name__}). Please try again.")
        finally:
            if is_current(turn):
                working[0] = False

    def on_press() -> None:
        with turn_lock:
            interrupting[0] = working[0] or speaker.is_speaking()
            working[0] = False
            current_turn[0] += 1  # cancels any answer still being written or spoken
        speaker.stop()
        try:
            if settings.beep:
                _beep()
            recorder.start()
            print("Listening... (release the key when done)")
        except Exception as err:
            print(f"Could not open the microphone: {err}")

    def on_release() -> None:
        wav = recorder.stop()
        if wav is None:
            print("(Stopped.)" if interrupting[0] else "(Too short, hold the key while you speak.)")
            interrupting[0] = False
            return
        interrupting[0] = False
        with turn_lock:
            turn = current_turn[0]
        info = (recorder.last_seconds, recorder.last_peak, recorder.volume_note())
        threading.Thread(target=handle_question, args=(wav, turn, *info), daemon=True).start()

    try:
        hotkey = HoldToTalkHotkey(hotkey_spec, on_press, on_release)
    except ValueError as err:
        print(f"Setup problem: {err}")
        return

    voice_note = "text only" if isinstance(speaker, NullSpeaker) else f"voice: {settings.tts_voice or 'Windows default'}"
    print("Trado (Round 1: talk, see your screen, answer out loud)")
    print(f"Hold [{hotkey_spec.upper()}] and speak after the beep. Release to ask. Press it again to stop Trado talking. Ctrl+C quits (or Ctrl+Break).")
    print(f"Speech: {settings.stt_model}   AI: {settings.llm_model}   Language: {settings.stt_language or 'auto-detect'}   {voice_note}")
    if settings.send_screen:
        print("Privacy: your voice and a screenshot of the screen under your mouse are sent to Groq.")
        print("         Close anything private first. Set TRADO_SEND_SCREEN=false to turn screenshots off.")
    else:
        print("Screenshots are OFF (TRADO_SEND_SCREEN=false). Only your question is sent.")
    hotkey.start()
    try:
        while hotkey.is_alive():
            hotkey.wait(0.3)  # short waits, so Ctrl+C is noticed within a fraction of a second
    except KeyboardInterrupt:
        print("\nBye!")
        speaker.stop()
        hotkey.stop()


if __name__ == "__main__":
    main()
