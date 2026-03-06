"""Tests for proactive ingestion rate limiting."""

from datetime import datetime, timedelta

from client.ingestion.uploader import IngestionUploader


class _DummyEventBus:
    def subscribe(self, _event, _handler):
        return None

    def unsubscribe(self, _event, _handler):
        return None

    def publish(self, _event, _payload):
        return None


class _DummyClient:
    def __init__(self):
        self._authenticated = True
        self.global_calls = 0
        self.trade_calls = 0

    def is_authenticated(self):
        return self._authenticated

    def ingest_globals(self, batch):
        self.global_calls += 1
        return {"accepted": len(batch), "duplicates": 0, "conflicts": 0, "invalid": 0}

    def ingest_trades(self, batch):
        self.trade_calls += 1
        return {"accepted": len(batch), "duplicates": 0, "conflicts": 0, "invalid": 0}


class _DummyConfig:
    ingestion_upload_interval_seconds = 30


def test_preemptive_throttle_requeues_without_request(monkeypatch):
    import client.ingestion.uploader as uploader_mod

    monkeypatch.setattr(uploader_mod, "MAX_BATCH_SIZE", 1)
    monkeypatch.setattr(uploader_mod, "INGEST_RATE_LIMIT_MAX_REQUESTS", 2)
    monkeypatch.setattr(
        uploader_mod,
        "INGEST_RATE_LIMIT_WINDOW",
        timedelta(seconds=60),
    )

    client = _DummyClient()
    uploader = IngestionUploader(
        event_bus=_DummyEventBus(),
        nexus_client=client,
        config=_DummyConfig(),
        db=None,
    )

    with uploader._lock:
        now = datetime.now()
        uploader._request_times["global"].append(now)
        uploader._request_times["global"].append(now)
        uploader._global_buffer.extend([{"id": 1}, {"id": 2}, {"id": 3}])

    sent, processed = uploader._flush_type(
        uploader._global_buffer,
        "global",
        client.ingest_globals,
    )

    assert sent == 0
    assert processed == []
    assert client.global_calls == 0
    assert len(uploader._global_buffer) == 3
    assert "global" in uploader._rate_limit_until


def test_preemptive_limit_is_per_endpoint(monkeypatch):
    import client.ingestion.uploader as uploader_mod

    monkeypatch.setattr(uploader_mod, "MAX_BATCH_SIZE", 1)
    monkeypatch.setattr(uploader_mod, "INGEST_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(
        uploader_mod,
        "INGEST_RATE_LIMIT_WINDOW",
        timedelta(seconds=60),
    )

    client = _DummyClient()
    uploader = IngestionUploader(
        event_bus=_DummyEventBus(),
        nexus_client=client,
        config=_DummyConfig(),
        db=None,
    )

    with uploader._lock:
        uploader._request_times["global"].append(datetime.now())
        uploader._global_buffer.append({"id": 1})
        uploader._trade_buffer.append({"id": 2})

    uploader._flush()

    assert client.global_calls == 0
    assert client.trade_calls == 1
    assert len(uploader._global_buffer) == 1
    assert len(uploader._trade_buffer) == 0
