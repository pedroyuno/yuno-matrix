"""
Unit tests for MATRIX test case parser.

Target coverage: 85%+
"""

import pytest
import json
from pathlib import Path

from src.parser import TestCaseParser, TestCaseParseError
from src.models import TestSuite


# ============================================================================
# Load From File Tests
# ============================================================================

@pytest.mark.unit
def test_load_valid_testcase_file():
    """Test loading a valid test case JSON file."""
    test_file = Path("tests/fixtures/valid_testcase.json")
    test_suite = TestCaseParser.load_from_file(test_file)

    assert isinstance(test_suite, TestSuite)
    assert test_suite.version == "1.0"
    assert test_suite.metadata.test_suite_name == "Test Suite"
    assert len(test_suite.test_cases) == 1


@pytest.mark.unit
def test_load_nonexistent_file():
    """Test loading non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError) as exc_info:
        TestCaseParser.load_from_file("nonexistent_file.json")
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.unit
def test_load_directory_path(tmp_path):
    """Test loading a directory path raises error."""
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()

    with pytest.raises(TestCaseParseError) as exc_info:
        TestCaseParser.load_from_file(dir_path)
    assert "not a file" in str(exc_info.value).lower()


@pytest.mark.unit
def test_load_invalid_json(tmp_path):
    """Test loading file with invalid JSON syntax."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{ invalid json }", encoding="utf-8")

    with pytest.raises(TestCaseParseError) as exc_info:
        TestCaseParser.load_from_file(invalid_file)
    assert "invalid json" in str(exc_info.value).lower()


@pytest.mark.unit
def test_load_empty_file(tmp_path):
    """Test loading empty JSON file."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("{}", encoding="utf-8")

    with pytest.raises(TestCaseParseError) as exc_info:
        TestCaseParser.load_from_file(empty_file)
    assert "validation failed" in str(exc_info.value).lower()


@pytest.mark.unit
def test_load_with_utf8_encoding(tmp_path):
    """Test loading file with UTF-8 encoding and special characters."""
    test_data = {
        "version": "1.0",
        "metadata": {
            "test_suite_name": "Test with émojis 🎉",
            "merchant_id": "merchant_123",
            "environment": "test",
            "created_at": "2026-01-29T12:00:00Z"
        },
        "test_cases": []
    }

    test_file = tmp_path / "utf8_test.json"
    test_file.write_text(json.dumps(test_data, ensure_ascii=False), encoding="utf-8")

    test_suite = TestCaseParser.load_from_file(test_file)
    assert "émojis" in test_suite.metadata.test_suite_name
    assert "🎉" in test_suite.metadata.test_suite_name


# ============================================================================
# Parse Test Suite Tests
# ============================================================================

@pytest.mark.unit
def test_parse_valid_test_suite(sample_test_suite):
    """Test parsing valid test suite data."""
    data = sample_test_suite.model_dump()
    parsed = TestCaseParser.parse_test_suite(data)

    assert isinstance(parsed, TestSuite)
    assert parsed.version == sample_test_suite.version
    assert parsed.metadata.test_suite_name == sample_test_suite.metadata.test_suite_name


@pytest.mark.unit
def test_parse_missing_required_field():
    """Test parsing with missing required fields."""
    data = {
        "version": "1.0",
        # missing metadata
        "test_cases": []
    }

    with pytest.raises(TestCaseParseError) as exc_info:
        TestCaseParser.parse_test_suite(data)
    assert "metadata" in str(exc_info.value).lower()


@pytest.mark.unit
def test_parse_invalid_type():
    """Test parsing with wrong data type."""
    with pytest.raises(TestCaseParseError) as exc_info:
        TestCaseParser.parse_test_suite("not a dict")
    assert "expected dict" in str(exc_info.value).lower()


@pytest.mark.unit
def test_parse_invalid_version():
    """Test parsing with invalid version."""
    data = {
        "version": "",  # Empty version
        "metadata": {
            "test_suite_name": "Test",
            "merchant_id": "m123",
            "environment": "test",
            "created_at": "2026-01-29T12:00:00Z"
        },
        "test_cases": []
    }

    with pytest.raises(TestCaseParseError) as exc_info:
        TestCaseParser.parse_test_suite(data)
    assert "validation failed" in str(exc_info.value).lower()


@pytest.mark.unit
def test_parse_invalid_step_sequence():
    """Test parsing test case with non-sequential step IDs."""
    data = {
        "version": "1.0",
        "metadata": {
            "test_suite_name": "Test",
            "merchant_id": "m123",
            "environment": "test",
            "created_at": "2026-01-29T12:00:00Z"
        },
        "test_cases": [
            {
                "id": "tc_001",
                "name": "Test",
                "description": "Test",
                "steps": [
                    {
                        "step_id": 1,
                        "operation": "authorize",
                        "provider": "p",
                        "description": "d",
                        "input_data": {}
                    },
                    {
                        "step_id": 3,  # Skip 2
                        "operation": "capture",
                        "provider": "p",
                        "description": "d",
                        "input_data": {}
                    }
                ]
            }
        ]
    }

    with pytest.raises(TestCaseParseError) as exc_info:
        TestCaseParser.parse_test_suite(data)
    assert "sequential" in str(exc_info.value).lower()


# ============================================================================
# Validate Schema Tests
# ============================================================================

@pytest.mark.unit
def test_validate_schema_valid(sample_test_suite):
    """Test schema validation with valid data."""
    data = sample_test_suite.model_dump()
    assert TestCaseParser.validate_schema(data) is True


@pytest.mark.unit
def test_validate_schema_invalid():
    """Test schema validation with invalid data."""
    data = {"version": "1.0"}  # Missing required fields

    with pytest.raises(TestCaseParseError):
        TestCaseParser.validate_schema(data)


# ============================================================================
# Load From String Tests
# ============================================================================

@pytest.mark.unit
def test_load_from_string_valid():
    """Test parsing valid JSON string."""
    json_string = """{
        "version": "1.0",
        "metadata": {
            "test_suite_name": "String Test",
            "merchant_id": "m123",
            "environment": "test",
            "created_at": "2026-01-29T12:00:00Z"
        },
        "test_cases": []
    }"""

    test_suite = TestCaseParser.load_from_string(json_string)
    assert isinstance(test_suite, TestSuite)
    assert test_suite.metadata.test_suite_name == "String Test"


@pytest.mark.unit
def test_load_from_string_invalid_json():
    """Test parsing invalid JSON string."""
    invalid_json = "{ invalid json }"

    with pytest.raises(TestCaseParseError) as exc_info:
        TestCaseParser.load_from_string(invalid_json)
    assert "invalid json" in str(exc_info.value).lower()


@pytest.mark.unit
def test_load_from_string_invalid_schema():
    """Test parsing JSON string with invalid schema."""
    json_string = '{"version": "1.0"}'  # Missing required fields

    with pytest.raises(TestCaseParseError):
        TestCaseParser.load_from_string(json_string)


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.unit
def test_parse_empty_test_cases():
    """Test parsing test suite with empty test_cases list."""
    data = {
        "version": "1.0",
        "metadata": {
            "test_suite_name": "Empty Test Suite",
            "merchant_id": "m123",
            "environment": "test",
            "created_at": "2026-01-29T12:00:00Z"
        },
        "test_cases": []
    }

    test_suite = TestCaseParser.parse_test_suite(data)
    assert len(test_suite.test_cases) == 0


@pytest.mark.unit
def test_parse_multiple_test_cases():
    """Test parsing test suite with multiple test cases."""
    data = {
        "version": "1.0",
        "metadata": {
            "test_suite_name": "Multi Test Suite",
            "merchant_id": "m123",
            "environment": "test",
            "created_at": "2026-01-29T12:00:00Z"
        },
        "test_cases": [
            {
                "id": "tc_001",
                "name": "Test 1",
                "description": "First test",
                "steps": [
                    {
                        "step_id": 1,
                        "operation": "authorize",
                        "provider": "p",
                        "description": "d",
                        "input_data": {}
                    }
                ]
            },
            {
                "id": "tc_002",
                "name": "Test 2",
                "description": "Second test",
                "steps": [
                    {
                        "step_id": 1,
                        "operation": "purchase",
                        "provider": "p",
                        "description": "d",
                        "input_data": {}
                    }
                ]
            }
        ]
    }

    test_suite = TestCaseParser.parse_test_suite(data)
    assert len(test_suite.test_cases) == 2
    assert test_suite.test_cases[0].id == "tc_001"
    assert test_suite.test_cases[1].id == "tc_002"


@pytest.mark.unit
def test_parse_complex_input_data():
    """Test parsing step with complex nested input_data."""
    data = {
        "version": "1.0",
        "metadata": {
            "test_suite_name": "Complex Data Test",
            "merchant_id": "m123",
            "environment": "test",
            "created_at": "2026-01-29T12:00:00Z"
        },
        "test_cases": [
            {
                "id": "tc_001",
                "name": "Complex Test",
                "description": "Test with nested data",
                "steps": [
                    {
                        "step_id": 1,
                        "operation": "authorize",
                        "provider": "p",
                        "description": "d",
                        "input_data": {
                            "amount": 100.50,
                            "currency": "USD",
                            "card": {
                                "number": "4111111111111111",
                                "cvv": "123",
                                "expiry": {
                                    "month": "12",
                                    "year": "2026"
                                }
                            },
                            "metadata": {
                                "user_id": "user_123",
                                "ip_address": "192.168.1.1"
                            }
                        }
                    }
                ]
            }
        ]
    }

    test_suite = TestCaseParser.parse_test_suite(data)
    step = test_suite.test_cases[0].steps[0]
    assert step.input_data["card"]["expiry"]["year"] == "2026"
    assert step.input_data["metadata"]["user_id"] == "user_123"
