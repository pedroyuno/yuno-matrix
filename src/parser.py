"""
Test case parser for MATRIX.

Loads and validates JSON test case files, converting them to TestSuite objects.
"""

import json
from pathlib import Path
from typing import Union
from pydantic import ValidationError

from src.models import TestSuite


class TestCaseParseError(Exception):
    """Exception raised when test case parsing fails."""
    pass


class TestCaseParser:
    """Parser for MATRIX test case JSON files."""

    @staticmethod
    def load_from_file(file_path: Union[str, Path]) -> TestSuite:
        """
        Load and parse a test case JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            TestSuite object

        Raises:
            FileNotFoundError: If file doesn't exist
            TestCaseParseError: If file cannot be parsed or validated
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Test case file not found: {file_path}")

        if not path.is_file():
            raise TestCaseParseError(f"Path is not a file: {file_path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise TestCaseParseError(f"Invalid JSON in file {file_path}: {str(e)}")
        except IOError as e:
            raise TestCaseParseError(f"Error reading file {file_path}: {str(e)}")

        return TestCaseParser.parse_test_suite(data)

    @staticmethod
    def validate_schema(data: dict) -> bool:
        """
        Validate that data conforms to TestSuite schema.

        Args:
            data: Dictionary to validate

        Returns:
            True if valid

        Raises:
            TestCaseParseError: If validation fails
        """
        try:
            TestSuite(**data)
            return True
        except ValidationError as e:
            raise TestCaseParseError(f"Schema validation failed: {str(e)}")

    @staticmethod
    def parse_test_suite(data: dict) -> TestSuite:
        """
        Parse dictionary data into a TestSuite object.

        Args:
            data: Dictionary containing test suite data

        Returns:
            TestSuite object

        Raises:
            TestCaseParseError: If parsing or validation fails
        """
        if not isinstance(data, dict):
            raise TestCaseParseError(f"Expected dict, got {type(data).__name__}")

        try:
            test_suite = TestSuite(**data)
            return test_suite
        except ValidationError as e:
            # Extract more user-friendly error messages
            error_messages = []
            for error in e.errors():
                loc = " -> ".join(str(l) for l in error['loc'])
                msg = error['msg']
                error_messages.append(f"{loc}: {msg}")

            raise TestCaseParseError(
                f"Test suite validation failed:\n" + "\n".join(error_messages)
            )
        except Exception as e:
            raise TestCaseParseError(f"Unexpected error parsing test suite: {str(e)}")

    @staticmethod
    def load_from_string(json_string: str) -> TestSuite:
        """
        Parse a JSON string into a TestSuite object.

        Args:
            json_string: JSON string containing test suite data

        Returns:
            TestSuite object

        Raises:
            TestCaseParseError: If parsing fails
        """
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as e:
            raise TestCaseParseError(f"Invalid JSON string: {str(e)}")

        return TestCaseParser.parse_test_suite(data)
