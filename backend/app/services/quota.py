"""Rate-limit budgets for the market watchers.

Port of beast-trader's `quota.js`: sliding windows for per-minute provider
limits plus a monthly credit tracker for Helius. Counters are process-local
on purpose — a restart re-grants the allowance, which is surfaced rather than
hidden (`status()["in_memory_only"]`).

Budgets degrade instead of failing: `take()` returning False means "skip this
tick", never "raise".
"""
from __future__ import annotations

import time
from typing import Dict


class Window:
    """Sliding rate window: up to `limit` takes per `window_ms`."""

    __slots__ = ("window_ms", "limit", "_events")

    def __init__(self, window_ms: int, limit: int) -> None:
        self.window_ms = window_ms
        self.limit = limit
        self._events: list[float] = []

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_ms / 1000.0
        if self._events and self._events[0] < cutoff:
            self._events = [t for t in self._events if t >= cutoff]

    def take(self, n: int = 1) -> bool:
        now = time.monotonic()
        self._prune(now)
        if len(self._events) + n > self.limit:
            return False
        self._events.extend([now] * n)
        return True

    def used(self) -> int:
        self._prune(time.monotonic())
        return len(self._events)

    def remaining(self) -> int:
        return max(0, self.limit - self.used())


class Credits:
    """Monthly credit allowance on a fixed 30-day cycle."""

    __slots__ = ("monthly", "_cycle_start", "_spent")

    def __init__(self, monthly: int) -> None:
        self.monthly = monthly
        self._cycle_start = time.monotonic()
        self._spent = 0

    def _roll(self) -> None:
        if time.monotonic() - self._cycle_start > 30 * 86400:
            self._cycle_start = time.monotonic()
            self._spent = 0

    def spend(self, n: int) -> bool:
        self._roll()
        if self._spent + n > self.monthly:
            return False
        self._spent += n
        return True

    def remaining(self) -> int:
        self._roll()
        return max(0, self.monthly - self._spent)


# Provider limits (dexscreener: 300 req/min pairs → 280 usable, 60/min meta;
# helius: 10 standard req/s → 8 usable, 1,000,000 credits/month).
dexscreener_pairs = Window(60_000, 280)
dexscreener_meta = Window(60_000, 50)
helius_standard = Window(1_000, 8)
credits = Credits(1_000_000)

BUDGETS: Dict[str, Window] = {
    "dexscreener_pairs": dexscreener_pairs,
    "dexscreener_meta": dexscreener_meta,
    "helius_standard": helius_standard,
}

#: Helius charges 10 credits per enhanced-transactions call.
CREDITS_PER_HELIUS_CALL = 10


def status() -> dict:
    return {
        "in_memory_only": True,
        "dexscreener_pairs_remaining": dexscreener_pairs.remaining(),
        "dexscreener_pairs_limit": dexscreener_pairs.limit,
        "helius_standard_remaining": helius_standard.remaining(),
        "helius_standard_limit": helius_standard.limit,
        "credits_remaining": credits.remaining(),
        "credits_monthly": credits.monthly,
    }
