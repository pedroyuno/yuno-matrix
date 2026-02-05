"""
Unit tests for Datadog client.
"""

import pytest
import json
from unittest.mock import patch, MagicMock

# Sample Datadog logs response based on real public-api logs
SAMPLE_DATADOG_LOGS = [
    {
        "attributes": {
            "attributes": {
                "attributes": {
                    "elapsed": "92",
                    "request": {
                        "headers": "[X-Trace-Id: 7a7364ae-74c9-4596-9912-98d8ef0f9db9]",
                        "http_method": "GET",
                        "url": "https://internal-api-sandbox.y.uno/api-auth-ms/v1/authorization"
                    },
                    "response": {
                        "body": "{\"organization_code\":\"06ccc240-0d33-4f4c-92dc-5a60e2ad9310\"}\n",
                        "http_status": 200
                    }
                },
                "trace_id": "7a7364ae-74c9-4596-9912-98d8ef0f9db9"
            },
            "service": "public-api"
        },
        "type": "log"
    },
    {
        "attributes": {
            "attributes": {
                "attributes": {
                    "card_token": "5cd3d91c-c233-4d24-bc38-6a8dfbd937f9",
                    "iin": "54482800",
                    "lfd": "0007"
                },
                "trace_id": "7a7364ae-74c9-4596-9912-98d8ef0f9db9"
            },
            "service": "public-api"
        },
        "type": "log"
    },
    {
        "attributes": {
            "attributes": {
                "attributes": {
                    "elapsed": "2813",
                    "request": {
                        "body": "{\"order_id\":\"5cb1a1cb-c5de-4ba6-bb6d-2dd42bb0f725\",\"description\":\"Demo Payment\",\"country\":\"BR\",\"amount\":{\"value\":49,\"currency\":\"BRL\"},\"payment_method\":{\"type\":\"CARD\",\"detail\":{\"card\":{\"number\":\"************0007\",\"holder_name\":\"Julio Akio\",\"expiration_month\":12,\"expiration_year\":27,\"security_code\":\"***\"}}},\"customer_payer\":{\"code\":\"23ab39e6-c745-4b5d-8678-bf14988f0e2a\"},\"workflow\":\"DIRECT\",\"metadata\":[{\"key\":\"provider\",\"value\":\"rede\"}]}\n",
                        "http_method": "POST",
                        "url": "https://internal-sandbox.y.uno/payment-api/v1/payment-b2b"
                    },
                    "response": {
                        "body": "{\"code\":\"7cd58b57-ff6f-4698-af2d-89a0045ecc53\",\"status\":\"SUCCEEDED\"}",
                        "http_status": 201
                    }
                },
                "trace_id": "7a7364ae-74c9-4596-9912-98d8ef0f9db9"
            },
            "service": "public-api"
        },
        "type": "log"
    },
    {
        "attributes": {
            "attributes": {
                "attributes": {
                    "elapsed": "3006",
                    "request": {
                        "body": "{\"description\": \"Demo Payment\", \"account_id\": \"a47da978-b69f-4954-a9f1-7707a9b79188\", \"merchant_order_id\": \"5cb1a1cb-c5de-4ba6-bb6d-2dd42bb0f725\", \"country\": \"BR\", \"amount\": {\"currency\": \"BRL\", \"value\": 49}, \"checkout\": {\"session\": \"4b6c5065-6581-4389-90fe-d0234da91a59\"}, \"customer_payer\": {\"id\": \"23ab39e6-c745-4b5d-8678-bf14988f0e2a\"}, \"payment_method\": {\"type\": \"CARD\", \"detail\": {\"card\": {\"verify\": false, \"card_data\": {\"number\": \"****************\", \"expiration_month\": 12, \"expiration_year\": 27, \"security_code\": \"***\", \"holder_name\": \"Julio Akio\"}}}}, \"metadata\": [{\"key\": \"provider\", \"value\": \"rede\"}], \"workflow\": \"DIRECT\"}",
                        "http_method": "POST",
                        "url": "/v1/payments"
                    },
                    "response": {
                        "body": "{\"id\":\"7cd58b57-ff6f-4698-af2d-89a0045ecc53\",\"status\":\"SUCCEEDED\"}",
                        "http_status": "201"
                    }
                },
                "file_name": "middlewareLoggerRequest.go:74",
                "function_name": "routers.ConfigRouter.MidlewareLogRequest.func7",
                "trace_id": "7a7364ae-74c9-4596-9912-98d8ef0f9db9"
            },
            "service": "public-api"
        },
        "type": "log"
    }
]


class TestDatadogClient:
    """Tests for DatadogClient."""
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_client_initialization(self):
        """Test that client initializes with environment variables."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        assert client.api_key == 'test_api_key'
        assert client.app_key == 'test_app_key'
    
    @patch.dict('os.environ', {'DD_API_KEY': '', 'DD_APP_KEY': ''})
    def test_client_initialization_fails_without_credentials(self):
        """Test that client raises error without credentials."""
        from src.datadog_client import DatadogClient
        
        with pytest.raises(ValueError, match="Datadog API credentials not configured"):
            DatadogClient(skip_dotenv=True)
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_extract_payment_payload_from_public_api_log(self):
        """Test extracting payment payload from /v1/payments public-api logs."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        payload, error = client._extract_payment_payload(SAMPLE_DATADOG_LOGS)
        
        assert payload is not None, f"Failed to extract payload: {error}"
        assert error is None
        
        # Verify it extracted from the /v1/payments log (has account_id)
        assert payload.get("account_id") == "a47da978-b69f-4954-a9f1-7707a9b79188"
        assert payload.get("merchant_order_id") == "5cb1a1cb-c5de-4ba6-bb6d-2dd42bb0f725"
        assert payload.get("country") == "BR"
        assert payload.get("workflow") == "DIRECT"
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_extract_payment_payload_contains_expected_fields(self):
        """Test that extracted payload contains all expected payment fields."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        payload, error = client._extract_payment_payload(SAMPLE_DATADOG_LOGS)
        
        assert payload is not None
        
        # Verify all expected fields from /v1/payments endpoint
        assert payload.get("description") == "Demo Payment"
        assert payload.get("account_id") == "a47da978-b69f-4954-a9f1-7707a9b79188"
        assert payload.get("merchant_order_id") == "5cb1a1cb-c5de-4ba6-bb6d-2dd42bb0f725"
        assert payload.get("country") == "BR"
        assert payload["amount"]["currency"] == "BRL"
        assert payload["amount"]["value"] == 49
        assert payload["checkout"]["session"] == "4b6c5065-6581-4389-90fe-d0234da91a59"
        assert payload["customer_payer"]["id"] == "23ab39e6-c745-4b5d-8678-bf14988f0e2a"
        assert payload["payment_method"]["type"] == "CARD"
        assert payload["payment_method"]["detail"]["card"]["verify"] is False
        assert payload["payment_method"]["detail"]["card"]["card_data"]["holder_name"] == "Julio Akio"
        assert payload["metadata"][0]["key"] == "provider"
        assert payload["metadata"][0]["value"] == "rede"
        assert payload.get("workflow") == "DIRECT"
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_extract_payment_payload_from_empty_logs(self):
        """Test that empty logs returns None."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        payload, error = client._extract_payment_payload([])
        
        assert payload is None
        assert error is not None
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_extract_payment_payload_from_logs_without_payment(self):
        """Test logs without payment data returns None."""
        from src.datadog_client import DatadogClient
        
        logs_without_payment = [
            {
                "attributes": {
                    "attributes": {
                        "attributes": {
                            "some_field": "some_value"
                        }
                    }
                }
            }
        ]
        
        client = DatadogClient(skip_dotenv=True)
        payload, error = client._extract_payment_payload(logs_without_payment)
        
        assert payload is None
        assert error is not None
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_is_payment_payload(self):
        """Test payment payload detection."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        
        # Valid payment payload
        valid_payload = {
            "amount": {"currency": "BRL", "value": 100},
            "payment_method": {"type": "CARD"},
            "country": "BR"
        }
        assert client._is_payment_payload(valid_payload) is True
        
        # Invalid payload (missing payment fields)
        invalid_payload = {
            "name": "test",
            "value": 123
        }
        assert client._is_payment_payload(invalid_payload) is False
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_try_parse_json_with_string(self):
        """Test JSON parsing from string."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        
        json_str = '{"key": "value", "number": 123}'
        result = client._try_parse_json(json_str)
        
        assert result == {"key": "value", "number": 123}
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_try_parse_json_with_dict(self):
        """Test JSON parsing with dict input."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        
        input_dict = {"key": "value"}
        result = client._try_parse_json(input_dict)
        
        assert result == input_dict
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_try_parse_json_with_invalid_json(self):
        """Test JSON parsing with invalid JSON returns None."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        
        result = client._try_parse_json("not valid json")
        
        assert result is None
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_validate_trace_id_format(self):
        """Test trace_id validation."""
        from src.datadog_client import DatadogClient
        
        client = DatadogClient(skip_dotenv=True)
        
        # Invalid UUID
        result = client.search_by_trace_id("invalid-trace-id")
        assert result["success"] is False
        assert "Invalid trace_id format" in result["error"]
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    @patch('src.datadog_client.requests.post')
    def test_search_by_trace_id_success(self, mock_post):
        """Test successful search by trace_id."""
        from src.datadog_client import DatadogClient
        
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": SAMPLE_DATADOG_LOGS}
        mock_post.return_value = mock_response
        
        client = DatadogClient(skip_dotenv=True)
        result = client.search_by_trace_id("7a7364ae-74c9-4596-9912-98d8ef0f9db9")
        
        assert result["success"] is True
        assert result["payload"] is not None
        assert result["logs_count"] == 4
        assert result["error"] is None
        
        # Verify API was called with correct query
        call_args = mock_post.call_args
        request_body = call_args.kwargs.get('json') or call_args[1].get('json')
        assert "@trace_id:7a7364ae-74c9-4596-9912-98d8ef0f9db9" in request_body["filter"]["query"]
        assert "service:public-api" in request_body["filter"]["query"]
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    @patch('src.datadog_client.requests.post')
    def test_search_by_trace_id_no_logs(self, mock_post):
        """Test search with no logs found."""
        from src.datadog_client import DatadogClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_post.return_value = mock_response
        
        client = DatadogClient(skip_dotenv=True)
        result = client.search_by_trace_id("7a7364ae-74c9-4596-9912-98d8ef0f9db9")
        
        assert result["success"] is False
        assert "No logs found" in result["error"]
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    @patch('src.datadog_client.requests.post')
    def test_search_by_trace_id_api_error(self, mock_post):
        """Test search with API error."""
        from src.datadog_client import DatadogClient
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"errors": ["Unauthorized"]}'
        mock_post.return_value = mock_response
        
        client = DatadogClient(skip_dotenv=True)
        result = client.search_by_trace_id("7a7364ae-74c9-4596-9912-98d8ef0f9db9")
        
        assert result["success"] is False
        assert "401" in result["error"]


class TestPayloadExtraction:
    """Tests specifically for payload extraction logic."""
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_extracts_from_request_body_field(self):
        """Test extraction from request.body field (JSON string)."""
        from src.datadog_client import DatadogClient
        
        logs = [{
            "attributes": {
                "attributes": {
                    "attributes": {
                        "request": {
                            "body": '{"amount": {"value": 100, "currency": "BRL"}, "payment_method": {"type": "CARD"}, "country": "BR"}',
                            "url": "/v1/payments"
                        }
                    }
                }
            }
        }]
        
        client = DatadogClient(skip_dotenv=True)
        payload, error = client._extract_payment_payload(logs)
        
        assert payload is not None
        assert payload["amount"]["value"] == 100
        assert payload["payment_method"]["type"] == "CARD"
    
    @patch.dict('os.environ', {'DD_API_KEY': 'test_api_key', 'DD_APP_KEY': 'test_app_key'})
    def test_prefers_public_api_endpoint(self):
        """Test that /v1/payments log is preferred over internal API logs."""
        from src.datadog_client import DatadogClient
        
        # The sample logs contain both internal API and /v1/payments logs
        # The extraction should prefer the /v1/payments log which has account_id
        
        client = DatadogClient(skip_dotenv=True)
        payload, error = client._extract_payment_payload(SAMPLE_DATADOG_LOGS)
        
        assert payload is not None
        assert error is None
        # account_id and checkout.session are only in the /v1/payments log
        assert payload.get("account_id") == "a47da978-b69f-4954-a9f1-7707a9b79188"
        assert payload.get("checkout", {}).get("session") == "4b6c5065-6581-4389-90fe-d0234da91a59"
