"""
Certification logger for MATRIX.

Logs all requests and responses for certification proof.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from colorama import Fore, Style, init as colorama_init

from src.models import TestCase, Step, TestCaseResult, ExecutionReport, APIRequest, APIResponse

# Initialize colorama for cross-platform color support
colorama_init(autoreset=True)


class CertificationLogger:
    """
    Logger for MATRIX test execution.

    Logs all requests/responses to JSON file for certification proof.
    Provides colored console output for user feedback.
    """

    def __init__(self, execution_id: str, log_dir: str = "logs"):
        """
        Initialize certification logger.

        Args:
            execution_id: Unique execution identifier
            log_dir: Directory for log files
        """
        self.execution_id = execution_id
        self.log_dir = Path(log_dir)
        self.log_entries: List[Dict[str, Any]] = []

        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Generate log file name
        self.log_file = self.log_dir / f"execution_{execution_id}.json"

        self._log_start()

    def _log_start(self) -> None:
        """Log execution start."""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}MATRIX Test Execution")
        print(f"{Fore.CYAN}Execution ID: {self.execution_id}")
        print(f"{Fore.CYAN}Log file: {self.log_file}")
        print(f"{Fore.CYAN}{'='*70}\n")

    def log_test_case_start(self, test_case: TestCase) -> None:
        """
        Log start of test case execution.

        Args:
            test_case: Test case being executed
        """
        print(f"\n{Fore.YELLOW}► Test Case: {test_case.name} ({test_case.id})")
        print(f"{Fore.WHITE}  {test_case.description}")
        print(f"{Fore.WHITE}  Steps: {len(test_case.steps)}")

    def log_test_case_end(self, test_case_id: str, result: TestCaseResult) -> None:
        """
        Log end of test case execution.

        Args:
            test_case_id: Test case identifier
            result: Test case result
        """
        status_color = {
            "pass": Fore.GREEN,
            "fail": Fore.RED,
            "error": Fore.MAGENTA
        }.get(result.status, Fore.WHITE)

        duration_str = f"{result.duration_ms}ms" if result.duration_ms else "N/A"
        print(f"{status_color}✓ Test Case {result.status.upper()}: {result.test_case_name} ({duration_str})\n")

        if result.error_message:
            print(f"{Fore.RED}  Error: {result.error_message}\n")

    def log_step(
        self,
        test_case_id: str,
        test_case_name: str,
        step: Step,
        request: Optional[APIRequest],
        response: Optional[APIResponse],
        status: str,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        captured_variables: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a single step execution.

        Args:
            test_case_id: Test case identifier
            test_case_name: Test case name
            step: Step being executed
            request: API request details
            response: API response details
            status: Step status (success, failure, error)
            duration_ms: Execution duration in milliseconds
            error_message: Error message if step failed
            captured_variables: Variables captured from response
        """
        # Create log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "execution_id": self.execution_id,
            "test_case_id": test_case_id,
            "test_case_name": test_case_name,
            "step_id": step.step_id,
            "operation": step.operation,
            "provider": step.provider,
            "description": step.description,
            "status": status,
            "duration_ms": duration_ms
        }

        # Add request details (with masking)
        if request:
            log_entry["request"] = {
                "method": request.method,
                "url": request.url,
                "headers": self._mask_sensitive_data(request.headers),
                "body": self._mask_sensitive_data(request.body)
            }

        # Add response details (with masking)
        if response:
            log_entry["response"] = {
                "status_code": response.status_code,
                "headers": self._mask_sensitive_data(response.headers),
                "body": self._mask_sensitive_data(response.body),
                "error": response.error
            }

        # Add captured variables
        if captured_variables:
            log_entry["captured_variables"] = captured_variables

        # Add error message
        if error_message:
            log_entry["error_message"] = error_message

        self.log_entries.append(log_entry)

        # Console output
        status_symbol = {
            "success": f"{Fore.GREEN}✓",
            "failure": f"{Fore.RED}✗",
            "error": f"{Fore.MAGENTA}⚠"
        }.get(status, "•")

        duration_str = f" ({duration_ms}ms)" if duration_ms else ""
        print(f"  {status_symbol} Step {step.step_id}: {step.description} - {step.operation}{duration_str}")

        if captured_variables:
            vars_str = ", ".join(f"{k}={v}" for k, v in captured_variables.items())
            print(f"    {Fore.CYAN}Captured: {vars_str}")

        if error_message:
            print(f"    {Fore.RED}Error: {error_message}")

    def log_execution_summary(self, report: ExecutionReport) -> None:
        """
        Log execution summary.

        Args:
            report: Execution report
        """
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}Execution Summary")
        print(f"{Fore.CYAN}{'='*70}")
        print(f"{Fore.WHITE}Test Suite: {report.test_suite_name}")
        print(f"{Fore.WHITE}Execution ID: {report.execution_id}")
        print(f"{Fore.WHITE}Duration: {report.duration_ms}ms" if report.duration_ms else "")
        print(f"\n{Fore.WHITE}Test Cases:")
        print(f"  {Fore.GREEN}Passed: {report.passed_test_cases}")
        print(f"  {Fore.RED}Failed: {report.failed_test_cases}")
        print(f"  {Fore.MAGENTA}Errors: {report.error_test_cases}")
        print(f"  {Fore.WHITE}Total: {report.total_test_cases}")
        print(f"\n{Fore.WHITE}Success Rate: {report.success_rate:.1f}%")
        print(f"{Fore.CYAN}{'='*70}\n")

    def close(self) -> None:
        """
        Finalize and write log file.

        Writes all log entries to JSON file.
        """
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.log_entries, f, indent=2, ensure_ascii=False)

            print(f"{Fore.GREEN}✓ Log file written: {self.log_file}\n")

            # Create symlink to latest log
            latest_link = self.log_dir / "latest.json"
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            try:
                latest_link.symlink_to(self.log_file.name)
            except (OSError, NotImplementedError):
                # Symlinks may not be supported on all platforms
                pass

        except IOError as e:
            print(f"{Fore.RED}Error writing log file: {e}\n")

    def _mask_sensitive_data(self, data: Any) -> Any:
        """
        Mask sensitive data in requests/responses.

        Masks:
        - Card numbers (PAN)
        - CVV codes
        - API keys / tokens in headers
        - Passwords

        Args:
            data: Data to mask (dict, list, or string)

        Returns:
            Data with sensitive values masked
        """
        if isinstance(data, dict):
            return {key: self._mask_sensitive_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        elif isinstance(data, str):
            return self._mask_string(data)
        else:
            return data

    def _mask_string(self, text: str) -> str:
        """
        Mask sensitive patterns in strings.

        Args:
            text: String to mask

        Returns:
            Masked string
        """
        # Mask card numbers (13-19 digits)
        text = re.sub(r'\b(\d{4})[\d\s]{5,11}(\d{4})\b', r'\1****\2', text)

        # Mask CVV (3-4 digits standalone)
        text = re.sub(r'\b\d{3,4}\b', '***', text)

        # Mask common sensitive field patterns
        sensitive_patterns = [
            (r'(Bearer\s+)[\w\-\.]+', r'\1***'),
            (r'(api[_-]?key["\s:=]+)[\w\-]+', r'\1***'),
            (r'(password["\s:=]+)[\w\-]+', r'\1***'),
            (r'(token["\s:=]+)[\w\-\.]+', r'\1***'),
        ]

        for pattern, replacement in sensitive_patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    def get_log_entries(self) -> List[Dict[str, Any]]:
        """
        Get all log entries.

        Returns:
            List of log entries
        """
        return self.log_entries.copy()

    def get_log_file_path(self) -> Path:
        """
        Get path to log file.

        Returns:
            Path to log file
        """
        return self.log_file
