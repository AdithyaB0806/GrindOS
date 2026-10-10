"""
Backend/ratelimit.py

Small in-memory sliding-window limiter. It is per process, which is right for a
single-instance deploy; if you ever run several workers or instances, swap
SlidingWindow for Redis.
"""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from Backend.models import User


class SlidingWindow:
    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key, limit: int, window: float) -> int:
        """Record a hit. Returns 0 if allowed, else seconds until a slot frees up."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return int(window - (now - hits[0])) + 1
            hits.append(now)
            if len(self._hits) > 20000:  # keep memory bounded
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > window]:
                    self._hits.pop(k, None)
            return 0

    def count(self, key, window: float) -> int:
        """How many hits are inside the window, without recording a new one."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.get(key)
            if not hits:
                return 0
            while hits and now - hits[0] > window:
                hits.popleft()
            return len(hits)

    def add(self, key) -> None:
        with self._lock:
            self._hits[key].append(time.monotonic())

    def reset(self, key) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self):
        with self._lock:
            self._hits.clear()


limiter = SlidingWindow()


def _too_many(wait: int, message: str) -> HTTPException:
    return HTTPException(status_code=429, detail=message, headers={"Retry-After": str(wait)})


def _minutes(seconds: int) -> int:
    return max(1, round(seconds / 60))


def spend_ai_budget(user: User) -> None:
    """
    Shared hourly budget for every AI feature, per user. Call it right before
    an AI call, so cached results that don't cost anything don't use it up.
    """
    limit = int(os.getenv("AI_RATE_LIMIT", "60"))
    wait = limiter.check(("ai", user.id), limit, 3600)
    if wait:
        raise _too_many(
            wait,
            f"You've used the hourly limit for AI features. Try again in about {_minutes(wait)} minutes.",
        )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


LOGIN_WINDOW = 600  # seconds


def login_rate_limit(request: Request, email: str) -> None:
    """
    Call before checking a password. Only FAILED sign-ins count (see
    record_login_failure), so using several devices never locks you out;
    guessing does.
    """
    attempts = int(os.getenv("LOGIN_ATTEMPTS", "8"))
    if (
        limiter.count(("login-email", email), LOGIN_WINDOW) >= attempts
        or limiter.count(("login-ip", _client_ip(request)), LOGIN_WINDOW) >= attempts * 5
    ):
        raise _too_many(
            LOGIN_WINDOW,
            f"Too many failed sign-ins. Try again in about {_minutes(LOGIN_WINDOW)} minutes.",
        )


def record_login_failure(request: Request, email: str) -> None:
    limiter.add(("login-email", email))
    limiter.add(("login-ip", _client_ip(request)))


def clear_login_failures(email: str) -> None:
    limiter.reset(("login-email", email))


def register_rate_limit(request: Request):
    wait = limiter.check(("register-ip", _client_ip(request)), int(os.getenv("REGISTER_LIMIT", "10")), 3600)
    if wait:
        raise _too_many(wait, "Too many accounts created from this network. Try again later.")