from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from dnd_db.ingest.api_client import SrdApiClient
from dnd_db.ingest.errors import ApiDecodeError


class FakeResponse:
    def __init__(self, status_code: int, payload: Any, url: str) -> None:
        self.status_code = status_code
        self._payload = payload
        self.url = url

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_caching_uses_disk(tmp_path: Path) -> None:
    payload = {"count": 1, "results": [{"index": "acid-arrow"}]}
    calls: list[str] = []

    def fake_get(url: str, params: dict | None = None, timeout: float = 0) -> FakeResponse:
        calls.append(url)
        return FakeResponse(200, payload, url)

    client = SrdApiClient(cache_dir=str(tmp_path))
    client._session.get = fake_get  # type: ignore[assignment]

    first = client.get_json("/api/spells")
    second = client.get_json("/api/spells")

    assert first == payload
    assert second == payload
    assert len(calls) == 1


def test_refresh_bypasses_cache(tmp_path: Path) -> None:
    payload = {"count": 1, "results": [{"index": "acid-arrow"}]}
    calls: list[str] = []

    def fake_get(url: str, params: dict | None = None, timeout: float = 0) -> FakeResponse:
        calls.append(url)
        return FakeResponse(200, payload, url)

    client = SrdApiClient(cache_dir=str(tmp_path))
    client._session.get = fake_get  # type: ignore[assignment]
    client.get_json("/api/spells")

    refresh_client = SrdApiClient(cache_dir=str(tmp_path), refresh=True)
    refresh_client._session.get = fake_get  # type: ignore[assignment]
    refresh_client.get_json("/api/spells")

    assert len(calls) == 2


def test_list_resources_handles_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SrdApiClient()
    monkeypatch.setattr(
        client, "get_json", lambda path, params=None: {"results": [{"index": "x"}]}
    )
    assert client.list_resources("spells") == [{"index": "x"}]

    monkeypatch.setattr(client, "get_json", lambda path, params=None: [{"index": "y"}])
    assert client.list_resources("spells") == [{"index": "y"}]

    monkeypatch.setattr(client, "get_json", lambda path, params=None: {"oops": []})
    with pytest.raises(ApiDecodeError):
        client.list_resources("spells")


def test_retries_on_transient_errors(tmp_path: Path) -> None:
    payload = {"index": "acid-arrow"}
    calls: list[int] = []

    def fake_get(url: str, params: dict | None = None, timeout: float = 0) -> FakeResponse:
        calls.append(1)
        if len(calls) == 1:
            return FakeResponse(503, {}, url)
        return FakeResponse(200, payload, url)

    client = SrdApiClient(cache_dir=str(tmp_path), max_retries=2, backoff_base_s=0)
    client._session.get = fake_get  # type: ignore[assignment]
    assert client.get_json("/api/spells/acid-arrow") == payload
    assert len(calls) == 2


def test_rate_limiting_calls_sleep(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payload = {"index": "acid-arrow"}
    calls: list[float] = []
    sleeps: list[float] = []

    def fake_get(url: str, params: dict | None = None, timeout: float = 0) -> FakeResponse:
        return FakeResponse(200, payload, url)

    timeline = iter([100.0, 100.0, 100.2, 100.2])

    def fake_monotonic() -> float:
        return next(timeline)

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = SrdApiClient(cache_dir=str(tmp_path), min_interval_s=1.0)
    client._session.get = fake_get  # type: ignore[assignment]
    monkeypatch.setattr("dnd_db.ingest.api_client.time.monotonic", fake_monotonic)
    monkeypatch.setattr("dnd_db.ingest.api_client.time.sleep", fake_sleep)

    client.get_json("/api/spells/acid-arrow")
    client.get_json("/api/spells/acid-arrow", params={"x": "y"})

    assert sleeps


def test_cache_decode_error(tmp_path: Path) -> None:
    cache_dir = tmp_path / "raw"
    client = SrdApiClient(cache_dir=str(cache_dir))
    cache_path = client._cache_path("/api/spells", None)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ApiDecodeError):
        client.get_json("/api/spells")
