"""Worker wake-up ping (app/core/worker_wake.py).

Pure unit tests with a fake httpx client - no network. The property that
matters most is the last one: a failed ping must never raise, since it
runs after a ticket is already safely queued and must not turn a
successful submission into an error.
"""

import httpx

from app.core import worker_wake


class _FakeClient:
    calls: list[str] = []
    raises: Exception | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        _FakeClient.calls.append(url)
        if _FakeClient.raises is not None:
            raise _FakeClient.raises


def _reset(monkeypatch, url):
    _FakeClient.calls = []
    _FakeClient.raises = None
    monkeypatch.setattr(worker_wake.settings, "worker_wake_url", url)
    monkeypatch.setattr(worker_wake.httpx, "AsyncClient", _FakeClient)


async def test_no_op_when_url_unset(monkeypatch):
    _reset(monkeypatch, None)
    await worker_wake.wake_worker()
    assert _FakeClient.calls == []


async def test_pings_the_configured_url(monkeypatch):
    _reset(monkeypatch, "https://worker.example.com/")
    await worker_wake.wake_worker()
    assert _FakeClient.calls == ["https://worker.example.com/"]


async def test_swallows_connection_errors(monkeypatch):
    _reset(monkeypatch, "https://worker.example.com/")
    _FakeClient.raises = httpx.ConnectError("worker unreachable")
    await worker_wake.wake_worker()  # must not raise


async def test_swallows_timeouts(monkeypatch):
    _reset(monkeypatch, "https://worker.example.com/")
    _FakeClient.raises = httpx.ReadTimeout("worker still cold-starting")
    await worker_wake.wake_worker()  # must not raise
