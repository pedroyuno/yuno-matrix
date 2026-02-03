#!/usr/bin/env python3
"""MATRIX - Merchant API Test & Regression Integration eXerciser
Main entry point for running test suites from scoping documents.
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from src.scoping_parser import ScopingParser, ScopingParseError
from src.test_generator import TestCaseGenerator, GeneratorConfig
from src.executor import TestExecutor
from src.api_client import APIClient
from src.logger import CertificationLogger
from src.context import ExecutionContext
from src.models import Config, TestSuite
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


def load_scoping_document(file_path: str, generator_config: GeneratorConfig) -> 'TestSuite':
    """
    Load scoping document and generate test suite.
    
    Args:
        file_path: Path to scoping document CSV file
        generator_config: Configuration for test case generation
        
    Returns:
        TestSuite object with generated test cases
    """
    from src.test_generator import HierarchicalTestSuite
    
    path = Path(file_path)
    
    if not path.suffix.lower() == '.csv':
        raise ScopingParseError(f"Invalid file format: {path.suffix}. Expected .csv scoping document.")
    
    print(f"{Fore.CYAN}Loading scoping document: {file_path}")
    scoping_doc = ScopingParser.load_from_file(file_path)
    
    print(f"\n{Fore.CYAN}Generating test cases...")
    generator = TestCaseGenerator(generator_config)
    hierarchical_suite = generator.generate_hierarchical_test_suite(scoping_doc)
    
    # Display hierarchical structure
    print(f"\n{Fore.WHITE}Test Structure:")
    pm_num = 0
    for pm_group in hierarchical_suite.payment_methods:
        pm_num += 1
        total_pm_tests = len(pm_group.get_all_test_cases())
        print(f"{Fore.CYAN}  {pm_num}. {pm_group.payment_method} ({total_pm_tests} tests)")
        
        provider_num = 0
        for provider_group in pm_group.providers:
            provider_num += 1
            print(f"{Fore.WHITE}    {pm_num}.{provider_num} {provider_group.provider} ({len(provider_group.test_cases)} tests)")
            
            test_num = 0
            for tc in provider_group.test_cases:
                test_num += 1
                print(f"{Fore.WHITE}      {pm_num}.{provider_num}.{test_num} {tc.name}")
    
    return hierarchical_suite.to_flat_test_suite()


def main():
    parser = argparse.ArgumentParser(
        description="MATRIX - Merchant API Test & Regression Integration eXerciser"
    )
    parser.add_argument(
        "--scoping",
        required=True, 
        help="Path to scoping document CSV file"
    )
    parser.add_argument("--config", default="config/config.json", help="Path to config file")
    parser.add_argument("--log-dir", default="logs", help="Directory for log files")
    parser.add_argument("--merchant-id", default="matrix_test", help="Merchant ID for generated tests")
    parser.add_argument("--environment", default="sandbox", help="Environment (sandbox, production)")
    parser.add_argument("--suite-name", default=None, help="Custom test suite name")
    parser.add_argument("--only-implemented", action="store_true", help="Only test implemented operations")
    parser.add_argument(
        "--operations", 
        nargs="+", 
        default=None,
        help="Specific operations to test (e.g., --operations authorize capture refund)"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Configure test generator
    generator_config = GeneratorConfig(
        merchant_id=args.merchant_id,
        environment=args.environment,
        test_suite_name=args.suite_name,
        only_implemented=args.only_implemented,
        operations_filter=args.operations
    )
    
    # Load scoping document and generate test suite
    try:
        test_suite = load_scoping_document(args.scoping, generator_config)
        print(f"{Fore.GREEN}✓ Generated test suite: {test_suite.metadata.test_suite_name}")
        print(f"{Fore.WHITE}  Test cases: {len(test_suite.test_cases)}")
        print(f"{Fore.WHITE}  Environment: {test_suite.metadata.environment}\n")
    except ScopingParseError as e:
        print(f"{Fore.RED}Error parsing scoping document:\n{e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"{Fore.RED}Error: Scoping document not found: {args.scoping}")
        sys.exit(1)
    
    if len(test_suite.test_cases) == 0:
        print(f"{Fore.YELLOW}Warning: No test cases were generated. Check your scoping document.")
        sys.exit(0)
    
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
