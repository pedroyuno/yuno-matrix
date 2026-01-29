"""Unit tests for MATRIX API client. Target coverage: 85%+"""
import pytest
from src.api_client import APIClient
from src.models import Config, APIConfig

@pytest.mark.unit
def test_api_client_placeholder_mode(mock_config):
    """Test API client in placeholder mode."""
    config = Config(**mock_config)
    client = APIClient(config)
    assert client.placeholder_mode is True

@pytest.mark.unit
def test_authorize_operation(mock_config):
    """Test authorize operation."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.authorize("provider_a", {"amount": 100, "currency": "USD"})
    assert response.status_code == 200
    assert "transaction_id" in response.body
    assert response.body["status"] == "authorized"

@pytest.mark.unit
def test_capture_operation(mock_config):
    """Test capture operation."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.capture("provider_a", {"transaction_id": "txn_123", "amount": 100})
    assert response.status_code == 200
    assert response.body["status"] == "captured"

@pytest.mark.unit
def test_purchase_operation(mock_config):
    """Test purchase operation."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.purchase("provider_a", {"amount": 50, "currency": "USD"})
    assert response.status_code == 200
    assert response.body["status"] == "completed"

@pytest.mark.unit
def test_refund_operation(mock_config):
    """Test refund operation."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.refund("provider_a", {"transaction_id": "txn_123", "amount": 50})
    assert response.status_code == 200
    assert response.body["status"] == "refunded"
    assert "refund_id" in response.body

@pytest.mark.unit
def test_execute_operation_dispatch(mock_config):
    """Test execute_operation dispatches correctly."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.execute_operation("authorize", "provider_a", {"amount": 100})
    assert response.status_code == 200

@pytest.mark.unit
def test_execute_operation_unknown(mock_config):
    """Test unknown operation raises error."""
    config = Config(**mock_config)
    client = APIClient(config)
    with pytest.raises(ValueError) as exc_info:
        client.execute_operation("invalid_operation", "provider_a", {})
    assert "unknown operation" in str(exc_info.value).lower()

@pytest.mark.unit
def test_all_operations_return_response(mock_config):
    """Test all operation methods return APIResponse."""
    config = Config(**mock_config)
    client = APIClient(config)
    operations = [
        ("authorize", {"amount": 100}),
        ("capture", {"transaction_id": "txn_123", "amount": 100}),
        ("purchase", {"amount": 50}),
        ("refund", {"transaction_id": "txn_123", "amount": 50}),
        ("void", {"transaction_id": "txn_123"}),
        ("verify", {}),
        ("tokenize", {"card_number": "4111111111111111"})
    ]
    for op, data in operations:
        response = client.execute_operation(op, "provider_a", data)
        assert response.status_code == 200
        assert isinstance(response.body, dict)
