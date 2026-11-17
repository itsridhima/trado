"""Hold the hotkey, speak, release: Trado transcribes, looks at your screen, answers in text and out loud."""

import sys
import threading

from trado.audio import Recorder, is_too_quiet, list_input_devices
from trado.config import load_settings
from trado.hotkey import HoldToTalkHotkey, describe_hotkey
from trado.llm import LlmError, create_llm_provider
from trado.memory import ConversationMemory, is_forget_request, is_non_answer
from trado.privacy import redact_sensitive
from trado.pointing import PointTagFilter, describe_target, parse_point_tag, resolve_height_fix
from trado.screen import capture_screen, make_dpi_aware
from trado.screen_need import needs_screenshot
from trado.sensitive_page import PageGuard
from trado.stt import SttError, create_provider
from trado.textsafe import sanitize_message, strip_control
from trado.tts import NullSpeaker, TtsError, create_speaker
from trado.tts.text import SentenceSplitter, clean_for_speech


def _beep() -> None:
    """A tiny 'ready, you can talk' sound, so you don't start speaking before the mic is open."""
    try:
        import winsound

        winsound.Beep(1000, 70)
    except Exception:
        pass


def _print_where() -> None:
    """`python -m trado --where`: show where the settings come from. Prints no key and no private text."""
    import os
    from pathlib import Path

    from dotenv import dotenv_values

    from trado import config

    print("Trado settings check (nothing secret is shown)")
    print(f"  Python program:        {sys.executable}")
    print(f"  Trado code folder:     {Path(config.__file__).parent}")
    print(f"  TRADO_ENV_FILE set in Windows environment: {os.environ.get('TRADO_ENV_FILE') or 'no'}")
    print(f"  TRADO_HOTKEY set in Windows environment:   {os.environ.get('TRADO_HOTKEY') or 'no'}")
    for label, path in (("private settings file", config.private_env_path()), ("project .env file", config.PROJECT_ROOT / ".env")):
        if path and path.is_file():
            values = dotenv_values(path)
            print(f"  {label}: found at {path}")
            print(f"      TRADO_HOTKEY in it = {values.get('TRADO_HOTKEY')!r}, key filled in = {bool(values.get('GROQ_API_KEY'))}")
        else:
            print(f"  {label}: not found")
    settings = config.load_settings()
    print(f"  Settings file Trado actually uses: {settings.env_file or 'none'}")
    print(f"  Hotkey Trado will use: {describe_hotkey(settings.hotkey)}   (setting text: {settings.hotkey!r})")
    if settings.env_overrides:
        print(f"  Overridden by the Windows environment: {', '.join(settings.env_overrides)}")


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

    if "--where" in sys.argv:
        _print_where()
        return
    if "--set" in sys.argv:
        from trado.keysetup import set_setting

        position = sys.argv.index("--set")
        argument = sys.argv[position + 1] if position + 1 < len(sys.argv) else ""
        print(set_setting(argument))
        return
    if "--setup" in sys.argv:
        from trado.keysetup import run_setup

        run_setup()
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

    # Some AI models give an up-and-down pointer number that is too small by height/width. This was measured for the
    # default model with python -m tools.run_pointing_test, so the correction is applied only to models known to need it.
    height_fix = resolve_height_fix(settings.llm_model, settings.point_fix)
    page_guard = PageGuard(settings.sensitive_pages)
    memory = ConversationMemory(settings.memory_exchanges)  # recent questions and answers, text only, never saved

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
                    print(f"Sorry: {sanitize_message(str(err))}")
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
            question, hidden = redact_sensitive(strip_control(question))  # private-looking details never reach the AI
            if hidden:
                print("(I hid what looked like private details in your words before asking the AI. Please don't say them aloud.)")
            print(f'You said: "{question}"')

            if memory.max_exchanges and is_forget_request(question):
                memory.clear()
                reply = "Okay, I've forgotten our conversation."
                print(f"Trado: {reply}")
                speaker.say(reply)
                return

            image = None
            capture = None  # the screenshot plus where it came from, so a pointer position can become a real one
            if settings.send_screen:
                if settings.screen_mode == "auto" and not needs_screenshot(question, len(memory) > 0):
                    print("(This isn't about your screen, so no screenshot was sent. Say \"look at my screen\" to include one.)")
                else:
                    allowed, note = page_guard.check()  # may show a Yes/No box on login, KYC, bank or broker pages
                    if note:
                        print(note)
                    if not is_current(turn):
                        return
                    if allowed:
                        try:
                            capture = capture_screen(settings.screen_max_side)  # kept in memory only
                            image = capture.jpeg
                        except Exception as err:
                            print(f"(Couldn't capture the screen: {type(err).__name__}. Answering without it.)")

            print("Thinking...")
            started = False
            splitter = SentenceSplitter()
            shown_parts: list[str] = []  # exactly what you saw and heard, which is what gets remembered

            def emit(sentences: list[str]) -> None:
                """Show and speak finished sentences, after hiding anything that looks like private details."""
                nonlocal started
                for sentence in sentences:
                    if not is_current(turn):
                        return
                    shown, _ = redact_sensitive(strip_control(sentence))
                    print(("" if started else "Trado: ") + shown + " ", end="", flush=True)
                    started = True
                    shown_parts.append(shown)
                    spoken = clean_for_speech(shown)
                    if spoken:
                        speaker.say(spoken)

            tag_filter = PointTagFilter()  # hides the [POINT:...] tag from the screen, the voice and the memory
            try:
                for piece in llm.stream_answer(
                    question, image, memory.messages(),
                    cancelled=lambda: not is_current(turn),
                    image_size=capture.image_size if capture else None,
                ):
                    if not is_current(turn):
                        return  # you pressed the key again: stop quietly
                    emit(splitter.feed(tag_filter.feed(piece)))
                emit(splitter.feed(tag_filter.flush()))
                emit(splitter.flush())
                print()
                if settings.pointing != "off" and is_current(turn):
                    target = parse_point_tag(
                        tag_filter.tag, capture.geometry if capture else None, correct_height=height_fix
                    )
                    if target:
                        print(describe_target(target))
            except LlmError as err:
                if is_current(turn):
                    message = sanitize_message(str(err))
                    print(f"\nSorry: {message}" if started else f"Sorry: {message}")
            finally:
                spoken_answer = " ".join(shown_parts)
                # An interrupted answer is remembered (you heard that part), but "I didn't catch that" is not.
                if shown_parts and not is_non_answer(spoken_answer):
                    memory.add(question, spoken_answer)
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
    print("Educational only, not financial advice. For personal decisions, ask a SEBI-registered adviser.")
    print(f"Hold [{describe_hotkey(hotkey_spec)}] and speak after the beep. Release to ask. Press it again to stop Trado talking. Ctrl+C quits (or Ctrl+Break).")
    print(f"Speech: {settings.stt_model}   AI: {settings.llm_model}   Language: {settings.stt_language or 'auto-detect'}   {voice_note}")
    if settings.send_screen:
        if settings.screen_mode == "auto":
            print("Privacy: your voice is sent to Groq, and so is a screenshot of the screen under your mouse, but only")
            print("         when your question looks like it is about the screen (TRADO_SCREEN_MODE=always sends every time).")
        else:
            print("Privacy: your voice and a screenshot of the screen under your mouse are sent to Groq with every question.")
        print("         Groq's free plan may store this data or use it to improve its services (check Groq's terms;")
        print("         its Zero Data Retention setting is worth switching on). Close anything private first.")
        print("         Set TRADO_SEND_SCREEN=false to turn screenshots off.")
        guard_text = {"ask": "asks you first", "skip": "skips the screenshot", "send": "is OFF"}[settings.sensitive_pages]
        print(f"         Login, KYC, bank and broker pages: Trado {guard_text} (TRADO_SENSITIVE_PAGES=ask|skip|send).")
    else:
        print("Screenshots are OFF (TRADO_SEND_SCREEN=false). Only your question is sent.")
    if settings.pointing == "print":
        print("Pointing (early test): when your question is about something on the screen, Trado prints where it would")
        print("         point. There is no glowing cursor yet. Set TRADO_POINTING=off to hide those lines.")
        print(f"         Screenshots are sent {settings.screen_max_side} pixels wide; height correction for this model: "
              f"{'on' if height_fix else 'off'}.")
    if settings.memory_exchanges:
        print(f"Memory: Trado remembers your last {settings.memory_exchanges} questions while it is open, so follow-ups work.")
        print("        That text is sent to Groq with each new question. Say \"forget that\" to clear it. Never saved to disk.")
    else:
        print("Memory is OFF (TRADO_MEMORY=0): every question is answered on its own.")
    if settings.env_overrides:
        print(f"NOTE: {', '.join(settings.env_overrides)} come(s) from your Windows environment and override your settings file.")
        print("      To use the file instead, remove it from the environment (in PowerShell: Remove-Item Env:NAME).")
    if settings.env_file_synced:
        print("WARNING: your key file is inside a cloud-synced folder (such as OneDrive), so your key may be copied")
        print("         to the cloud. Run  python -m trado --setup  to keep it in a private local folder instead.")
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
