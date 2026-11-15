"""Offline tests for the short conversation memory."""

import threading
import unittest

from trado.memory import MAX_ANSWER_CHARS, ConversationMemory, is_forget_request, is_non_answer


class MemoryTests(unittest.TestCase):
    def test_keeps_turns_in_order_in_the_shape_the_ai_expects(self):
        memory = ConversationMemory(5)
        memory.add("What is a SIP?", "A SIP invests a fixed amount regularly.")
        memory.add("And the minimum?", "Often 500 rupees a month.")
        self.assertEqual(
            memory.messages(),
            [
                {"role": "user", "content": "What is a SIP?"},
                {"role": "assistant", "content": "A SIP invests a fixed amount regularly."},
                {"role": "user", "content": "And the minimum?"},
                {"role": "assistant", "content": "Often 500 rupees a month."},
            ],
        )

    def test_only_the_last_few_are_kept(self):
        memory = ConversationMemory(3)
        for i in range(6):
            memory.add(f"question {i}", f"answer {i}")
        self.assertEqual(len(memory), 3)
        self.assertEqual(memory.messages()[0]["content"], "question 3")
        self.assertEqual(memory.messages()[-1]["content"], "answer 5")

    def test_zero_means_no_memory_at_all(self):
        memory = ConversationMemory(0)
        memory.add("q", "a")
        self.assertEqual(memory.messages(), [])
        self.assertEqual(len(memory), 0)

    def test_long_answers_are_trimmed_and_empty_ones_ignored(self):
        memory = ConversationMemory(2)
        memory.add("q", "x" * 5000)
        memory.add("", "an answer with no question")
        memory.add("a question with no answer", "   ")
        self.assertEqual(len(memory), 1)
        self.assertEqual(len(memory.messages()[1]["content"]), MAX_ANSWER_CHARS)

    def test_clear_forgets_everything(self):
        memory = ConversationMemory(5)
        memory.add("q", "a")
        memory.clear()
        self.assertEqual(memory.messages(), [])

    def test_messages_are_a_copy(self):
        memory = ConversationMemory(5)
        memory.add("q", "a")
        memory.messages().clear()
        self.assertEqual(len(memory.messages()), 2)

    def test_safe_when_several_threads_add_at_once(self):
        memory = ConversationMemory(4)
        threads = [threading.Thread(target=memory.add, args=(f"q{i}", f"a{i}")) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(memory), 4)


class NonAnswerTests(unittest.TestCase):
    def test_misses_are_recognised(self):
        for text in ["I didn't catch that. Could you please say your question again?",
                     "Sorry, I couldn't catch that.", "I did not catch that."]:
            self.assertTrue(is_non_answer(text), text)

    def test_real_answers_are_not_misses(self):
        for text in ["A SIP invests a fixed amount regularly.", "I can't recommend stocks.", ""]:
            self.assertFalse(is_non_answer(text), text)


class ForgetCommandTests(unittest.TestCase):
    def test_short_commands_are_recognised(self):
        for text in ["Forget that.", "forget everything", "Clear the memory", "Start over", "New topic please",
                     "Reset the conversation.", "Let's start again"]:
            self.assertTrue(is_forget_request(text), text)

    def test_real_questions_that_happen_to_contain_the_words_are_not_commands(self):
        for text in [
            "How do I start over after losing money on a trade in the stock market?",
            "Why do people say forget that rule about buying only on dips when investing for the long term?",
            "What is a SIP?",
            "",
        ]:
            self.assertFalse(is_forget_request(text), text)


if __name__ == "__main__":
    unittest.main()
