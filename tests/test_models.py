"""
Unit tests for MATRIX data models.

Target coverage: 90%+
"""

import pytest
from pydantic import ValidationError
from datetime import datetime

from src.models import (
    Metadata, Step, TestCase, TestSuite,
    APIResponse, APIRequest, StepResult, TestCaseResult, ExecutionReport,
    APIConfig, Config
)


# ============================================================================
# Metadata Tests
# ============================================================================

@pytest.mark.unit
def test_metadata_valid(sample_metadata):
    """Test valid Metadata creation."""
    assert sample_metadata.test_suite_name == "Merchant Certification Tests"
    assert sample_metadata.merchant_id == "merchant_123"
    assert sample_metadata.environment == "sandbox"
    assert sample_metadata.created_at == "2026-01-29T10:00:00Z"


@pytest.mark.unit
def test_metadata_missing_required_field():
    """Test Metadata raises error when missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        Metadata(
            test_suite_name="Test",
            merchant_id="m123",
            environment="sandbox"
            # missing created_at
        )
    assert "created_at" in str(exc_info.value)


@pytest.mark.unit
def test_metadata_invalid_timestamp():
    """Test Metadata validates timestamp format."""
    with pytest.raises(ValidationError) as exc_info:
        Metadata(
            test_suite_name="Test",
            merchant_id="m123",
            environment="sandbox",
            created_at="invalid-timestamp"
        )
    assert "timestamp" in str(exc_info.value).lower()


@pytest.mark.unit
def test_metadata_empty_string_fields():
    """Test Metadata rejects empty string fields."""
    with pytest.raises(ValidationError):
        Metadata(
            test_suite_name="",  # Empty string
            merchant_id="m123",
            environment="sandbox",
            created_at="2026-01-29T10:00:00Z"
        )


# ============================================================================
# Step Tests
# ============================================================================

@pytest.mark.unit
def test_step_valid(sample_step_authorize):
    """Test valid Step creation."""
    assert sample_step_authorize.step_id == 1
    assert sample_step_authorize.operation == "authorize"
    assert sample_step_authorize.provider == "provider_a"
    assert sample_step_authorize.description == "Authorize payment"
    assert sample_step_authorize.input_data["amount"] == 100.00
    assert sample_step_authorize.capture_variables is not None


@pytest.mark.unit
def test_step_operation_normalized():
    """Test that operation is normalized to lowercase."""
    step = Step(
        step_id=1,
        operation="AUTHORIZE",  # Uppercase
        provider="provider_a",
        description="Test",
        input_data={}
    )
    assert step.operation == "authorize"


@pytest.mark.unit
def test_step_custom_operation():
    """Test that custom operations are allowed."""
    step = Step(
        step_id=1,
        operation="custom_operation",
        provider="provider_a",
        description="Custom operation",
        input_data={}
    )
    assert step.operation == "custom_operation"


@pytest.mark.unit
def test_step_invalid_step_id():
    """Test Step rejects invalid step_id."""
    with pytest.raises(ValidationError) as exc_info:
        Step(
            step_id=0,  # Must be >= 1
            operation="authorize",
            provider="provider_a",
            description="Test",
            input_data={}
        )
    assert "step_id" in str(exc_info.value).lower()


@pytest.mark.unit
def test_step_missing_required_fields():
    """Test Step raises error when missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        Step(
            step_id=1,
            operation="authorize"
            # missing provider and description
        )
    assert "provider" in str(exc_info.value) or "description" in str(exc_info.value)


@pytest.mark.unit
def test_step_optional_fields():
    """Test Step with optional fields set to None."""
    step = Step(
        step_id=1,
        operation="authorize",
        provider="provider_a",
        description="Test",
        input_data={},
        capture_variables=None,
        expected_status=None
    )
    assert step.capture_variables is None
    assert step.expected_status is None


# ============================================================================
# TestCase Tests
# ============================================================================

@pytest.mark.unit
def test_testcase_valid(sample_test_case):
    """Test valid TestCase creation."""
    assert sample_test_case.id == "tc_001"
    assert sample_test_case.name == "Authorize and Capture Flow"
    assert len(sample_test_case.steps) == 2


@pytest.mark.unit
def test_testcase_sequential_step_ids():
    """Test TestCase validates sequential step IDs."""
    step1 = Step(step_id=1, operation="authorize", provider="p", description="d", input_data={})
    step2 = Step(step_id=2, operation="capture", provider="p", description="d", input_data={})

    tc = TestCase(
        id="tc_001",
        name="Test",
        description="Test",
        steps=[step1, step2]
    )
    assert len(tc.steps) == 2


@pytest.mark.unit
def test_testcase_non_sequential_step_ids():
    """Test TestCase rejects non-sequential step IDs."""
    step1 = Step(step_id=1, operation="authorize", provider="p", description="d", input_data={})
    step3 = Step(step_id=3, operation="capture", provider="p", description="d", input_data={})  # Skip 2

    with pytest.raises(ValidationError) as exc_info:
        TestCase(
            id="tc_001",
            name="Test",
            description="Test",
            steps=[step1, step3]
        )
    assert "sequential" in str(exc_info.value).lower()


@pytest.mark.unit
def test_testcase_empty_steps():
    """Test TestCase requires at least one step."""
    with pytest.raises(ValidationError) as exc_info:
        TestCase(
            id="tc_001",
            name="Test",
            description="Test",
            steps=[]  # Empty
        )
    assert "steps" in str(exc_info.value).lower()


# ============================================================================
# TestSuite Tests
# ============================================================================

@pytest.mark.unit
def test_testsuite_valid(sample_test_suite):
    """Test valid TestSuite creation."""
    assert sample_test_suite.version == "1.0"
    assert sample_test_suite.metadata.test_suite_name == "Merchant Certification Tests"
    assert len(sample_test_suite.test_cases) == 1


@pytest.mark.unit
def test_testsuite_empty_test_cases():
    """Test TestSuite allows empty test_cases list."""
    metadata = Metadata(
        test_suite_name="Test",
        merchant_id="m123",
        environment="sandbox",
        created_at="2026-01-29T10:00:00Z"
    )
    ts = TestSuite(
        version="1.0",
        metadata=metadata,
        test_cases=[]
    )
    assert len(ts.test_cases) == 0


@pytest.mark.unit
def test_testsuite_invalid_version():
    """Test TestSuite validates version."""
    metadata = Metadata(
        test_suite_name="Test",
        merchant_id="m123",
        environment="sandbox",
        created_at="2026-01-29T10:00:00Z"
    )
    with pytest.raises(ValidationError):
        TestSuite(
            version="",  # Empty version
            metadata=metadata,
            test_cases=[]
        )


@pytest.mark.unit
def test_testsuite_json_serialization(sample_test_suite):
    """Test TestSuite can be serialized to JSON and back."""
    json_data = sample_test_suite.model_dump()
    reconstructed = TestSuite(**json_data)
    assert reconstructed.version == sample_test_suite.version
    assert reconstructed.metadata.test_suite_name == sample_test_suite.metadata.test_suite_name


# ============================================================================
# APIResponse Tests
# ============================================================================

@pytest.mark.unit
def test_api_response_success(mock_api_response):
    """Test APIResponse for successful request."""
    assert mock_api_response.status_code == 200
    assert mock_api_response.is_success is True
    assert mock_api_response.error is None


@pytest.mark.unit
def test_api_response_failure():
    """Test APIResponse for failed request."""
    response = APIResponse(
        status_code=400,
        headers={},
        body={"error": "Bad Request"},
        error="Invalid request"
    )
    assert response.is_success is False
    assert response.error == "Invalid request"


@pytest.mark.unit
def test_api_response_without_error_field():
    """Test APIResponse with error status but no error field."""
    response = APIResponse(
        status_code=500,
        headers={},
        body={}
    )
    assert response.is_success is False


# ============================================================================
# StepResult Tests
# ============================================================================

@pytest.mark.unit
def test_step_result_success(sample_step_result):
    """Test StepResult for successful step."""
    assert sample_step_result.status == "success"
    assert sample_step_result.operation == "authorize"
    assert sample_step_result.error_message is None


@pytest.mark.unit
def test_step_result_failure():
    """Test StepResult for failed step."""
    result = StepResult(
        step_id=1,
        operation="authorize",
        provider="provider_a",
        status="failure",
        error_message="Authorization failed"
    )
    assert result.status == "failure"
    assert result.error_message == "Authorization failed"


# ============================================================================
# ExecutionReport Tests
# ============================================================================

@pytest.mark.unit
def test_execution_report_success_rate():
    """Test ExecutionReport success_rate calculation."""
    report = ExecutionReport(
        execution_id="exec_001",
        start_time="2026-01-29T10:00:00Z",
        test_suite_name="Test Suite",
        total_test_cases=10,
        passed_test_cases=8,
        failed_test_cases=2,
        error_test_cases=0,
        total_steps=20
    )
    assert report.success_rate == 80.0


@pytest.mark.unit
def test_execution_report_zero_test_cases():
    """Test ExecutionReport with zero test cases."""
    report = ExecutionReport(
        execution_id="exec_001",
        start_time="2026-01-29T10:00:00Z",
        test_suite_name="Test Suite",
        total_test_cases=0,
        passed_test_cases=0,
        failed_test_cases=0,
        error_test_cases=0,
        total_steps=0
    )
    assert report.success_rate == 0.0


@pytest.mark.unit
def test_execution_report_all_passed():
    """Test ExecutionReport with all tests passed."""
    report = ExecutionReport(
        execution_id="exec_001",
        start_time="2026-01-29T10:00:00Z",
        test_suite_name="Test Suite",
        total_test_cases=5,
        passed_test_cases=5,
        failed_test_cases=0,
        error_test_cases=0,
        total_steps=10
    )
    assert report.success_rate == 100.0


# ============================================================================
# Config Tests
# ============================================================================

@pytest.mark.unit
def test_config_defaults():
    """Test Config with default values."""
    config = Config()
    assert config.placeholder_mode is True
    assert config.api.timeout == 30
    assert config.api.retry_attempts == 3


@pytest.mark.unit
def test_api_config_validation():
    """Test APIConfig validation."""
    api_config = APIConfig(
        base_urls={"provider_a": "https://api.example.com"},
        timeout=60,
        retry_attempts=5
    )
    assert api_config.timeout == 60
    assert api_config.retry_attempts == 5


@pytest.mark.unit
def test_api_config_invalid_timeout():
    """Test APIConfig rejects invalid timeout."""
    with pytest.raises(ValidationError):
        APIConfig(timeout=0)  # Must be >= 1


@pytest.mark.unit
def test_api_config_negative_retry():
    """Test APIConfig rejects negative retry_attempts."""
    with pytest.raises(ValidationError):
        APIConfig(retry_attempts=-1)  # Must be >= 0
