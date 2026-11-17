"""Client-side limits that mirror Groq's free plan, so Trado slows itself down before the server has to say no.

The numbers are a little below Groq's published free limits and are estimates: Groq's own answers (HTTP 429)
are still handled separately. Daily totals are only counted while Trado is open.
"""

import threading
import time
from collections import deque
from typing import Callable


class LimitReached(Exception):
    """Staying inside the limit would mean waiting too long. `wait_seconds` says how long."""

    def __init__(self, wait_seconds: float):
        super().__init__(f"would have to wait {wait_seconds:.0f}s")
        self.wait_seconds = wait_seconds


class Cancelled(Exception):
    """The question was given up on (the hotkey was pressed again) while waiting for the free limit."""


class RateLimiter:
    """Allows at most `capacity` units in any `window` seconds; waits (briefly) when full."""

    def __init__(
        self,
        capacity: float,
        window: float = 60.0,
        label: str = "request",
        max_wait: float = 25.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.capacity, self.window, self.label, self.max_wait = capacity, window, label, max_wait
        self._clock, self._sleep = clock, sleep
        self._events: deque[tuple[float, float]] = deque()  # (when, how much)
        self._lock = threading.Lock()

    def _wait_needed(self, cost: float, now: float) -> float:
        while self._events and now - self._events[0][0] >= self.window:
            self._events.popleft()
        used = sum(c for _, c in self._events)
        if used + cost <= self.capacity:
            return 0.0
        needed, freed = used + cost - self.capacity, 0.0
        for when, c in self._events:
            freed += c
            if freed >= needed:
                return max(0.0, when + self.window - now)
        return self.window

    def acquire(
        self, cost: float = 1.0, notify: Callable[[str], None] = print, cancelled: Callable[[], bool] | None = None
    ) -> float:
        """Reserve `cost` units, waiting if needed. Returns seconds waited.

        Raises LimitReached if the wait would be too long, and Cancelled if `cancelled()` becomes true while waiting
        (for example you pressed the hotkey again), so a question you gave up on doesn't spend your free allowance."""
        cost = min(cost, self.capacity)
        waited, told = 0.0, False
        while True:
            if cancelled and cancelled():
                raise Cancelled()
            with self._lock:
                now = self._clock()
                wait = self._wait_needed(cost, now)
                if wait <= 0:
                    self._events.append((now, cost))
                    return waited
            if waited + wait > self.max_wait:
                raise LimitReached(wait)
            if not told and wait >= 2:  # a wait of a second or so isn't worth a message
                notify(f"  (Staying inside Groq's free {self.label} limit: waiting about {wait:.0f} seconds...)")
                told = True
            remaining = wait + 0.05
            while remaining > 0:  # sleep in short slices so a cancel is noticed quickly
                step = min(0.25, remaining)
                self._sleep(step)
                remaining -= step
                if cancelled and cancelled():
                    raise Cancelled()
            waited += wait + 0.05


class UsageCounter:
    """Counts requests this session and gives one friendly warning when the daily free limit is getting close."""

    def __init__(self, daily_limit: int, what: str, warn_at: float = 0.8):
        self.daily_limit, self.what, self.warn_at = daily_limit, what, warn_at
        self.count = 0
        self._warned = False

    def record(self, amount: int = 1) -> str | None:
        """Add `amount` (1 request, or an estimate of tokens). Returns a warning the first time 80% is passed."""
        self.count += amount
        if not self._warned and self.count >= self.daily_limit * self.warn_at:
            self._warned = True
            return (
                f"  (Heads up: about {self.count:,} {self.what} used this session. Groq's free plan allows about "
                f"{self.daily_limit:,} a day, so Trado may soon ask you to wait until tomorrow.)"
            )
        return None
