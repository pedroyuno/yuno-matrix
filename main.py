#!/usr/bin/env python3
"""MATRIX - Merchant API Test & Regression Integration eXerciser
Main entry point for running test suites.
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from src.parser import TestCaseParser, TestCaseParseError
from src.executor import TestExecutor
from src.api_client import APIClient
from src.logger import CertificationLogger
from src.context import ExecutionContext
from src.models import Config
from colorama import Fore

def load_config(config_path: str) -> Config:
    """Load configuration from file."""
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return Config(**config_data)
    except FileNotFoundError:
        print(f"{Fore.RED}Error: Config file not found: {config_path}")
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}Error loading config: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="MATRIX - Merchant API Test & Regression Integration eXerciser"
    )
    parser.add_argument("--testcase", required=True, help="Path to test case JSON file")
    parser.add_argument("--config", default="config/config.json", help="Path to config file")
    parser.add_argument("--log-dir", default="logs", help="Directory for log files")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Parse test case file
    try:
        test_suite = TestCaseParser.load_from_file(args.testcase)
        print(f"{Fore.GREEN}✓ Loaded test suite: {test_suite.metadata.test_suite_name}")
        print(f"{Fore.WHITE}  Test cases: {len(test_suite.test_cases)}")
        print(f"{Fore.WHITE}  Environment: {test_suite.metadata.environment}\n")
    except TestCaseParseError as e:
        print(f"{Fore.RED}Error parsing test case file:\n{e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"{Fore.RED}Error: Test case file not found: {args.testcase}")
        sys.exit(1)
    
    # Generate execution ID
    execution_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Initialize components
    api_client = APIClient(config)
    logger = CertificationLogger(execution_id, args.log_dir)
    context = ExecutionContext()
    executor = TestExecutor(api_client, logger, context)
    
    # Execute test suite
    try:
        report = executor.execute_test_suite(test_suite)
        logger.close()
        
        # Exit with appropriate code
        exit_code = 0 if report.failed_test_cases == 0 and report.error_test_cases == 0 else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Execution interrupted by user")
        logger.close()
        sys.exit(130)
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error during execution: {e}")
        import traceback
        traceback.print_exc()
        logger.close()
        sys.exit(1)

if __name__ == "__main__":
    main()
