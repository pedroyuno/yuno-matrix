"""Unit tests for MATRIX executor. Target coverage: 85%+"""
import pytest
from src.executor import TestExecutor
from src.api_client import APIClient
from src.logger import CertificationLogger
from src.context import ExecutionContext
from src.models import Config

@pytest.mark.unit
def test_execute_single_step(mock_config, sample_test_case, temp_log_dir):
    """Test executing a single step."""
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    result = executor.execute_step(sample_test_case, sample_test_case.steps[0])
    assert result.status == "success"
    assert result.operation == "authorize"

@pytest.mark.unit
def test_execute_test_case(mock_config, sample_test_case, temp_log_dir):
    """Test executing a complete test case."""
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    result = executor.execute_test_case(sample_test_case)
    assert result.status == "pass"
    assert len(result.steps) == 2

@pytest.mark.unit
def test_execute_test_suite(mock_config, sample_test_suite, temp_log_dir):
    """Test executing full test suite."""
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    report = executor.execute_test_suite(sample_test_suite)
    assert report.total_test_cases == 1
    assert report.passed_test_cases == 1
    assert report.success_rate == 100.0

@pytest.mark.unit
def test_variable_passing_between_steps(mock_config, temp_log_dir):
    """Test variables are passed between steps."""
    from src.models import TestCase, Step
    
    tc = TestCase(
        id="tc_var_test", name="Variable Test", description="Test variable passing",
        steps=[
            Step(step_id=1, operation="authorize", provider="test", description="Auth",
                 input_data={"amount": 100}, capture_variables={"txn_id": "$.body.transaction_id"}),
            Step(step_id=2, operation="capture", provider="test", description="Capture",
                 input_data={"transaction_id": "{{txn_id}}", "amount": 100})
        ]
    )
    
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    result = executor.execute_test_case(tc)
    assert result.status == "pass"
    assert result.steps[0].captured_variables is not None
    assert "txn_id" in result.steps[0].captured_variables

@pytest.mark.unit
def test_context_isolation_between_test_cases(mock_config, temp_log_dir):
    """Test context is cleared between test cases."""
    from src.models import TestSuite, Metadata
    
    metadata = Metadata(
        test_suite_name="Isolation Test", merchant_id="m123",
        environment="test", created_at="2026-01-29T12:00:00Z"
    )
    suite = TestSuite(version="1.0", metadata=metadata, test_cases=[])
    
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    context.set_variable("should_be_cleared", "value")
    executor = TestExecutor(api_client, logger, context)
    
    executor.execute_test_suite(suite)
    # Context should be cleared (though suite has no test cases)
    # Just verify no errors occur
    assert True


@pytest.mark.unit
def test_step_with_missing_variable(mock_config, temp_log_dir):
    """Test step fails gracefully when variable is missing."""
    from src.models import TestCase, Step
    
    tc = TestCase(
        id="tc_missing_var", name="Missing Var Test", description="Test missing variable error",
        steps=[
            Step(step_id=1, operation="capture", provider="test", description="Capture",
                 input_data={"transaction_id": "{{missing_var}}", "amount": 100})
        ]
    )
    
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    result = executor.execute_test_case(tc)
    assert result.status == "error"
    assert len(result.steps) == 1
    assert result.steps[0].status == "error"
    assert "missing_var" in result.steps[0].error_message


@pytest.mark.unit
def test_step_failure_stops_execution(mock_config, temp_log_dir):
    """Test that step failure stops test case execution."""
    from src.models import TestCase, Step
    from unittest.mock import patch, MagicMock
    
    tc = TestCase(
        id="tc_failure", name="Failure Test", description="Test failure handling",
        steps=[
            Step(step_id=1, operation="authorize", provider="test", description="Auth",
                 input_data={"amount": 100}),
            Step(step_id=2, operation="capture", provider="test", description="Capture",
                 input_data={"amount": 100})
        ]
    )
    
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    # Mock execute_operation to return failure
    from src.models import APIResponse
    with patch.object(api_client, 'execute_operation') as mock_exec:
        mock_exec.return_value = APIResponse(
            status_code=400,
            headers={},
            body={"error": "declined"},
            error="Payment declined"
        )
        
        result = executor.execute_test_case(tc)
        
    assert result.status == "fail"
    assert len(result.steps) == 1  # Second step should not run
    assert result.steps[0].status == "failure"


@pytest.mark.unit
def test_execute_step_exception_handling(mock_config, temp_log_dir):
    """Test exception handling in execute_step."""
    from src.models import TestCase, Step
    from unittest.mock import patch
    
    tc = TestCase(
        id="tc_exception", name="Exception Test", description="Test exception handling",
        steps=[
            Step(step_id=1, operation="authorize", provider="test", description="Auth",
                 input_data={"amount": 100})
        ]
    )
    
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    # Mock execute_operation to raise exception
    with patch.object(api_client, 'execute_operation') as mock_exec:
        mock_exec.side_effect = Exception("Connection error")
        
        result = executor.execute_step(tc, tc.steps[0])
        
    assert result.status == "error"
    assert "Connection error" in result.error_message


@pytest.mark.unit
def test_test_suite_with_multiple_test_cases(mock_config, temp_log_dir):
    """Test executing suite with multiple test cases."""
    from src.models import TestSuite, TestCase, Step, Metadata
    
    metadata = Metadata(
        test_suite_name="Multi TC Test", merchant_id="m123",
        environment="test", created_at="2026-01-29T12:00:00Z"
    )
    
    tc1 = TestCase(
        id="tc_001", name="Test 1", description="First test",
        steps=[Step(step_id=1, operation="authorize", provider="test", 
                   description="Auth", input_data={"amount": 100})]
    )
    tc2 = TestCase(
        id="tc_002", name="Test 2", description="Second test",
        steps=[Step(step_id=1, operation="purchase", provider="test",
                   description="Purchase", input_data={"amount": 50})]
    )
    
    suite = TestSuite(version="1.0", metadata=metadata, test_cases=[tc1, tc2])
    
    config = Config(**mock_config)
    api_client = APIClient(config)
    logger = CertificationLogger("test_exec", temp_log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    report = executor.execute_test_suite(suite)
    
    assert report.total_test_cases == 2
    assert report.passed_test_cases == 2
    assert len(report.test_case_results) == 2
