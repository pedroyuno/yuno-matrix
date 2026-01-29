"""
Unit tests for MATRIX execution context.

Target coverage: 90%+
"""

import pytest
from src.context import ExecutionContext, ContextError


# ============================================================================
# Set and Get Variable Tests
# ============================================================================

@pytest.mark.unit
def test_set_and_get_variable():
    """Test setting and getting a variable."""
    context = ExecutionContext()
    context.set_variable("txn_id", "12345")

    assert context.get_variable("txn_id") == "12345"


@pytest.mark.unit
def test_set_variable_different_types():
    """Test storing variables of different types."""
    context = ExecutionContext()

    context.set_variable("string_var", "test")
    context.set_variable("int_var", 123)
    context.set_variable("float_var", 45.67)
    context.set_variable("bool_var", True)
    context.set_variable("none_var", None)
    context.set_variable("dict_var", {"key": "value"})
    context.set_variable("list_var", [1, 2, 3])

    assert context.get_variable("string_var") == "test"
    assert context.get_variable("int_var") == 123
    assert context.get_variable("float_var") == 45.67
    assert context.get_variable("bool_var") is True
    assert context.get_variable("none_var") is None
    assert context.get_variable("dict_var") == {"key": "value"}
    assert context.get_variable("list_var") == [1, 2, 3]


@pytest.mark.unit
def test_get_missing_variable():
    """Test getting non-existent variable raises error."""
    context = ExecutionContext()

    with pytest.raises(ContextError) as exc_info:
        context.get_variable("missing_var")

    assert "not found" in str(exc_info.value)
    assert "missing_var" in str(exc_info.value)


@pytest.mark.unit
def test_get_missing_variable_with_available_vars():
    """Test error message lists available variables."""
    context = ExecutionContext()
    context.set_variable("var1", "value1")
    context.set_variable("var2", "value2")

    with pytest.raises(ContextError) as exc_info:
        context.get_variable("missing_var")

    error_msg = str(exc_info.value)
    assert "var1" in error_msg or "var2" in error_msg


@pytest.mark.unit
def test_set_variable_invalid_name():
    """Test setting variable with invalid name."""
    context = ExecutionContext()

    with pytest.raises(ContextError):
        context.set_variable("", "value")  # Empty name

    with pytest.raises(ContextError):
        context.set_variable(123, "value")  # Non-string name


@pytest.mark.unit
def test_has_variable():
    """Test checking if variable exists."""
    context = ExecutionContext()
    context.set_variable("existing", "value")

    assert context.has_variable("existing") is True
    assert context.has_variable("missing") is False


@pytest.mark.unit
def test_overwrite_variable():
    """Test overwriting an existing variable."""
    context = ExecutionContext()
    context.set_variable("var", "old_value")
    context.set_variable("var", "new_value")

    assert context.get_variable("var") == "new_value"


# ============================================================================
# Variable Substitution Tests
# ============================================================================

@pytest.mark.unit
def test_substitute_single_variable():
    """Test substituting a single variable."""
    context = ExecutionContext()
    context.set_variable("amount", 100)

    data = {"charge": "{{amount}}"}
    result = context.substitute_variables(data)

    assert result["charge"] == 100  # Type preserved


@pytest.mark.unit
def test_substitute_multiple_variables():
    """Test substituting multiple variables in nested dict."""
    context = ExecutionContext()
    context.set_variable("amount", 100.50)
    context.set_variable("currency", "USD")
    context.set_variable("txn_id", "txn_123")

    data = {
        "amount": "{{amount}}",
        "currency": "{{currency}}",
        "transaction": {
            "id": "{{txn_id}}",
            "amount": "{{amount}}"
        }
    }

    result = context.substitute_variables(data)

    assert result["amount"] == 100.50
    assert result["currency"] == "USD"
    assert result["transaction"]["id"] == "txn_123"
    assert result["transaction"]["amount"] == 100.50


@pytest.mark.unit
def test_substitute_in_string():
    """Test variable substitution within a string."""
    context = ExecutionContext()
    context.set_variable("user", "john")
    context.set_variable("id", "123")

    data = {"message": "User {{user}} has ID {{id}}"}
    result = context.substitute_variables(data)

    assert result["message"] == "User john has ID 123"


@pytest.mark.unit
def test_substitute_in_list():
    """Test variable substitution in lists."""
    context = ExecutionContext()
    context.set_variable("item1", "apple")
    context.set_variable("item2", "banana")

    data = {"items": ["{{item1}}", "{{item2}}", "orange"]}
    result = context.substitute_variables(data)

    assert result["items"] == ["apple", "banana", "orange"]


@pytest.mark.unit
def test_substitute_preserves_types():
    """Test that full variable substitution preserves types."""
    context = ExecutionContext()
    context.set_variable("amount", 100.50)
    context.set_variable("active", True)
    context.set_variable("count", 42)

    data = {
        "amount": "{{amount}}",  # Should become float
        "active": "{{active}}",  # Should become bool
        "count": "{{count}}"     # Should become int
    }

    result = context.substitute_variables(data)

    assert result["amount"] == 100.50
    assert isinstance(result["amount"], float)
    assert result["active"] is True
    assert isinstance(result["active"], bool)
    assert result["count"] == 42
    assert isinstance(result["count"], int)


@pytest.mark.unit
def test_substitute_missing_variable():
    """Test substitution fails with missing variable."""
    context = ExecutionContext()
    context.set_variable("existing", "value")

    data = {"field": "{{missing_var}}"}

    with pytest.raises(ContextError) as exc_info:
        context.substitute_variables(data)

    assert "missing_var" in str(exc_info.value)


@pytest.mark.unit
def test_substitute_no_variables():
    """Test substitution with no variable placeholders."""
    context = ExecutionContext()
    context.set_variable("var", "value")

    data = {
        "string": "plain text",
        "number": 123,
        "bool": True,
        "nested": {"key": "value"}
    }

    result = context.substitute_variables(data)

    assert result == data


# ============================================================================
# JSONPath Extraction Tests
# ============================================================================

@pytest.mark.unit
def test_extract_from_response_simple():
    """Test extracting simple value using JSONPath."""
    context = ExecutionContext()
    response = {"body": {"transaction_id": "txn_789"}}

    value = context.extract_from_response(response, "$.body.transaction_id")

    assert value == "txn_789"


@pytest.mark.unit
def test_extract_from_response_nested():
    """Test extracting nested value using JSONPath."""
    context = ExecutionContext()
    response = {
        "body": {
            "data": {
                "transaction": {
                    "id": "txn_abc",
                    "amount": 100.00
                }
            }
        }
    }

    value = context.extract_from_response(response, "$.body.data.transaction.id")
    assert value == "txn_abc"

    amount = context.extract_from_response(response, "$.body.data.transaction.amount")
    assert amount == 100.00


@pytest.mark.unit
def test_extract_from_response_array():
    """Test extracting from array using JSONPath."""
    context = ExecutionContext()
    response = {
        "body": {
            "items": [
                {"id": "item_1"},
                {"id": "item_2"}
            ]
        }
    }

    # Get first item
    value = context.extract_from_response(response, "$.body.items[0].id")
    assert value == "item_1"


@pytest.mark.unit
def test_extract_invalid_jsonpath():
    """Test extraction with invalid JSONPath expression."""
    context = ExecutionContext()
    response = {"body": {"key": "value"}}

    with pytest.raises(ContextError) as exc_info:
        context.extract_from_response(response, "$.body[invalid")

    assert "invalid jsonpath" in str(exc_info.value).lower()


@pytest.mark.unit
def test_extract_no_match():
    """Test extraction when JSONPath doesn't match."""
    context = ExecutionContext()
    response = {"body": {"key": "value"}}

    with pytest.raises(ContextError) as exc_info:
        context.extract_from_response(response, "$.nonexistent.path")

    assert "did not match" in str(exc_info.value)


@pytest.mark.unit
def test_extract_from_non_dict():
    """Test extraction from non-dictionary raises error."""
    context = ExecutionContext()

    with pytest.raises(ContextError) as exc_info:
        context.extract_from_response("not a dict", "$.key")

    assert "must be a dictionary" in str(exc_info.value)


# ============================================================================
# Capture Variables Tests
# ============================================================================

@pytest.mark.unit
def test_capture_variables_from_response():
    """Test capturing multiple variables from response."""
    context = ExecutionContext()
    response = {
        "body": {
            "transaction_id": "txn_123",
            "auth_code": "AUTH456",
            "amount": 100.00
        }
    }

    capture_spec = {
        "txn_id": "$.body.transaction_id",
        "auth": "$.body.auth_code"
    }

    captured = context.capture_variables_from_response(response, capture_spec)

    assert captured == {"txn_id": "txn_123", "auth": "AUTH456"}
    assert context.get_variable("txn_id") == "txn_123"
    assert context.get_variable("auth") == "AUTH456"


@pytest.mark.unit
def test_capture_variables_empty_spec():
    """Test capturing with empty spec returns empty dict."""
    context = ExecutionContext()
    response = {"body": {"key": "value"}}

    captured = context.capture_variables_from_response(response, {})

    assert captured == {}


@pytest.mark.unit
def test_capture_variables_failure():
    """Test capture failure with invalid JSONPath."""
    context = ExecutionContext()
    response = {"body": {"key": "value"}}

    capture_spec = {"var": "$.nonexistent"}

    with pytest.raises(ContextError) as exc_info:
        context.capture_variables_from_response(response, capture_spec)

    assert "failed to capture" in str(exc_info.value).lower()
    assert "var" in str(exc_info.value)


# ============================================================================
# Context Management Tests
# ============================================================================

@pytest.mark.unit
def test_clear_context():
    """Test clearing all variables."""
    context = ExecutionContext()
    context.set_variable("var1", "value1")
    context.set_variable("var2", "value2")

    context.clear()

    assert not context.has_variable("var1")
    assert not context.has_variable("var2")


@pytest.mark.unit
def test_get_all_variables():
    """Test getting all variables."""
    context = ExecutionContext()
    context.set_variable("var1", "value1")
    context.set_variable("var2", 123)

    all_vars = context.get_all_variables()

    assert all_vars == {"var1": "value1", "var2": 123}


@pytest.mark.unit
def test_get_all_variables_returns_copy():
    """Test that get_all_variables returns a copy."""
    context = ExecutionContext()
    context.set_variable("var1", "value1")

    all_vars = context.get_all_variables()
    all_vars["var2"] = "value2"  # Modify returned dict

    # Original context should not be modified
    assert not context.has_variable("var2")


@pytest.mark.unit
def test_context_repr():
    """Test string representation of context."""
    context = ExecutionContext()
    repr_str = repr(context)
    assert "ExecutionContext" in repr_str
    assert "0 variables" in repr_str

    context.set_variable("var1", "value1")
    repr_str = repr(context)
    assert "1 variables" in repr_str
    assert "var1" in repr_str


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.unit
def test_variable_with_special_characters():
    """Test variables with underscores and numbers."""
    context = ExecutionContext()
    context.set_variable("var_with_underscore", "value1")
    context.set_variable("var123", "value2")

    data = {
        "field1": "{{var_with_underscore}}",
        "field2": "{{var123}}"
    }

    result = context.substitute_variables(data)

    assert result["field1"] == "value1"
    assert result["field2"] == "value2"


@pytest.mark.unit
def test_deeply_nested_substitution():
    """Test substitution in deeply nested structures."""
    context = ExecutionContext()
    context.set_variable("value", "deep_value")

    data = {
        "level1": {
            "level2": {
                "level3": {
                    "level4": {
                        "field": "{{value}}"
                    }
                }
            }
        }
    }

    result = context.substitute_variables(data)

    assert result["level1"]["level2"]["level3"]["level4"]["field"] == "deep_value"


@pytest.mark.unit
def test_substitute_complex_types():
    """Test substituting complex variable types."""
    context = ExecutionContext()
    context.set_variable("obj", {"nested": "value"})
    context.set_variable("arr", [1, 2, 3])

    data = {
        "object_field": "{{obj}}",
        "array_field": "{{arr}}"
    }

    result = context.substitute_variables(data)

    assert result["object_field"] == {"nested": "value"}
    assert result["array_field"] == [1, 2, 3]


@pytest.mark.unit
def test_empty_context_operations():
    """Test operations on empty context."""
    context = ExecutionContext()

    assert context.get_all_variables() == {}
    assert not context.has_variable("any_var")

    # Substitution with no variables should work
    data = {"field": "value"}
    result = context.substitute_variables(data)
    assert result == data
