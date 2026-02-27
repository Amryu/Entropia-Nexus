"""Tests for inventory-related API methods in NexusClient."""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest
import requests

from client.api.nexus_client import NexusClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a NexusClient with mocked config and oauth."""
    config = MagicMock()
    config.nexus_base_url = "https://entropianexus.com"
    oauth = MagicMock()
    oauth.get_access_token.return_value = "test-token"
    oauth.is_authenticated.return_value = True
    event_bus = MagicMock()
    return NexusClient(config, oauth, event_bus)


def _mock_response(status_code=200, json_data=None, raise_for_status=True):
    """Create a mock response object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    if json_data is not None:
        resp.json.return_value = json_data
    if raise_for_status and status_code >= 400:
        http_error = requests.HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_error
    else:
        resp.raise_for_status.return_value = None
    return resp


# ===================================================================
# get_inventory
# ===================================================================

class TestGetInventory:
    def test_success(self, client):
        items = [
            {"item_id": 100, "item_name": "Test Weapon", "quantity": 1},
            {"item_id": 200, "item_name": "Test Material", "quantity": 500},
        ]
        with patch.object(client._session, 'get', return_value=_mock_response(200, items)):
            result = client.get_inventory()
        assert result == items
        assert len(result) == 2

    def test_auth_error_403(self, client):
        with patch.object(client._session, 'get', return_value=_mock_response(403)):
            result = client.get_inventory()
        assert result is None

    def test_not_authenticated_401(self, client):
        with patch.object(client._session, 'get', return_value=_mock_response(401)):
            result = client.get_inventory()
        assert result is None

    def test_network_error(self, client):
        with patch.object(client._session, 'get', side_effect=requests.ConnectionError("timeout")):
            result = client.get_inventory()
        assert result is None

    def test_sends_auth_header(self, client):
        with patch.object(client._session, 'get', return_value=_mock_response(200, [])) as mock_get:
            client.get_inventory()
        _, kwargs = mock_get.call_args
        assert kwargs['headers']['Authorization'] == 'Bearer test-token'


# ===================================================================
# get_inventory_markups
# ===================================================================

class TestGetInventoryMarkups:
    def test_success(self, client):
        markups = [
            {"item_id": 100, "markup": 120.5, "updated_at": "2026-01-01T00:00:00Z"},
        ]
        with patch.object(client._session, 'get', return_value=_mock_response(200, markups)):
            result = client.get_inventory_markups()
        assert result == markups

    def test_error_returns_none(self, client):
        with patch.object(client._session, 'get', return_value=_mock_response(500)):
            result = client.get_inventory_markups()
        assert result is None


# ===================================================================
# save_inventory_markups
# ===================================================================

class TestSaveInventoryMarkups:
    def test_success(self, client):
        items = [{"item_id": 100, "markup": 150.0}]
        with patch.object(client._session, 'put', return_value=_mock_response(200, items)) as mock_put:
            result = client.save_inventory_markups(items)
        assert result is True
        # Verify payload
        _, kwargs = mock_put.call_args
        assert kwargs['json'] == {"items": items}

    def test_rate_limited_429(self, client):
        with patch.object(client._session, 'put', return_value=_mock_response(429)):
            result = client.save_inventory_markups([{"item_id": 1, "markup": 100}])
        assert result is False

    def test_server_error(self, client):
        with patch.object(client._session, 'put', return_value=_mock_response(500)):
            result = client.save_inventory_markups([])
        assert result is False

    def test_sends_auth_header(self, client):
        with patch.object(client._session, 'put', return_value=_mock_response(200, [])) as mock_put:
            client.save_inventory_markups([{"item_id": 1, "markup": 100}])
        _, kwargs = mock_put.call_args
        assert kwargs['headers']['Authorization'] == 'Bearer test-token'


# ===================================================================
# delete_inventory_markup
# ===================================================================

class TestDeleteInventoryMarkup:
    def test_success(self, client):
        with patch.object(client._session, 'delete', return_value=_mock_response(200, {"success": True})):
            result = client.delete_inventory_markup(100)
        assert result is True

    def test_not_found_404(self, client):
        with patch.object(client._session, 'delete', return_value=_mock_response(404)):
            result = client.delete_inventory_markup(999)
        assert result is False

    def test_server_error(self, client):
        with patch.object(client._session, 'delete', return_value=_mock_response(500)):
            result = client.delete_inventory_markup(100)
        assert result is False

    def test_correct_url(self, client):
        with patch.object(client._session, 'delete', return_value=_mock_response(200, {})) as mock_del:
            client.delete_inventory_markup(42)
        url = mock_del.call_args[0][0]
        assert url.endswith('/api/users/inventory/markups/42')


# ===================================================================
# get_inventory_containers
# ===================================================================

class TestGetInventoryContainers:
    def test_success(self, client):
        containers = [
            {"container_path": "STORAGE (Calypso) > Safe", "custom_name": "My Safe"},
        ]
        with patch.object(client._session, 'get', return_value=_mock_response(200, containers)):
            result = client.get_inventory_containers()
        assert result == containers

    def test_error_returns_none(self, client):
        with patch.object(client._session, 'get', return_value=_mock_response(403)):
            result = client.get_inventory_containers()
        assert result is None
