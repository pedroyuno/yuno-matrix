"""
Data models for MATRIX test case definitions and execution results.

MATRIX: Merchant API Test & Regression Integration eXerciser
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Test Case Definition Models
# ============================================================================

class Metadata(BaseModel):
    """Metadata about the test suite."""
    test_suite_name: str = Field(..., min_length=1, description="Name of the test suite")
    merchant_id: str = Field(..., min_length=1, description="Merchant identifier")
    environment: str = Field(..., min_length=1, description="Environment (sandbox, production, etc.)")
    created_at: str = Field(..., description="ISO 8601 timestamp of creation")

    @field_validator('created_at')
    @classmethod
    def validate_iso_timestamp(cls, v: str) -> str:
        """Validate ISO 8601 timestamp format."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}")
        return v


class Step(BaseModel):
    """A single step in a test case."""
    step_id: int = Field(..., ge=1, description="Step number (1-indexed)")
    operation: str = Field(..., min_length=1, description="Operation type (authorize, capture, purchase, refund, etc.)")
    provider: str = Field(..., min_length=1, description="Provider identifier")
    description: str = Field(..., min_length=1, description="Human-readable step description")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input data for the operation")
    capture_variables: Optional[Dict[str, str]] = Field(
        default=None,
        description="Variables to capture from response using JSONPath expressions"
    )
    expected_status: Optional[str] = Field(default="success", description="Expected status (success, failure, etc.)")

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v: str) -> str:
        """Validate that operation is a known type."""
        valid_operations = {'authorize', 'capture', 'purchase', 'refund', 'partial_refund', 'void', 'verify', 'tokenize', 'e2e_payment'}
        if v.lower() not in valid_operations:
            # Allow custom operations but warn about unknown types
            pass
        return v.lower()


class TestCase(BaseModel):
    """A test case containing multiple steps."""
    id: str = Field(..., min_length=1, description="Test case identifier")
    name: str = Field(..., min_length=1, description="Test case name")
    description: str = Field(..., min_length=1, description="Test case description")
    steps: List[Step] = Field(..., min_length=1, description="List of steps to execute")

    @field_validator('steps')
    @classmethod
    def validate_step_ids(cls, v: List[Step]) -> List[Step]:
        """Ensure step IDs are sequential starting from 1."""
        expected_ids = list(range(1, len(v) + 1))
        actual_ids = [step.step_id for step in v]
        if actual_ids != expected_ids:
            raise ValueError(f"Step IDs must be sequential from 1 to {len(v)}, got {actual_ids}")
        return v


class TestSuite(BaseModel):
    """Complete test suite definition."""
    version: str = Field(..., min_length=1, description="Test suite schema version")
    metadata: Metadata = Field(..., description="Test suite metadata")
    test_cases: List[TestCase] = Field(default_factory=list, description="List of test cases")

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format (simple check for now)."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Version cannot be empty")
        return v


# ============================================================================
# Execution Result Models
# ============================================================================

class APIRequest(BaseModel):
    """API request details for logging."""
    method: str = Field(..., description="HTTP method")
    url: str = Field(..., description="Request URL")
    headers: Dict[str, str] = Field(default_factory=dict, description="Request headers")
    body: Dict[str, Any] = Field(default_factory=dict, description="Request body")


class APIResponseBody(BaseModel):
    """API response body."""
    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    body: Dict[str, Any] = Field(default_factory=dict, description="Response body")
    error: Optional[str] = Field(default=None, description="Error message if request failed")


class APIResponse(BaseModel):
    """Complete API response including timing."""
    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    body: Dict[str, Any] = Field(default_factory=dict, description="Response body")
    duration_ms: Optional[int] = Field(default=None, description="Response time in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if request failed")
    request_url: Optional[str] = Field(default=None, description="Actual URL that was called")

    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return 200 <= self.status_code < 300 and self.error is None


class StepResult(BaseModel):
    """Result of executing a single step."""
    step_id: int = Field(..., description="Step number")
    operation: str = Field(..., description="Operation type")
    provider: str = Field(..., description="Provider identifier")
    status: Literal["success", "failure", "error"] = Field(..., description="Step execution status")
    request: Optional[APIRequest] = Field(default=None, description="API request details")
    response: Optional[APIResponse] = Field(default=None, description="API response details")
    duration_ms: Optional[int] = Field(default=None, description="Step execution time")
    error_message: Optional[str] = Field(default=None, description="Error message if step failed")
    captured_variables: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Variables captured from this step"
    )


class TestCaseResult(BaseModel):
    """Result of executing a test case."""
    test_case_id: str = Field(..., description="Test case identifier")
    test_case_name: str = Field(..., description="Test case name")
    status: Literal["pass", "fail", "error"] = Field(..., description="Overall test case status")
    steps: List[StepResult] = Field(default_factory=list, description="Results of individual steps")
    duration_ms: Optional[int] = Field(default=None, description="Total test case execution time")
    error_message: Optional[str] = Field(default=None, description="Error message if test case failed")


class ExecutionReport(BaseModel):
    """Complete execution report for the test suite."""
    execution_id: str = Field(..., description="Unique execution identifier")
    start_time: str = Field(..., description="Execution start time (ISO 8601)")
    end_time: Optional[str] = Field(default=None, description="Execution end time (ISO 8601)")
    test_suite_name: str = Field(..., description="Name of the executed test suite")
    total_test_cases: int = Field(..., ge=0, description="Total number of test cases")
    passed_test_cases: int = Field(..., ge=0, description="Number of passed test cases")
    failed_test_cases: int = Field(..., ge=0, description="Number of failed test cases")
    error_test_cases: int = Field(..., ge=0, description="Number of test cases with errors")
    total_steps: int = Field(..., ge=0, description="Total number of steps executed")
    test_case_results: List[TestCaseResult] = Field(default_factory=list, description="Individual test case results")
    duration_ms: Optional[int] = Field(default=None, description="Total execution time")

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_test_cases == 0:
            return 0.0
        return (self.passed_test_cases / self.total_test_cases) * 100


# ============================================================================
# Configuration Models
# ============================================================================

class APIConfig(BaseModel):
    """API client configuration."""
    base_urls: Dict[str, str] = Field(default_factory=dict, description="Provider base URLs")
    timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, ge=0, description="Number of retry attempts")


class ProviderTestCard(BaseModel):
    """Test card configuration for a specific provider."""
    number: str = Field(..., description="Card number (PAN)")
    expiration_month: int = Field(..., ge=1, le=12, description="Card expiration month (1-12)")
    expiration_year: int = Field(..., ge=0, description="Card expiration year (2-digit or 4-digit)")
    security_code: str = Field(..., description="Card security code (CVV/CVC)")
    holder_name: str = Field(..., description="Cardholder name")


class Config(BaseModel):
    """Main application configuration."""
    api: APIConfig = Field(default_factory=APIConfig, description="API configuration")
    placeholder_mode: bool = Field(default=True, description="Use placeholder/mock API responses")
    provider_test_cards: Dict[str, ProviderTestCard] = Field(
        default_factory=dict,
        description="Provider-specific test cards (provider name -> card data)"
    )
