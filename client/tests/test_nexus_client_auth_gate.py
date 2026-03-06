"""Auth-gate tests for NexusClient protected endpoints."""

from unittest.mock import MagicMock, patch

from client.api.nexus_client import NexusClient


def _unauthenticated_client() -> NexusClient:
    config = MagicMock()
    config.nexus_base_url = "https://entropianexus.com"
    oauth = MagicMock()
    oauth.is_authenticated.return_value = False
    oauth.get_access_token.return_value = None
    return NexusClient(config, oauth, event_bus=MagicMock())


def test_get_inventory_skips_network_when_unauthenticated():
    client = _unauthenticated_client()
    with patch.object(client._session, "get") as mock_get:
        result = client.get_inventory()
    assert result is None
    mock_get.assert_not_called()


def test_save_preference_skips_network_when_unauthenticated():
    client = _unauthenticated_client()
    with patch.object(client._session, "put") as mock_put:
        ok = client.save_preference("theme", {"mode": "dark"})
    assert ok is False
    mock_put.assert_not_called()


def test_ingest_globals_skips_network_when_unauthenticated():
    client = _unauthenticated_client()
    with patch.object(client._session, "post") as mock_post:
        result = client.ingest_globals([{"player": "Test"}])
    assert result is None
    mock_post.assert_not_called()
