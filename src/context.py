"""
Execution context manager for MATRIX.

Manages variable storage and substitution between test steps.
"""

import re
from typing import Any, Dict, Optional
from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JsonPathParserError


class ContextError(Exception):
    """Exception raised for context-related errors."""
    pass


class ExecutionContext:
    """
    Manages execution context for test cases.

    Handles variable storage, substitution, and extraction from API responses.
    """

    def __init__(self):
        """Initialize empty context."""
        self._variables: Dict[str, Any] = {}

    def set_variable(self, name: str, value: Any) -> None:
        """
        Store a variable in the context.

        Args:
            name: Variable name
            value: Variable value (can be any JSON-serializable type)
        """
        if not isinstance(name, str) or not name:
            raise ContextError(f"Variable name must be a non-empty string, got: {name}")

        self._variables[name] = value

    def get_variable(self, name: str) -> Any:
        """
        Retrieve a variable from the context.

        Args:
            name: Variable name

        Returns:
            Variable value

        Raises:
            ContextError: If variable not found
        """
        if name not in self._variables:
            available = ", ".join(self._variables.keys()) if self._variables else "none"
            raise ContextError(
                f"Variable '{name}' not found in context. "
                f"Available variables: {available}"
            )
        return self._variables[name]

    def has_variable(self, name: str) -> bool:
        """
        Check if a variable exists in the context.

        Args:
            name: Variable name

        Returns:
            True if variable exists, False otherwise
        """
        return name in self._variables

    def clear(self) -> None:
        """Clear all variables from the context."""
        self._variables.clear()

    def get_all_variables(self) -> Dict[str, Any]:
        """
        Get a copy of all variables.

        Returns:
            Dictionary of all variables
        """
        return self._variables.copy()

    def substitute_variables(self, data: Any) -> Any:
        """
        Substitute {{variable_name}} placeholders with actual values.

        Recursively processes dictionaries, lists, and strings.

        Args:
            data: Data structure with potential variable placeholders

        Returns:
            Data with variables substituted

        Raises:
            ContextError: If referenced variable not found
        """
        if isinstance(data, dict):
            return {key: self.substitute_variables(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.substitute_variables(item) for item in data]
        elif isinstance(data, str):
            return self._substitute_string(data)
        else:
            # Numbers, booleans, None - return as is
            return data

    def _substitute_string(self, text: str) -> Any:
        """
        Substitute variables in a string.

        Supports:
        - Full replacement: "{{var}}" -> value (preserves type)
        - Partial replacement: "prefix_{{var}}_suffix" -> "prefix_value_suffix"

        Args:
            text: String with potential variable placeholders

        Returns:
            Substituted value (may be non-string if full replacement)
        """
        # Pattern to match {{variable_name}}
        pattern = r'\{\{(\w+)\}\}'

        # Check if entire string is a single variable reference
        match = re.fullmatch(pattern, text)
        if match:
            var_name = match.group(1)
            return self.get_variable(var_name)

        # Multiple or partial variable references - replace within string
        def replace_var(match_obj):
            var_name = match_obj.group(1)
            value = self.get_variable(var_name)
            return str(value)

        result = re.sub(pattern, replace_var, text)
        return result

    def extract_from_response(self, response: Dict[str, Any], jsonpath: str) -> Any:
        """
        Extract a value from an API response using JSONPath.

        Args:
            response: API response dictionary
            jsonpath: JSONPath expression (e.g., "$.body.transaction_id")

        Returns:
            Extracted value

        Raises:
            ContextError: If JSONPath is invalid or no match found
        """
        if not isinstance(response, dict):
            raise ContextError(f"Response must be a dictionary, got {type(response).__name__}")

        try:
            jsonpath_expr = jsonpath_parse(jsonpath)
        except JsonPathParserError as e:
            raise ContextError(f"Invalid JSONPath expression '{jsonpath}': {str(e)}")
        except Exception as e:
            raise ContextError(f"Error parsing JSONPath '{jsonpath}': {str(e)}")

        matches = jsonpath_expr.find(response)

        if not matches:
            raise ContextError(
                f"JSONPath '{jsonpath}' did not match any values in response"
            )

        # Return first match
        return matches[0].value

    def capture_variables_from_response(
        self,
        response: Dict[str, Any],
        capture_spec: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Extract and store multiple variables from a response.

        Args:
            response: API response dictionary
            capture_spec: Dict mapping variable names to JSONPath expressions

        Returns:
            Dictionary of captured variables

        Raises:
            ContextError: If extraction fails
        """
        if not capture_spec:
            return {}

        captured = {}
        for var_name, jsonpath in capture_spec.items():
            try:
                value = self.extract_from_response(response, jsonpath)
                self.set_variable(var_name, value)
                captured[var_name] = value
            except ContextError as e:
                raise ContextError(
                    f"Failed to capture variable '{var_name}' using JSONPath '{jsonpath}': {str(e)}"
                )

        return captured

    def __repr__(self) -> str:
        """String representation of context."""
        var_count = len(self._variables)
        var_names = ", ".join(self._variables.keys()) if self._variables else "none"
        return f"ExecutionContext({var_count} variables: {var_names})"
