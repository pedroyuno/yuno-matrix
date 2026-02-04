"""Test executor for MATRIX. Orchestrates test case execution."""
import time
from datetime import datetime
from typing import List
from src.models import (TestSuite, TestCase, Step, ExecutionReport, 
                        TestCaseResult, StepResult, APIRequest, APIResponse)
from src.api_client import APIClient
from src.logger import CertificationLogger
from src.context import ExecutionContext, ContextError

class TestExecutor:
    """Executes test suites and manages the execution flow."""
    
    def __init__(self, api_client: APIClient, logger: CertificationLogger, context: ExecutionContext):
        self.api_client = api_client
        self.logger = logger
        self.context = context
    
    def execute_test_suite(self, test_suite: TestSuite) -> ExecutionReport:
        """Execute complete test suite."""
        start_time = datetime.utcnow()
        start_ms = time.time() * 1000
        
        results: List[TestCaseResult] = []
        for test_case in test_suite.test_cases:
            self.context.clear()  # Isolate variables between test cases
            result = self.execute_test_case(test_case)
            results.append(result)
        
        end_time = datetime.utcnow()
        duration_ms = int((time.time() * 1000) - start_ms)
        
        # Calculate stats
        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        errors = sum(1 for r in results if r.status == "error")
        total_steps = sum(len(r.steps) for r in results)
        
        report = ExecutionReport(
            execution_id=self.logger.execution_id,
            start_time=start_time.isoformat() + "Z",
            end_time=end_time.isoformat() + "Z",
            test_suite_name=test_suite.metadata.test_suite_name,
            total_test_cases=len(test_suite.test_cases),
            passed_test_cases=passed,
            failed_test_cases=failed,
            error_test_cases=errors,
            total_steps=total_steps,
            test_case_results=results,
            duration_ms=duration_ms
        )
        
        self.logger.log_execution_summary(report)
        return report
    
    def execute_test_case(self, test_case: TestCase) -> TestCaseResult:
        """Execute single test case."""
        self.logger.log_test_case_start(test_case)
        start_ms = time.time() * 1000
        
        step_results: List[StepResult] = []
        overall_status = "pass"
        error_msg = None
        
        for step in test_case.steps:
            try:
                result = self.execute_step(test_case, step)
                step_results.append(result)
                if result.status in ("failure", "error"):
                    overall_status = "fail" if result.status == "failure" else "error"
                    error_msg = result.error_message
                    break  # Stop on first failure
            except Exception as e:
                overall_status = "error"
                error_msg = str(e)
                step_results.append(StepResult(
                    step_id=step.step_id, operation=step.operation,
                    provider=step.provider, status="error", error_message=str(e)
                ))
                break
        
        duration_ms = int((time.time() * 1000) - start_ms)
        result = TestCaseResult(
            test_case_id=test_case.id, test_case_name=test_case.name,
            status=overall_status, steps=step_results, 
            duration_ms=duration_ms, error_message=error_msg
        )
        
        self.logger.log_test_case_end(test_case.id, result)
        return result
    
    def execute_step(self, test_case: TestCase, step: Step) -> StepResult:
        """Execute single step."""
        start_ms = time.time() * 1000
        response = None
        request = None
        
        try:
            # Substitute variables in input data
            substituted_data = self.context.substitute_variables(step.input_data)
            
            # Create API request
            base_url = self.api_client.config.api.base_urls.get(step.provider, "https://api.example.com")
            request = APIRequest(
                method="POST", url=f"{base_url}/{step.operation}",
                headers={"Content-Type": "application/json"}, body=substituted_data
            )
            
            # Execute API call
            response = self.api_client.execute_operation(step.operation, step.provider, substituted_data)
            
            # Capture variables from response
            captured_vars = {}
            if step.capture_variables and response.body:
                captured_vars = self.context.capture_variables_from_response(
                    {"body": response.body}, step.capture_variables
                )
            
            duration_ms = int((time.time() * 1000) - start_ms)
            status = "success" if response.is_success else "failure"
            
            result = StepResult(
                step_id=step.step_id, operation=step.operation, provider=step.provider,
                status=status, request=request, response=response, duration_ms=duration_ms,
                captured_variables=captured_vars if captured_vars else None
            )
            
            self.logger.log_step(test_case.id, test_case.name, step, request, response,
                               status, duration_ms, captured_variables=captured_vars)
            return result
            
        except ContextError as e:
            duration_ms = int((time.time() * 1000) - start_ms)
            error_msg = f"Context error: {str(e)}"
            # Include response if available so user can see what the API returned
            result = StepResult(
                step_id=step.step_id, operation=step.operation, provider=step.provider,
                status="error", duration_ms=duration_ms, error_message=error_msg,
                request=request, response=response
            )
            self.logger.log_step(test_case.id, test_case.name, step, request, response,
                               "error", duration_ms, error_message=error_msg)
            return result
        except Exception as e:
            duration_ms = int((time.time() * 1000) - start_ms)
            error_msg = f"Execution error: {str(e)}"
            # Include response if available so user can see what the API returned
            result = StepResult(
                step_id=step.step_id, operation=step.operation, provider=step.provider,
                status="error", duration_ms=duration_ms, error_message=error_msg,
                request=request, response=response
            )
            self.logger.log_step(test_case.id, test_case.name, step, request, response,
                               "error", duration_ms, error_message=error_msg)
            return result
