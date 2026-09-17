"""Minimal in-memory sliding-window rate limiter (single-instance)."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

_hits: dict[str, deque] = defaultdict(deque)


def hit(key: str, max_hits: int = 10, window: int = 300) -> None:
    now = time.time()
    dq = _hits[key]
    while dq and dq[0] < now - window:
        dq.popleft()
    if len(dq) >= max_hits:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many attempts — slow down and try again shortly")
    dq.append(now)
