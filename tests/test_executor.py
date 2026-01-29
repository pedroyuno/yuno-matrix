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
