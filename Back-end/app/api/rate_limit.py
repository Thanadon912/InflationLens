"""Bounded, thread-safe in-memory HTTP rate limiting for the Flask API.

Protects both cached read endpoints (GET/HEAD) and CPU-bound calculation
endpoints (POST) from single-client flooding while keeping memory usage
strictly bounded under spoofed-IP attacks.
"""

from __future__ import annotations

from collections import OrderedDict
import math
import os
import threading
import time
from typing import Callable

from flask import Flask, jsonify, request

DEFAULT_READ_LIMIT_PER_MINUTE = 600
DEFAULT_CALC_LIMIT_PER_MINUTE = 120
DEFAULT_WINDOW_SECONDS = 60.0
DEFAULT_MAX_CLIENTS = 4096


class SlidingWindowLimiter:
    """Thread-safe fixed/sliding window counter with LRU client eviction."""

    def __init__(
        self,
        *,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        max_clients: int = DEFAULT_MAX_CLIENTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window_seconds = float(window_seconds)
        self.max_clients = int(max_clients)
        self._clock = clock
        self._lock = threading.Lock()
        # Maps (bucket, client_id) -> (window_start, count)
        self._buckets: OrderedDict[tuple[str, str], tuple[float, int]] = OrderedDict()

    def check(self, bucket: str, client_id: str, limit: int) -> tuple[bool, int, int]:
        """Record a request and return ``(allowed, remaining, reset_seconds)``."""
        now = self._clock()
        key = (bucket, client_id)
        with self._lock:
            window_start, count = self._buckets.get(key, (now, 0))
            elapsed = now - window_start
            if elapsed >= self.window_seconds:
                window_start = now
                count = 0
                elapsed = 0.0

            reset_seconds = max(1, math.ceil(self.window_seconds - elapsed))
            if count >= limit:
                self._buckets.move_to_end(key)
                return False, 0, reset_seconds

            count += 1
            self._buckets[key] = (window_start, count)
            self._buckets.move_to_end(key)
            while len(self._buckets) > self.max_clients:
                self._buckets.popitem(last=False)

            remaining = max(0, limit - count)
            return True, remaining, reset_seconds

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


def _client_identifier(app: Flask) -> str:
    trust_proxy = app.config.get("TRUST_PROXY_HEADERS")
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For", "")
        first_hop = forwarded.split(",", 1)[0].strip()
        if first_hop:
            return first_hop
    return request.remote_addr or "local"


def register_rate_limiter(
    app: Flask,
    *,
    limiter: SlidingWindowLimiter | None = None,
) -> SlidingWindowLimiter:
    """Attach before/after request rate-limiting hooks to ``app``."""
    active_limiter = limiter or SlidingWindowLimiter(
        window_seconds=float(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS)),
        max_clients=int(os.environ.get("RATE_LIMIT_MAX_CLIENTS", DEFAULT_MAX_CLIENTS)),
    )
    app.extensions["rate_limiter"] = active_limiter

    app.config.setdefault(
        "RATE_LIMIT_ENABLED",
        os.environ.get("RATE_LIMIT_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"},
    )
    app.config.setdefault(
        "RATE_LIMIT_READ_PER_MINUTE",
        int(os.environ.get("RATE_LIMIT_READ_PER_MINUTE", DEFAULT_READ_LIMIT_PER_MINUTE)),
    )
    app.config.setdefault(
        "RATE_LIMIT_CALC_PER_MINUTE",
        int(os.environ.get("RATE_LIMIT_CALC_PER_MINUTE", DEFAULT_CALC_LIMIT_PER_MINUTE)),
    )
    app.config.setdefault(
        "TRUST_PROXY_HEADERS",
        os.environ.get("TRUST_PROXY_HEADERS", "0").strip().lower() in {"1", "true", "yes", "on"},
    )

    @app.before_request
    def _enforce_rate_limit():
        if not app.config.get("RATE_LIMIT_ENABLED", True):
            return None
        if request.method == "OPTIONS" or request.path.endswith("/health"):
            return None

        is_calc = request.method == "POST"
        bucket = "calc" if is_calc else "read"
        limit = int(
            app.config["RATE_LIMIT_CALC_PER_MINUTE"]
            if is_calc
            else app.config["RATE_LIMIT_READ_PER_MINUTE"]
        )
        client_id = _client_identifier(app)
        allowed, remaining, reset_seconds = active_limiter.check(bucket, client_id, limit)
        request.environ["lens.ratelimit"] = (limit, remaining, reset_seconds)
        if not allowed:
            response = jsonify({
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Rate limit exceeded; please retry later.",
                    "details": {
                        "bucket": bucket,
                        "limit": limit,
                        "window_seconds": int(active_limiter.window_seconds),
                        "retry_after_seconds": reset_seconds,
                    },
                }
            })
            response.status_code = 429
            response.headers["Retry-After"] = str(reset_seconds)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(reset_seconds)
            return response
        return None

    @app.after_request
    def _attach_rate_limit_headers(response):
        meta = request.environ.get("lens.ratelimit")
        if meta is not None:
            limit, remaining, reset_seconds = meta
            response.headers.setdefault("X-RateLimit-Limit", str(limit))
            response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
            response.headers.setdefault("X-RateLimit-Reset", str(reset_seconds))
        return response

    return active_limiter
