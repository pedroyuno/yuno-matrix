"""Unit tests for MATRIX API client. Target coverage: 85%+"""
import pytest
from unittest.mock import patch, MagicMock
import os
from src.api_client import APIClient
from src.models import Config, APIConfig

@pytest.mark.unit
def test_api_client_placeholder_mode(mock_config):
    """Test API client in placeholder mode."""
    config = Config(**mock_config)
    client = APIClient(config)
    assert client.placeholder_mode is True


@pytest.mark.unit
def test_api_client_real_mode_no_credentials():
    """Test API client warns about missing credentials."""
    config = Config(placeholder_mode=False)
    
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(os.environ, 'get', return_value=None):
            client = APIClient(config)
            # Should fall back to placeholder mode when credentials missing
            assert client.placeholder_mode is True


@pytest.mark.unit
def test_api_client_real_mode_with_credentials():
    """Test API client in real mode with credentials."""
    config = Config(placeholder_mode=False)
    
    env_vars = {
        'YUNO_PUBLIC_API_KEY': 'test_public_key',
        'YUNO_PRIVATE_SECRET_KEY': 'test_private_key',
        'YUNO_ACCOUNT_ID': 'test_account_id',
        'YUNO_ENVIRONMENT': 'sandbox'
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        client = APIClient(config)
        assert client.placeholder_mode is False
        assert client.yuno_public_key == 'test_public_key'
        assert client.yuno_private_key == 'test_private_key'


@pytest.mark.unit
def test_api_client_production_environment():
    """Test API client in production environment."""
    config = Config(placeholder_mode=False)
    
    env_vars = {
        'YUNO_PUBLIC_API_KEY': 'test_public_key',
        'YUNO_PRIVATE_SECRET_KEY': 'test_private_key',
        'YUNO_ACCOUNT_ID': 'test_account_id',
        'YUNO_ENVIRONMENT': 'production'
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        client = APIClient(config)
        assert client.yuno_environment == 'production'

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
    response = client.capture("provider_a", {
        "payment_id": "pay_123",
        "transaction_id": "txn_123",
        "amount": {"currency": "USD", "value": 100}
    })
    assert response.status_code == 200
    assert response.body["status"] == "SUCCEEDED"
    assert response.body["type"] == "CAPTURE"

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
    response = client.refund("provider_a", {
        "payment_id": "pay_123",
        "transaction_id": "txn_123",
        "amount": {"currency": "USD", "value": 50}
    })
    assert response.status_code == 200
    # Full refund returns REFUNDED status
    assert response.body["status"] in ["REFUNDED", "SUCCEEDED"]
    assert "transactions" in response.body


@pytest.mark.unit
def test_partial_refund_operation(mock_config):
    """Test partial refund returns PARTIALLY_REFUNDED sub_status."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.refund("provider_a", {
        "payment_id": "pay_123",
        "transaction_id": "txn_123",
        "amount": {"currency": "BRL", "value": 25}
    })
    assert response.status_code == 200
    assert response.body["status"] == "SUCCEEDED"
    assert response.body["sub_status"] == "PARTIALLY_REFUNDED"
    assert response.body["amount"]["refunded"] == 25
    assert response.body["transactions"]["type"] == "REFUND"


@pytest.mark.unit
def test_execute_operation_partial_refund_dispatch(mock_config):
    """Test that execute_operation('partial_refund') dispatches to refund."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.execute_operation("partial_refund", "provider_a", {
        "payment_id": "pay_123",
        "transaction_id": "txn_123",
        "amount": {"currency": "BRL", "value": 30}
    })
    assert response.status_code == 200
    assert response.body["sub_status"] == "PARTIALLY_REFUNDED"


@pytest.mark.unit
def test_cancel_operation(mock_config):
    """Test cancel operation."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.cancel("provider_a", {
        "payment_id": "pay_123",
        "transaction_id": "txn_123"
    })
    assert response.status_code == 200
    assert response.body["status"] == "SUCCEEDED"
    assert response.body["type"] == "CANCEL"

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
        ("capture", {"payment_id": "pay_123", "transaction_id": "txn_123", "amount": {"currency": "USD", "value": 100}}),
        ("purchase", {"amount": 50}),
        ("refund", {"payment_id": "pay_123", "transaction_id": "txn_123", "amount": {"currency": "USD", "value": 50}}),
        ("cancel", {"payment_id": "pay_123", "transaction_id": "txn_123"}),
        ("void", {"payment_id": "pay_123", "transaction_id": "txn_123"}),
        ("verify", {}),
        ("tokenize", {"card_number": "4111111111111111"})
    ]
    for op, data in operations:
        response = client.execute_operation(op, "provider_a", data)
        assert response.status_code == 200
        assert isinstance(response.body, dict)


# ============================================================================
# E2E SDK Lite Tests
# ============================================================================

@pytest.mark.unit
def test_create_checkout_session_success(mock_config):
    """Test checkout session creation in placeholder mode."""
    config = Config(**mock_config)
    client = APIClient(config)
    data = {
        "description": "Test Payment",
        "country": "BR",
        "amount": {"currency": "BRL", "value": 100},
        "customer_payer": {"id": "cust-uuid-1234-5678-abcdefabcdef"}
    }
    response = client.create_checkout_session(data)
    assert response.status_code == 200
    assert "checkout_session" in response.body
    assert response.body["country"] == "BR"
    assert response.body["customer_id"] == "cust-uuid-1234-5678-abcdefabcdef"
    assert response.body["amount"]["currency"] == "BRL"


@pytest.mark.unit
def test_create_checkout_session_missing_customer_id(mock_config):
    """Test checkout session fails when customer_payer.id is missing."""
    config = Config(**mock_config)
    client = APIClient(config)
    data = {
        "description": "Test Payment",
        "country": "BR",
        "amount": {"currency": "BRL", "value": 100},
    }
    response = client.create_checkout_session(data)
    assert response.status_code == 400
    assert response.error is not None
    assert "customer_payer.id" in response.error


@pytest.mark.unit
def test_create_checkout_session_empty_customer_payer(mock_config):
    """Test checkout session fails when customer_payer exists but has no id."""
    config = Config(**mock_config)
    client = APIClient(config)
    data = {
        "description": "Test Payment",
        "country": "BR",
        "amount": {"currency": "BRL", "value": 100},
        "customer_payer": {"email": "test@y.uno"}
    }
    response = client.create_checkout_session(data)
    assert response.status_code == 400
    assert "customer_payer.id" in response.error


@pytest.mark.unit
def test_e2e_create_payment_transforms_data(mock_config):
    """Test that e2e_create_payment correctly transforms payment JSON."""
    config = Config(**mock_config)
    client = APIClient(config)
    data = {
        "description": "SafraPay Test",
        "country": "BR",
        "amount": {"currency": "BRL", "value": 100},
        "workflow": "DIRECT",
        "customer_payer": {"id": "cust-uuid", "email": "test@y.uno"},
        "payment_method": {
            "type": "CARD",
            "detail": {
                "card": {
                    "capture": True,
                    "card_data": {
                        "number": "4507990000000002",
                        "expiration_month": 12,
                        "expiration_year": 2030,
                        "security_code": "123",
                        "holder_name": "John Doe"
                    }
                }
            }
        },
        "metadata": [{"key": "provider", "value": "safrapay"}]
    }

    response = client.e2e_create_payment(
        provider="safrapay",
        data=data,
        one_time_token="ott-test-token-12345",
        checkout_session="cs-test-session-id"
    )

    assert response.status_code == 200
    # Original data must NOT be mutated
    assert data["workflow"] == "DIRECT"
    assert "card_data" in data["payment_method"]["detail"]["card"]


@pytest.mark.unit
def test_e2e_create_payment_preserves_metadata(mock_config):
    """Test that e2e_create_payment preserves and updates provider metadata."""
    config = Config(**mock_config)
    client = APIClient(config)
    data = {
        "description": "Test",
        "country": "CO",
        "amount": {"currency": "COP", "value": 50000},
        "workflow": "DIRECT",
        "customer_payer": {"id": "cust-uuid"},
        "payment_method": {
            "type": "CARD",
            "detail": {"card": {"card_data": {"number": "4111111111111111"}}}
        },
        "metadata": [{"key": "provider", "value": "original_provider"}]
    }

    response = client.e2e_create_payment(
        provider="paymentes",
        data=data,
        one_time_token="ott-12345",
        checkout_session="cs-12345"
    )

    assert response.status_code == 200
    # Original metadata should be preserved
    assert data["metadata"][0]["value"] == "original_provider"


@pytest.mark.unit
def test_e2e_create_payment_placeholder_mode(mock_config):
    """Test e2e_create_payment returns mock response in placeholder mode."""
    config = Config(**mock_config)
    client = APIClient(config)
    assert client.placeholder_mode is True

    data = {
        "description": "Placeholder Test",
        "country": "US",
        "amount": {"currency": "USD", "value": 10},
        "workflow": "DIRECT",
        "customer_payer": {"id": "cust-uuid"},
        "payment_method": {
            "type": "CARD",
            "detail": {"card": {"card_data": {"number": "4111111111111111"}}}
        }
    }

    response = client.e2e_create_payment(
        provider="test_provider",
        data=data,
        one_time_token="ott-placeholder",
        checkout_session="cs-placeholder"
    )

    assert response.status_code == 200
    assert response.body.get("id") is not None
    assert response.body.get("provider") == "test_provider"


# ============================================================================
# Customer Creation Tests
# ============================================================================

@pytest.mark.unit
def test_create_customer_placeholder_mode(mock_config):
    """Test customer creation returns mock response in placeholder mode."""
    config = Config(**mock_config)
    client = APIClient(config)
    customer_data = {
        "email": "test@y.uno",
        "first_name": "Test",
        "last_name": "User",
        "document": {"document_type": "CPF", "document_number": "12345678900"}
    }
    response = client.create_customer(customer_data)
    assert response.status_code == 200
    assert response.body.get("id") is not None
    assert response.body["email"] == "test@y.uno"
    assert response.body["merchant_customer_id"].startswith("matrix_e2e_")


@pytest.mark.unit
def test_create_customer_uses_default_email(mock_config):
    """Test customer creation uses default email when none is provided."""
    config = Config(**mock_config)
    client = APIClient(config)
    response = client.create_customer({})
    assert response.status_code == 200
    assert response.body["email"] == "matrix-e2e@y.uno"


@pytest.mark.unit
def test_create_customer_then_checkout_session(mock_config):
    """Test the full E2E flow: create customer, then checkout session."""
    config = Config(**mock_config)
    client = APIClient(config)

    # Payment data without customer_payer.id
    customer_data = {"email": "test@y.uno", "first_name": "Test"}
    customer_response = client.create_customer(customer_data)
    assert customer_response.is_success
    customer_id = customer_response.body["id"]

    payment_data = {
        "description": "E2E Test",
        "country": "BR",
        "amount": {"currency": "BRL", "value": 100},
        "customer_payer": {"id": customer_id, "email": "test@y.uno"}
    }
    checkout_response = client.create_checkout_session(payment_data)
    assert checkout_response.is_success
    assert checkout_response.body.get("checkout_session") is not None
