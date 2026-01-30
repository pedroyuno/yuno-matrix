"""
Shared pytest fixtures for MATRIX tests.
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from src.models import (
    Metadata, Step, TestCase, TestSuite,
    APIResponse, APIRequest, StepResult, TestCaseResult, ExecutionReport
)


@pytest.fixture
def sample_metadata() -> Metadata:
    """Returns a valid Metadata object."""
    return Metadata(
        test_suite_name="Merchant Certification Tests",
        merchant_id="merchant_123",
        environment="sandbox",
        created_at="2026-01-29T10:00:00Z"
    )


@pytest.fixture
def sample_step_authorize() -> Step:
    """Returns an authorize step."""
    return Step(
        step_id=1,
        operation="authorize",
        provider="provider_a",
        description="Authorize payment",
        input_data={
            "amount": 100.00,
            "currency": "USD",
            "card_token": "tok_test_visa_4111"
        },
        capture_variables={
            "transaction_id": "$.body.transaction_id",
            "auth_code": "$.body.auth_code"
        },
        expected_status="success"
    )


@pytest.fixture
def sample_step_capture() -> Step:
    """Returns a capture step with variable reference."""
    return Step(
        step_id=2,
        operation="capture",
        provider="provider_a",
        description="Capture authorized payment",
        input_data={
            "transaction_id": "{{transaction_id}}",
            "amount": 100.00
        },
        expected_status="success"
    )


@pytest.fixture
def sample_test_case(sample_step_authorize: Step, sample_step_capture: Step) -> TestCase:
    """Returns a valid TestCase with multiple steps."""
    return TestCase(
        id="tc_001",
        name="Authorize and Capture Flow",
        description="Test successful authorization followed by capture",
        steps=[sample_step_authorize, sample_step_capture]
    )


@pytest.fixture
def sample_test_suite(sample_metadata: Metadata, sample_test_case: TestCase) -> TestSuite:
    """Returns a valid TestSuite object."""
    return TestSuite(
        version="1.0",
        metadata=sample_metadata,
        test_cases=[sample_test_case]
    )


@pytest.fixture
def mock_api_response() -> APIResponse:
    """Returns a mock API response."""
    return APIResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body={
            "transaction_id": "txn_12345",
            "status": "authorized",
            "auth_code": "AUTH123",
            "amount": 100.00
        },
        duration_ms=245
    )


@pytest.fixture
def mock_api_request() -> APIRequest:
    """Returns a mock API request."""
    return APIRequest(
        method="POST",
        url="https://api.provider-a.com/authorize",
        headers={"Authorization": "Bearer ***", "Content-Type": "application/json"},
        body={"amount": 100.00, "currency": "USD"}
    )


@pytest.fixture
def sample_step_result(mock_api_request: APIRequest, mock_api_response: APIResponse) -> StepResult:
    """Returns a sample step result."""
    return StepResult(
        step_id=1,
        operation="authorize",
        provider="provider_a",
        status="success",
        request=mock_api_request,
        response=mock_api_response,
        duration_ms=245,
        captured_variables={"transaction_id": "txn_12345"}
    )


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Returns a test configuration."""
    return {
        "api": {
            "base_urls": {
                "provider_a": "https://api.provider-a.com",
                "provider_b": "https://api.provider-b.com"
            },
            "timeout": 30,
            "retry_attempts": 3
        },
        "placeholder_mode": True
    }


@pytest.fixture
def temp_log_dir(tmp_path):
    """Returns a temporary directory for logs."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return str(log_dir)
