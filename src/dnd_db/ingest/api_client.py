"""REST API client for SRD data."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

from dnd_db.config import get_api_base_url
from dnd_db.ingest.errors import ApiConfigError, ApiDecodeError, ApiHttpError

TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _normalize_path(path: str) -> str:
    if not path:
        raise ApiConfigError("Path cannot be empty.")
    if not path.startswith("/"):
        return f"/{path}"
    return path


def _join_url(base_url: str, path: str) -> str:
    return f"{_normalize_base_url(base_url)}{_normalize_path(path)}"


def _stable_cache_key(path: str, params: dict[str, Any] | None) -> str:
    normalized_path = _normalize_path(path)
    if not params:
        return normalized_path
    encoded = urlencode(sorted(params.items()), doseq=True)
    return f"{normalized_path}?{encoded}"


class SrdApiClient:
    """REST client with caching, retries, and rate limiting."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        user_agent: str = "dnd_db_2/0.1",
        timeout_s: float = 30.0,
        max_retries: int = 3,
        backoff_base_s: float = 0.5,
        min_interval_s: float = 0.1,
        cache_dir: str = "data/raw",
        use_cache: bool = True,
        refresh: bool = False,
    ) -> None:
        self.base_url = _normalize_base_url(base_url or get_api_base_url())
        self.user_agent = user_agent
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.min_interval_s = min_interval_s
        self.cache_dir = Path(cache_dir)
        self.use_cache = use_cache
        self.refresh = refresh
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent})
        self._last_request_at: float | None = None

    def _cache_path(self, path: str, params: dict[str, Any] | None) -> Path:
        parsed = urlparse(self.base_url)
        host = parsed.netloc or "local"
        cache_root = self.cache_dir / "http_cache" / host
        key = _stable_cache_key(path, params)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return cache_root / f"{digest}.json"

    def _read_cache(self, path: str, params: dict[str, Any] | None) -> Any:
        cache_path = self._cache_path(path, params)
        if not cache_path.exists():
            raise FileNotFoundError
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return payload["json"]

    def _write_cache(self, path: str, params: dict[str, Any] | None, payload: Any, url: str, status: int) -> None:
        cache_path = self._cache_path(path, params)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        wrapper = {
            "url": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "json": payload,
        }
        cache_path.write_text(
            json.dumps(wrapper, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _respect_rate_limit(self) -> None:
        if self.min_interval_s <= 0:
            return
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_interval_s - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _request_with_retries(
        self, path: str, params: dict[str, Any] | None
    ) -> requests.Response:
        url = _join_url(self.base_url, path)
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._respect_rate_limit()
            try:
                response = self._session.get(
                    url, params=params, timeout=self.timeout_s
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise ApiHttpError(0, url, f"Request failed: {exc}") from exc
                time.sleep(self.backoff_base_s * (2**attempt))
                continue
            finally:
                self._last_request_at = time.monotonic()

            if response.status_code in TRANSIENT_STATUS_CODES:
                if attempt >= self.max_retries:
                    raise ApiHttpError(response.status_code, response.url)
                time.sleep(self.backoff_base_s * (2**attempt))
                continue
            if not response.ok:
                raise ApiHttpError(response.status_code, response.url)
            return response
        if last_exc:
            raise ApiHttpError(0, url, f"Request failed: {last_exc}") from last_exc
        raise ApiHttpError(0, url, "Request failed without response.")

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict | list:
        if self.use_cache and not self.refresh:
            try:
                return self._read_cache(path, params)
            except FileNotFoundError:
                pass
            except json.JSONDecodeError as exc:
                raise ApiDecodeError(f"Invalid cached JSON for {path}") from exc
        response = self._request_with_retries(path, params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiDecodeError(f"Invalid JSON from {response.url}") from exc
        if self.use_cache:
            self._write_cache(path, params, payload, response.url, response.status_code)
        return payload

    def list_resources(self, resource: str) -> list[dict]:
        payload = self.get_json(f"/api/{resource}")
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        if isinstance(payload, list):
            return payload
        raise ApiDecodeError("Unexpected response shape for list_resources.")

    def get_resource(self, resource: str, index: str) -> dict:
        payload = self.get_json(f"/api/{resource}/{index}")
        if isinstance(payload, dict):
            return payload
        raise ApiDecodeError("Unexpected response shape for get_resource.")

    def get_by_url(self, url_or_path: str) -> dict:
        parsed = urlparse(url_or_path)
        if parsed.scheme:
            path = parsed.path
        else:
            path = url_or_path
        payload = self.get_json(path)
        if isinstance(payload, dict):
            return payload
        raise ApiDecodeError("Unexpected response shape for get_by_url.")
