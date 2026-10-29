from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

_SYSTEM_RANDOM = secrets.SystemRandom()
_SENSITIVE_PARAM_KEYS = {"api_key", "apikey", "userid", "token", "access_token", "key"}
_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)\b(api_key|apikey|userid|token|access_token|key)=([^&\s'\"<>]+)"
)


class ProviderError(RuntimeError):
    pass


class ProviderSchemaError(ProviderError):
    pass


@dataclass(frozen=True)
class SourcePoint:
    mapping: dict[str, Any]
    period: str
    value: float
    is_estimated: bool = False
    is_revised: bool = False
    publication_date: str | None = None
    data_vintage: str | None = None
    provider_status: str | None = None


@dataclass(frozen=True)
class FetchBundle:
    provider: str
    request_url: str
    retrieved_at: str
    body: bytes
    content_type: str
    points: tuple[SourcePoint, ...]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, "REDACTED" if key.lower() in _SENSITIVE_PARAM_KEYS else value)
        for key, value in parse_qsl(parts.query)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def sanitize_text(text: str) -> str:
    """Redact credential query parameters inside arbitrary error messages or URLs."""
    return _SENSITIVE_TEXT_RE.sub(r"\1=REDACTED", text)


class ResilientClient:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        attempts: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.attempts = attempts
        self.sleep = sleep
        self.client = httpx.Client(timeout=timeout, follow_redirects=True, transport=transport)

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if urlsplit(url).scheme != "https":
            raise ProviderError("Refusing non-HTTPS provider URL")
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code not in {408, 429} and response.status_code < 500:
                    response.raise_for_status()
                    return response
                last_error = ProviderError(f"Provider returned retryable HTTP {response.status_code}")
                retry_after = response.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else (2**attempt + _SYSTEM_RANDOM.random())
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                delay = 2**attempt + _SYSTEM_RANDOM.random()
            except httpx.HTTPStatusError as exc:
                raise ProviderError(f"Provider returned HTTP {exc.response.status_code}") from exc
            if attempt + 1 < self.attempts:
                self.sleep(min(delay, 60.0))
        raise ProviderError(f"Provider request failed after {self.attempts} attempts") from last_error

    def close(self) -> None:
        self.client.close()


def json_bytes(response: httpx.Response) -> tuple[bytes, Any]:
    try:
        return response.content, response.json()
    except json.JSONDecodeError as exc:
        raise ProviderSchemaError("Provider response is not valid JSON") from exc
