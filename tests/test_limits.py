"""Offline tests for the client-side rate limits (a fake clock is used, so nothing really waits)."""

import unittest
from unittest import mock

import httpx

from tests.test_groq_vision import FakeStream, sse
from trado.limits import Cancelled, LimitReached, RateLimiter, UsageCounter
from trado.llm.base import LlmRateLimitError
from trado.llm.groq_vision import GroqVisionProvider
from trado.stt.base import RateLimitError
from trado.stt.groq_whisper import GroqWhisperProvider


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def limiter(capacity, clock, max_wait=25.0):
    return RateLimiter(capacity, 60.0, "test", max_wait=max_wait, clock=clock, sleep=clock.sleep)


class RateLimiterTests(unittest.TestCase):
    def test_allows_up_to_capacity_then_waits_for_the_window(self):
        clock, told = FakeClock(), []
        lim = limiter(2, clock, max_wait=120)  # allow a full-minute wait for this test
        self.assertEqual(lim.acquire(notify=told.append), 0)
        self.assertEqual(lim.acquire(notify=told.append), 0)
        self.assertEqual(told, [])
        waited = lim.acquire(notify=told.append)  # third one has to wait for the first to expire
        self.assertAlmostEqual(waited, 60.0, delta=1.0)
        self.assertEqual(len(told), 1)  # told once, in plain words
        self.assertIn("free test limit", told[0])

    def test_a_wait_of_a_second_or_so_is_silent(self):
        clock, told = FakeClock(), []
        lim = limiter(1, clock)
        lim.acquire(notify=told.append)
        clock.now += 59.2  # only about a second short of the window
        lim.acquire(notify=told.append)
        self.assertEqual(told, [])  # no "waiting about 0 seconds" message
        self.assertGreater(sum(clock.slept), 0.5)  # but it still waited

    def test_a_wait_can_be_cancelled_and_stops_within_a_fraction_of_a_second(self):
        clock = FakeClock()
        lim = limiter(1, clock, max_wait=120)
        lim.acquire()
        checks = {"n": 0}

        def cancelled():
            checks["n"] += 1
            return checks["n"] > 3  # gives up shortly after the wait begins

        with self.assertRaises(Cancelled):
            lim.acquire(notify=lambda _m: None, cancelled=cancelled)
        self.assertLess(sum(clock.slept), 2.0)  # it did not sit out the whole minute

    def test_gives_up_instead_of_waiting_too_long(self):
        clock = FakeClock()
        lim = limiter(1, clock, max_wait=5)
        lim.acquire()
        with self.assertRaises(LimitReached) as ctx:
            lim.acquire()
        self.assertGreater(ctx.exception.wait_seconds, 5)
        self.assertEqual(clock.slept, [])  # it did not sit and wait

    def test_old_requests_expire(self):
        clock = FakeClock()
        lim = limiter(1, clock)
        lim.acquire()
        clock.now += 61
        self.assertEqual(lim.acquire(), 0)

    def test_a_request_bigger_than_the_whole_budget_still_gets_through_alone(self):
        clock = FakeClock()
        self.assertEqual(limiter(100, clock).acquire(5000), 0)

    def test_token_costs_add_up(self):
        clock = FakeClock()
        lim = limiter(7000, clock, max_wait=1)
        lim.acquire(3100)
        lim.acquire(3100)
        with self.assertRaises(LimitReached):
            lim.acquire(3100)  # a third screenshot inside the same minute would go over


class UsageCounterTests(unittest.TestCase):
    def test_warns_once_near_the_daily_limit(self):
        counter = UsageCounter(10, "things")
        notes = [counter.record() for _ in range(10)]
        self.assertEqual([i for i, n in enumerate(notes) if n], [7])  # on the 8th use (80%), and only once
        self.assertIn("about 10 a day", notes[7])


class ProviderIntegrationTests(unittest.TestCase):
    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_ai_provider_refuses_locally_instead_of_hammering_the_server(self, stream):
        stream.side_effect = lambda *a, **k: FakeStream(lines=sse("ok"))
        clock = FakeClock()
        provider = GroqVisionProvider("test-key", notify=lambda _m: None)
        provider._token_limiter = limiter(100, clock, max_wait=1)
        self.assertEqual("".join(provider.stream_answer("q", b"jpg")), "ok")
        with self.assertRaises(LlmRateLimitError):
            list(provider.stream_answer("q", b"jpg"))
        self.assertEqual(stream.call_count, 1)  # the second question never reached Groq

    def test_the_ai_provider_is_willing_to_wait_up_to_a_minute(self):
        provider = GroqVisionProvider("test-key", notify=lambda _m: None)
        self.assertEqual(provider._token_limiter.max_wait, 60.0)
        self.assertEqual(provider._request_limiter.max_wait, 60.0)

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_a_question_given_up_on_sends_nothing(self, stream):
        stream.side_effect = lambda *a, **k: FakeStream(lines=sse("ok"))
        provider = GroqVisionProvider("test-key", notify=lambda _m: None)
        self.assertEqual("".join(provider.stream_answer("q", None, None, lambda: True)), "")  # cancelled from the start
        self.assertEqual(stream.call_count, 0)

    @mock.patch("trado.llm.groq_vision.httpx.stream")
    def test_giving_up_during_a_long_wait_sends_nothing(self, stream):
        stream.side_effect = lambda *a, **k: FakeStream(lines=sse("ok"))
        clock = FakeClock()
        provider = GroqVisionProvider("test-key", notify=lambda _m: None)
        provider._token_limiter = limiter(100, clock, max_wait=120)
        list(provider.stream_answer("q", b"jpg"))  # uses up the budget
        asked = {"n": 0}

        def cancelled():
            asked["n"] += 1
            return asked["n"] > 4

        self.assertEqual("".join(provider.stream_answer("q", b"jpg", None, cancelled)), "")
        self.assertEqual(stream.call_count, 1)  # the second request was never sent

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_speech_provider_refuses_locally_too(self, post):
        post.return_value = httpx.Response(200, json={"text": "hello there"})
        clock = FakeClock()
        provider = GroqWhisperProvider("test-key")
        provider._limiter = limiter(1, clock, max_wait=1)
        self.assertEqual(provider.transcribe(b"wav"), "hello there")
        with self.assertRaises(RateLimitError):
            provider.transcribe(b"wav")
        self.assertEqual(post.call_count, 1)

    @mock.patch("trado.stt.groq_whisper.httpx.post")
    def test_normal_use_is_never_slowed(self, post):
        post.return_value = httpx.Response(200, json={"text": "hi"})
        provider = GroqWhisperProvider("test-key")
        for _ in range(10):
            provider.transcribe(b"wav")  # 10 quick questions: well inside 18 a minute
        self.assertEqual(post.call_count, 10)


if __name__ == "__main__":
    unittest.main()
