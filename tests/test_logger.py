"""
Unit tests for MATRIX certification logger.

Target coverage: 85%+
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from src.logger import CertificationLogger
from src.models import (
    TestCase, Step, TestCaseResult, ExecutionReport,
    APIRequest, APIResponse, StepResult
)


# ============================================================================
# Logger Initialization Tests
# ============================================================================

@pytest.mark.unit
def test_logger_initialization(temp_log_dir):
    """Test logger initialization creates log directory."""
    logger = CertificationLogger("test_exec_001", temp_log_dir)

    assert logger.execution_id == "test_exec_001"
    assert Path(temp_log_dir).exists()
    assert logger.log_file.exists() is False  # Not written until close()


@pytest.mark.unit
def test_logger_creates_directory_if_missing(tmp_path):
    """Test logger creates log directory if it doesn't exist."""
    log_dir = tmp_path / "new_logs"
    logger = CertificationLogger("test_exec_002", str(log_dir))

    assert log_dir.exists()


# ============================================================================
# Log Step Tests
# ============================================================================

@pytest.mark.unit
def test_log_step_basic(temp_log_dir, sample_step_authorize, mock_api_request, mock_api_response):
    """Test logging a basic step."""
    logger = CertificationLogger("test_exec_003", temp_log_dir)

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test Case",
        step=sample_step_authorize,
        request=mock_api_request,
        response=mock_api_response,
        status="success",
        duration_ms=100
    )

    entries = logger.get_log_entries()
    assert len(entries) == 1

    entry = entries[0]
    assert entry["test_case_id"] == "tc_001"
    assert entry["step_id"] == 1
    assert entry["operation"] == "authorize"
    assert entry["status"] == "success"
    assert entry["duration_ms"] == 100


@pytest.mark.unit
def test_log_step_with_captured_variables(temp_log_dir, sample_step_authorize, mock_api_request, mock_api_response):
    """Test logging step with captured variables."""
    logger = CertificationLogger("test_exec_004", temp_log_dir)

    captured_vars = {"transaction_id": "txn_123", "auth_code": "AUTH456"}

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test Case",
        step=sample_step_authorize,
        request=mock_api_request,
        response=mock_api_response,
        status="success",
        duration_ms=150,
        captured_variables=captured_vars
    )

    entries = logger.get_log_entries()
    assert entries[0]["captured_variables"] == captured_vars


@pytest.mark.unit
def test_log_step_with_error(temp_log_dir, sample_step_authorize):
    """Test logging failed step with error message."""
    logger = CertificationLogger("test_exec_005", temp_log_dir)

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test Case",
        step=sample_step_authorize,
        request=None,
        response=None,
        status="error",
        error_message="Connection timeout"
    )

    entries = logger.get_log_entries()
    assert entries[0]["status"] == "error"
    assert entries[0]["error_message"] == "Connection timeout"


@pytest.mark.unit
def test_log_multiple_steps(temp_log_dir, sample_step_authorize, sample_step_capture, mock_api_request, mock_api_response):
    """Test logging multiple steps in sequence."""
    logger = CertificationLogger("test_exec_006", temp_log_dir)

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test",
        step=sample_step_authorize,
        request=mock_api_request,
        response=mock_api_response,
        status="success"
    )

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test",
        step=sample_step_capture,
        request=mock_api_request,
        response=mock_api_response,
        status="success"
    )

    entries = logger.get_log_entries()
    assert len(entries) == 2
    assert entries[0]["step_id"] == 1
    assert entries[1]["step_id"] == 2


# ============================================================================
# Sensitive Data Masking Tests
# ============================================================================

@pytest.mark.unit
def test_mask_card_number(temp_log_dir, sample_step_authorize):
    """Test card number masking in logs."""
    logger = CertificationLogger("test_exec_007", temp_log_dir)

    request = APIRequest(
        method="POST",
        url="https://api.test.com/pay",
        headers={},
        body={"card_number": "4111111111111111", "amount": 100}
    )

    response = APIResponse(
        status_code=200,
        headers={},
        body={"status": "success"}
    )

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test",
        step=sample_step_authorize,
        request=request,
        response=response,
        status="success"
    )

    entries = logger.get_log_entries()
    # Card number should be masked
    card_in_log = entries[0]["request"]["body"]["card_number"]
    assert "*" in card_in_log  # Contains masking
    assert card_in_log != "4111111111111111"  # Different from original


@pytest.mark.unit
def test_mask_authorization_header(temp_log_dir, sample_step_authorize):
    """Test API key/token masking in headers."""
    logger = CertificationLogger("test_exec_008", temp_log_dir)

    request = APIRequest(
        method="POST",
        url="https://api.test.com/pay",
        headers={"Authorization": "Bearer sk_live_abc123xyz789"},
        body={}
    )

    response = APIResponse(status_code=200, headers={}, body={})

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test",
        step=sample_step_authorize,
        request=request,
        response=response,
        status="success"
    )

    entries = logger.get_log_entries()
    auth_header = entries[0]["request"]["headers"]["Authorization"]
    assert "***" in auth_header
    assert "sk_live_abc123xyz789" not in auth_header


# ============================================================================
# Test Case Logging Tests
# ============================================================================

@pytest.mark.unit
def test_log_test_case_start(temp_log_dir, sample_test_case, capsys):
    """Test logging test case start."""
    logger = CertificationLogger("test_exec_009", temp_log_dir)

    logger.log_test_case_start(sample_test_case)

    captured = capsys.readouterr()
    assert sample_test_case.name in captured.out
    assert sample_test_case.id in captured.out


@pytest.mark.unit
def test_log_test_case_end_pass(temp_log_dir, capsys):
    """Test logging successful test case end."""
    logger = CertificationLogger("test_exec_010", temp_log_dir)

    result = TestCaseResult(
        test_case_id="tc_001",
        test_case_name="Test Case",
        status="pass",
        duration_ms=500
    )

    logger.log_test_case_end("tc_001", result)

    captured = capsys.readouterr()
    assert "PASS" in captured.out
    assert "500ms" in captured.out


@pytest.mark.unit
def test_log_test_case_end_fail(temp_log_dir, capsys):
    """Test logging failed test case end."""
    logger = CertificationLogger("test_exec_011", temp_log_dir)

    result = TestCaseResult(
        test_case_id="tc_001",
        test_case_name="Test Case",
        status="fail",
        error_message="Step 2 failed"
    )

    logger.log_test_case_end("tc_001", result)

    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "Step 2 failed" in captured.out


# ============================================================================
# Execution Summary Tests
# ============================================================================

@pytest.mark.unit
def test_log_execution_summary(temp_log_dir, capsys):
    """Test logging execution summary."""
    logger = CertificationLogger("test_exec_012", temp_log_dir)

    report = ExecutionReport(
        execution_id="test_exec_012",
        start_time="2026-01-29T10:00:00Z",
        test_suite_name="Test Suite",
        total_test_cases=10,
        passed_test_cases=8,
        failed_test_cases=1,
        error_test_cases=1,
        total_steps=25,
        duration_ms=5000
    )

    logger.log_execution_summary(report)

    captured = capsys.readouterr()
    assert "Execution Summary" in captured.out
    assert "Passed: 8" in captured.out
    assert "Failed: 1" in captured.out
    assert "Errors: 1" in captured.out
    assert "Total: 10" in captured.out
    assert "80.0%" in captured.out  # Success rate


# ============================================================================
# File Writing Tests
# ============================================================================

@pytest.mark.unit
def test_close_writes_log_file(temp_log_dir, sample_step_authorize, mock_api_request, mock_api_response):
    """Test that close() writes log file."""
    logger = CertificationLogger("test_exec_013", temp_log_dir)

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test",
        step=sample_step_authorize,
        request=mock_api_request,
        response=mock_api_response,
        status="success"
    )

    logger.close()

    # Verify file exists
    assert logger.log_file.exists()

    # Verify valid JSON
    with open(logger.log_file, 'r') as f:
        data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1


@pytest.mark.unit
def test_log_file_structure(temp_log_dir, sample_step_authorize, mock_api_request, mock_api_response):
    """Test log file has correct structure."""
    logger = CertificationLogger("test_exec_014", temp_log_dir)

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test Case",
        step=sample_step_authorize,
        request=mock_api_request,
        response=mock_api_response,
        status="success",
        duration_ms=200
    )

    logger.close()

    with open(logger.log_file, 'r') as f:
        data = json.load(f)
        entry = data[0]

        # Check required fields
        assert "timestamp" in entry
        assert "execution_id" in entry
        assert "test_case_id" in entry
        assert "step_id" in entry
        assert "operation" in entry
        assert "provider" in entry
        assert "status" in entry
        assert "request" in entry
        assert "response" in entry

        # Validate timestamp format (ISO 8601)
        datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))


@pytest.mark.unit
def test_log_file_naming(temp_log_dir):
    """Test log file has correct naming pattern."""
    logger = CertificationLogger("20260129_120000", temp_log_dir)

    expected_name = "execution_20260129_120000.json"
    assert logger.log_file.name == expected_name


# ============================================================================
# Utility Method Tests
# ============================================================================

@pytest.mark.unit
def test_get_log_entries(temp_log_dir, sample_step_authorize, mock_api_request, mock_api_response):
    """Test getting log entries."""
    logger = CertificationLogger("test_exec_015", temp_log_dir)

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test",
        step=sample_step_authorize,
        request=mock_api_request,
        response=mock_api_response,
        status="success"
    )

    entries = logger.get_log_entries()
    assert isinstance(entries, list)
    assert len(entries) == 1


@pytest.mark.unit
def test_get_log_entries_returns_copy(temp_log_dir, sample_step_authorize, mock_api_request, mock_api_response):
    """Test that get_log_entries returns a copy."""
    logger = CertificationLogger("test_exec_016", temp_log_dir)

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test",
        step=sample_step_authorize,
        request=mock_api_request,
        response=mock_api_response,
        status="success"
    )

    entries = logger.get_log_entries()
    entries.append({"fake": "entry"})

    # Original should not be modified
    assert len(logger.get_log_entries()) == 1


@pytest.mark.unit
def test_get_log_file_path(temp_log_dir):
    """Test getting log file path."""
    logger = CertificationLogger("test_exec_017", temp_log_dir)

    path = logger.get_log_file_path()
    assert isinstance(path, Path)
    assert "execution_test_exec_017.json" in str(path)


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.unit
def test_log_step_without_request_response(temp_log_dir, sample_step_authorize):
    """Test logging step without request/response."""
    logger = CertificationLogger("test_exec_018", temp_log_dir)

    logger.log_step(
        test_case_id="tc_001",
        test_case_name="Test",
        step=sample_step_authorize,
        request=None,
        response=None,
        status="error",
        error_message="Step skipped"
    )

    entries = logger.get_log_entries()
    assert "request" not in entries[0]
    assert "response" not in entries[0]


@pytest.mark.unit
def test_multiple_loggers_different_dirs(tmp_path):
    """Test multiple loggers with different directories."""
    dir1 = tmp_path / "logs1"
    dir2 = tmp_path / "logs2"

    logger1 = CertificationLogger("exec_001", str(dir1))
    logger2 = CertificationLogger("exec_002", str(dir2))

    assert dir1.exists()
    assert dir2.exists()
    assert logger1.log_file != logger2.log_file
