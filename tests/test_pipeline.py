"""End-to-end tests of Trado's flow, using the real main() with a fake microphone, speech, AI and voice.

Nothing touches the network, the microphone, the screen or the keyboard.
"""

import contextlib
import io
import os
import sys
import threading
import time
import unittest
from unittest import mock

from trado import config
from trado import main as trado_main
from trado.llm.base import LlmError
from trado.screen import Capture

FAKE_KEY = "gsk_FAKE0123456789abcdefghijklmnop"


class FakeRecorder:
    last_seconds, last_peak = 2.0, 0.5

    def __init__(self, device=""):
        pass

    def start(self):
        pass

    def stop(self):
        return b"wav"

    def volume_note(self):
        return "volume OK"


class FakeHotkey:
    instance = None

    def __init__(self, spec, on_press, on_release):
        self.on_press, self.on_release = on_press, on_release
        FakeHotkey.instance = self

    def start(self):
        pass

    def is_alive(self):
        return False  # lets main() return straight away, leaving the callbacks for the test to use

    def wait(self, seconds):
        pass

    def stop(self):
        pass


class FakeSpeaker:
    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)

    def stop(self):
        pass

    def is_speaking(self):
        return False


class FakeStt:
    def __init__(self, questions):
        self.questions, self.last_confidence = list(questions), None

    def transcribe(self, wav):
        return self.questions.pop(0)


class FakeLlm:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def stream_answer(self, question, image_jpeg=None, history=None, cancelled=None, image_size=None):
        self.calls.append({"question": question, "image": image_jpeg, "history": list(history or []),
                           "cancelled": cancelled, "image_size": image_size})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        yield from step()


def says(*chunks):
    return lambda: iter(chunks)


class Harness:
    def __init__(self, questions, script, memory=5, screenshots=False, screen_mode="auto", pointing="print",
                 point_fix="none", model=""):
        env = {"GROQ_API_KEY": FAKE_KEY, "TRADO_MEMORY": str(memory), "TRADO_TTS": "off",
               "TRADO_SEND_SCREEN": "true" if screenshots else "false", "TRADO_SCREEN_MODE": screen_mode,
               "TRADO_POINTING": pointing, "TRADO_POINT_FIX": point_fix, "TRADO_LLM_MODEL": model}
        self.guard = mock.Mock(check=mock.Mock(return_value=(True, "")))  # stands in for the sensitive-page check
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("trado.config.find_env_file", return_value=None):
            self.settings = config.load_settings()
        self.stt, self.llm, self.speaker = FakeStt(questions), FakeLlm(script), FakeSpeaker()
        self.out = io.StringIO()
        self._stack = contextlib.ExitStack()

    def __enter__(self):
        patches = {
            "load_settings": mock.Mock(return_value=self.settings),
            "create_provider": mock.Mock(return_value=self.stt),
            "create_llm_provider": mock.Mock(return_value=self.llm),
            "create_speaker": mock.Mock(return_value=self.speaker),
            "Recorder": FakeRecorder,
            "HoldToTalkHotkey": FakeHotkey,
            "make_dpi_aware": mock.Mock(),
            # a 1920x1200 monitor whose screenshot was shrunk to 1568x980 before it was sent
            "capture_screen": mock.Mock(return_value=Capture(b"screenshot-bytes", (1568, 980), (0, 0, 1920, 1200))),
            "PageGuard": mock.Mock(return_value=self.guard),
            "_beep": mock.Mock(),
        }
        for name, replacement in patches.items():
            self._stack.enter_context(mock.patch.object(trado_main, name, replacement))
        self._stack.enter_context(mock.patch.object(sys, "argv", ["trado"]))
        self._stack.enter_context(contextlib.redirect_stdout(self.out))
        trado_main.main()
        return self

    def __exit__(self, *exc):
        self._stack.close()

    def release(self):
        """Release the hotkey (a question is asked) and wait for the answer to finish."""
        before = threading.active_count()
        FakeHotkey.instance.on_release()
        deadline = time.time() + 5
        while threading.active_count() > before and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.02)

    def ask(self):
        FakeHotkey.instance.on_press()
        self.release()

    @property
    def text(self):
        return self.out.getvalue()


class MemoryFlowTests(unittest.TestCase):
    def test_a_follow_up_receives_the_earlier_turn(self):
        with Harness(["What is a SIP?", "And the minimum?"], [
            says("A SIP invests a fixed amount regularly. ", "It is popular in India."),
            says("Often about five hundred rupees a month."),
        ]) as t:
            t.ask()
            t.ask()
        first, second = t.llm.calls
        self.assertEqual(first["history"], [])
        self.assertEqual([m["role"] for m in second["history"]], ["user", "assistant"])
        self.assertEqual(second["history"][0]["content"], "What is a SIP?")
        self.assertIn("A SIP invests a fixed amount regularly.", second["history"][1]["content"])
        self.assertIn("It is popular in India.", second["history"][1]["content"])
        self.assertIn("Memory: Trado remembers your last 5 questions", t.text)

    def test_only_the_most_recent_exchanges_are_kept(self):
        with Harness([f"question {i}" for i in range(4)], [says(f"answer number {i} is here for you.") for i in range(4)], memory=2) as t:
            for _ in range(4):
                t.ask()
        last = t.llm.calls[-1]["history"]
        self.assertEqual([m["content"] for m in last if m["role"] == "user"], ["question 1", "question 2"])

    def test_forget_that_clears_memory_without_asking_the_ai(self):
        with Harness(["What is a SIP?", "Forget that.", "What is a P E ratio?"], [
            says("A SIP invests a fixed amount regularly."),
            says("The P E ratio compares price with earnings."),
        ]) as t:
            t.ask()
            t.ask()  # "Forget that."
            t.ask()
        self.assertEqual(len(t.llm.calls), 2)  # the forget command never went to the AI
        self.assertIn("forgotten our conversation", t.text)
        self.assertTrue(any("forgotten" in s for s in t.speaker.said))
        self.assertEqual(t.llm.calls[1]["history"], [])  # and the third question starts fresh

    def test_memory_off_means_no_history_and_forget_is_just_a_question(self):
        with Harness(["What is a SIP?", "Forget that."], [says("A SIP invests regularly."), says("Okay.")], memory=0) as t:
            t.ask()
            t.ask()
        self.assertEqual([c["history"] for c in t.llm.calls], [[], []])
        self.assertIn("Memory is OFF", t.text)
        self.assertEqual(len(t.llm.calls), 2)

    def test_private_details_are_hidden_before_they_are_sent_or_remembered(self):
        with Harness(["My PAN is ABCDE1234F, what is it for?", "And why does it matter?"], [
            says("I see ABCDE1234F on your screen, keep it private please. "),
            says("It identifies you to the tax department."),
        ]) as t:
            t.ask()
            t.ask()
        everything_the_ai_saw = str(t.llm.calls)
        self.assertNotIn("ABCDE1234F", everything_the_ai_saw)
        self.assertIn("[hidden PAN]", t.llm.calls[0]["question"])
        self.assertNotIn("ABCDE1234F", t.text)  # nor was it shown on screen
        self.assertNotIn("ABCDE1234F", " ".join(t.speaker.said))  # nor spoken

    def test_an_interrupted_answer_is_remembered_up_to_what_you_heard(self):
        def interrupted():
            yield "First sentence of the answer is here. Second sentence begins "
            FakeHotkey.instance.on_press()  # you press the hotkey again in the middle of the answer
            yield "this part must never be shown or remembered. "

        with Harness(["Tell me about SIPs", "What did you mean?"], [interrupted, says("I meant regular investing.")]) as t:
            FakeHotkey.instance.on_press()
            t.release()
            t.release()  # the follow-up question, asked right after the interruption
        history = t.llm.calls[1]["history"]
        self.assertEqual(history[1]["content"], "First sentence of the answer is here.")
        self.assertNotIn("must never be shown", t.text)

    def test_i_didnt_catch_that_is_not_remembered(self):
        with Harness(["Mumble mumble", "What is a SIP?"], [
            says("I didn't catch that. Could you please say your question again?"),
            says("A SIP invests regularly."),
        ]) as t:
            t.ask()
            t.ask()
        self.assertEqual(t.llm.calls[1]["history"], [])  # the useless exchange did not pollute the memory

    def test_the_ai_is_told_when_the_user_gives_up_on_a_waiting_question(self):
        seen = {}

        def answer():
            seen["cancelled_before"] = t.llm.calls[0]["cancelled"]()
            FakeHotkey.instance.on_press()  # press the hotkey again
            seen["cancelled_after"] = t.llm.calls[0]["cancelled"]()
            yield "Unused. "

        with Harness(["What is a SIP?"], [answer]) as t:
            FakeHotkey.instance.on_press()
            t.release()
        self.assertFalse(seen["cancelled_before"])
        self.assertTrue(seen["cancelled_after"])  # this is how a pending wait learns it should stop

    def test_a_failed_request_is_not_remembered(self):
        with Harness(["What is a SIP?", "Try again"], [LlmError("Groq had a problem on its side (error 503). Try again soon."),
                                                      says("A SIP invests regularly.")]) as t:
            t.ask()
            t.ask()
        self.assertEqual(t.llm.calls[1]["history"], [])
        self.assertIn("Sorry: Groq had a problem", t.text)

    def test_the_screenshot_is_only_sent_with_the_newest_question(self):
        with Harness(["What is on my screen?", "What does this mean now?"], [says("A chart of Nifty."), says("Still the chart.")], screenshots=True) as t:
            t.ask()
            t.ask()
        for call in t.llm.calls:
            self.assertEqual(call["image"], b"screenshot-bytes")
            self.assertTrue(all(isinstance(m["content"], str) for m in call["history"]))  # remembered turns have no pictures

    def test_general_questions_send_no_screenshot_and_show_no_private_page_box(self):
        with Harness(["What is a SIP?", "What am I looking at?"], [says("A SIP invests regularly."), says("A chart.")], screenshots=True) as t:
            t.ask()
            t.ask()
        self.assertIsNone(t.llm.calls[0]["image"])  # general knowledge: nothing about the screen was sent
        self.assertEqual(t.llm.calls[1]["image"], b"screenshot-bytes")  # a screen question gets one
        self.assertEqual(t.guard.check.call_count, 1)  # the private-page box was only consulted when a screenshot was due
        self.assertIn("This isn't about your screen", t.text)

    def test_always_mode_sends_a_screenshot_with_every_question(self):
        with Harness(["What is a SIP?"], [says("A SIP invests regularly.")], screenshots=True, screen_mode="always") as t:
            t.ask()
        self.assertEqual(t.llm.calls[0]["image"], b"screenshot-bytes")
        self.assertNotIn("This isn't about your screen", t.text)

    def test_screenshots_off_still_means_off(self):
        with Harness(["What am I looking at?"], [says("I can't see your screen.")], screenshots=False) as t:
            t.ask()
        self.assertIsNone(t.llm.calls[0]["image"])
        self.assertEqual(t.guard.check.call_count, 0)

class PointingFlowTests(unittest.TestCase):
    QUESTION = "What does this box on my screen do?"  # mentions the screen, so a screenshot is sent

    def run_one(self, answer_chunks, pointing="print", screenshots=True):
        with Harness([self.QUESTION], [says(*answer_chunks)], screenshots=screenshots, pointing=pointing) as t:
            t.ask()
        return t

    def test_the_tag_is_hidden_and_the_position_is_printed(self):
        t = self.run_one(["This box is where you type how many shares. ", "[POINT:784,490:Quantity box]"])
        self.assertNotIn("[POINT", t.text)  # not on screen
        self.assertNotIn("POINT", " ".join(t.speaker.said))  # not spoken
        self.assertIn("This box is where you type how many shares.", t.text)
        self.assertIn('Would point at screen position (960, 600) "Quantity box"', t.text)  # 1568x980 picture -> 1920x1200 monitor

    def test_the_tag_is_hidden_even_when_it_arrives_in_tiny_pieces(self):
        text = "It sets the quantity. [POINT:784,490:Quantity box]"
        t = self.run_one([text[i:i + 3] for i in range(0, len(text), 3)])
        self.assertNotIn("[POINT", t.text)
        self.assertNotIn("POINT", " ".join(t.speaker.said))
        self.assertIn("(960, 600)", t.text)

    def test_none_junk_and_unfinished_tags_print_nothing(self):
        for tag in ["[POINT:none]", "[POINT:abc,def:x]", "[POINT:5000000,3:big]", "[POINT:10,20:Thing", "[POINT:-5,10:neg]"]:
            t = self.run_one(["Nothing specific here. ", tag])
            self.assertNotIn("Would point", t.text, tag)
            self.assertNotIn("POINT", " ".join(t.speaker.said), tag)

    def test_an_off_screen_position_is_pulled_back_onto_the_screen(self):
        t = self.run_one(["Down in the corner. ", "[POINT:99999,99999:Corner]"])
        self.assertIn("(1919, 1199)", t.text)  # the last real pixel, never beyond it

    def test_no_screenshot_means_no_pointing_but_the_tag_is_still_hidden(self):
        with Harness(["What is a SIP?"], [says("A SIP invests regularly. ", "[POINT:100,100:Something]")], screenshots=True) as t:
            t.ask()
        self.assertNotIn("Would point", t.text)
        self.assertNotIn("[POINT", t.text)
        self.assertIsNone(t.llm.calls[0]["image_size"])

    def test_pointing_off_hides_the_tag_and_prints_nothing(self):
        t = self.run_one(["This is the box. ", "[POINT:784,490:Quantity box]"], pointing="off")
        self.assertNotIn("Would point", t.text)
        self.assertNotIn("[POINT", t.text)

    def run_with(self, tag, **settings):
        with Harness([self.QUESTION], [says("This is the box. ", tag)], screenshots=True, **settings) as t:
            t.ask()
        return t

    def test_the_height_correction_is_applied_for_the_default_model_in_auto_mode(self):
        # The AI's up-and-down number (490) is too small by height/width = 980/1568. 490 * 1.6 = 784, the true row.
        t = self.run_with("[POINT:784,490:Quantity box]", point_fix="auto", model="qwen/qwen3.8-27b")
        self.assertIn("(960, 960)", t.text)  # x unchanged (784 -> 960); y corrected (784 of 980 -> 960 of 1200)
        self.assertIn("height correction for this model: on", t.text)

    def test_no_correction_for_an_unknown_model_in_auto_mode(self):
        t = self.run_with("[POINT:784,490:Quantity box]", point_fix="auto", model="some/other-model")
        self.assertIn("(960, 600)", t.text)
        self.assertIn("height correction for this model: off", t.text)

    def test_the_correction_can_be_forced_on_or_off(self):
        self.assertIn("(960, 960)", self.run_with("[POINT:784,490:Box]", point_fix="aspect", model="some/other-model").text)
        self.assertIn("(960, 600)", self.run_with("[POINT:784,490:Box]", point_fix="none", model="qwen/qwen3.8-27b").text)

    def test_a_corrected_position_that_runs_off_the_picture_is_still_pulled_back(self):
        t = self.run_with("[POINT:500,900:Low]", point_fix="aspect")  # 900 * 1.6 = 1440, beyond the 980-tall picture
        self.assertIn("(", t.text.split("Would point at screen position")[1])
        self.assertIn("1199)", t.text)  # clamped onto the last real row of the monitor

    def test_the_ai_is_told_the_size_of_the_picture(self):
        t = self.run_one(["Fine. ", "[POINT:none]"])
        self.assertEqual(t.llm.calls[0]["image_size"], (1568, 980))

    def test_the_tag_never_gets_into_memory(self):
        with Harness([self.QUESTION, "Explain that more simply."], [
            says("This is the box for shares. ", "[POINT:784,490:Quantity box]"),
            says("It is where you type the number. ", "[POINT:none]"),
        ], screenshots=True) as t:
            t.ask()
            t.ask()
        remembered = " ".join(m["content"] for m in t.llm.calls[1]["history"])
        self.assertIn("This is the box for shares.", remembered)
        self.assertNotIn("POINT", remembered)

    def test_an_interrupted_answer_prints_no_pointing(self):
        def interrupted():
            yield "The box is right here, and it matters a lot. Another sentence starts "
            FakeHotkey.instance.on_press()  # you press the hotkey before the answer ends
            yield "[POINT:784,490:Quantity box]"

        with Harness([self.QUESTION], [interrupted], screenshots=True) as t:
            FakeHotkey.instance.on_press()
            t.release()
        self.assertNotIn("Would point", t.text)


class MoreFlowTests(unittest.TestCase):
    def test_the_key_never_appears_in_anything_printed(self):
        with Harness(["What is a SIP?"], [says("A SIP invests regularly.")]) as t:
            t.ask()
        self.assertNotIn(FAKE_KEY, t.text)


if __name__ == "__main__":
    unittest.main()
