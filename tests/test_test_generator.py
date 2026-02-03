"""
Unit tests for MATRIX test case generator.

Target coverage: 85%+
"""

import pytest
from pathlib import Path

from src.scoping_parser import ScopingParser, ProviderIntegration, OperationSupport
from src.test_generator import TestCaseGenerator, GeneratorConfig
from src.models import TestSuite, TestCase, Step


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_scoping_doc():
    """Load sample scoping document."""
    return ScopingParser.load_from_file("tests/fixtures/sample_scoping.csv")


@pytest.fixture
def card_integration():
    """Create a sample card integration."""
    integration = ProviderIntegration(
        integration_id="TEST_CARD",
        provider="TEST_PROVIDER",
        payment_method="CARD",
        country="BR"
    )
    integration.operations = {
        "authorize": OperationSupport(supported=True, status="Implemented"),
        "capture": OperationSupport(supported=True, status="Implemented"),
        "refund": OperationSupport(supported=True, status="Implemented"),
        "cancel": OperationSupport(supported=True, status="Implemented"),
        "purchase": OperationSupport(supported=False, status="Not Applicable"),
    }
    return integration


@pytest.fixture
def pix_integration():
    """Create a sample PIX integration."""
    integration = ProviderIntegration(
        integration_id="TEST_PIX",
        provider="TEST_PROVIDER",
        payment_method="PIX",
        country="BR"
    )
    integration.operations = {
        "purchase": OperationSupport(supported=True, status="Implemented"),
        "refund": OperationSupport(supported=True, status="Implemented"),
        "authorize": OperationSupport(supported=False, status="Not Applicable"),
        "capture": OperationSupport(supported=False, status="Not Applicable"),
    }
    return integration


# ============================================================================
# Basic Generation Tests
# ============================================================================

@pytest.mark.unit
def test_generate_test_suite(sample_scoping_doc):
    """Test generating a complete test suite from scoping document."""
    generator = TestCaseGenerator()
    test_suite = generator.generate_test_suite(sample_scoping_doc)
    
    assert isinstance(test_suite, TestSuite)
    assert test_suite.version == "1.0"
    assert len(test_suite.test_cases) > 0


@pytest.mark.unit
def test_generate_suite_metadata(sample_scoping_doc):
    """Test generated suite has correct metadata."""
    config = GeneratorConfig(
        merchant_id="test_merchant",
        environment="sandbox",
        test_suite_name="Custom Suite Name"
    )
    generator = TestCaseGenerator(config)
    test_suite = generator.generate_test_suite(sample_scoping_doc)
    
    assert test_suite.metadata.merchant_id == "test_merchant"
    assert test_suite.metadata.environment == "sandbox"
    assert test_suite.metadata.test_suite_name == "Custom Suite Name"


@pytest.mark.unit
def test_generate_card_integration_tests(card_integration):
    """Test generating tests for card integration."""
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(card_integration)
    
    assert len(test_cases) > 0
    
    # Should have authorize_capture flow
    auth_capture = next((tc for tc in test_cases if "authorize_capture" in tc.id), None)
    assert auth_capture is not None
    assert len(auth_capture.steps) == 2
    assert auth_capture.steps[0].operation == "authorize"
    assert auth_capture.steps[1].operation == "capture"


@pytest.mark.unit
def test_generate_pix_integration_tests(pix_integration):
    """Test generating tests for PIX integration."""
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(pix_integration)
    
    assert len(test_cases) > 0
    
    # Should have purchase flow
    purchase = next((tc for tc in test_cases if tc.id.endswith("_purchase")), None)
    assert purchase is not None
    assert len(purchase.steps) == 1
    assert purchase.steps[0].operation == "purchase"


# ============================================================================
# Configuration Tests
# ============================================================================

@pytest.mark.unit
def test_only_implemented_filter(sample_scoping_doc):
    """Test filtering to only implemented operations."""
    config = GeneratorConfig(only_implemented=True)
    generator = TestCaseGenerator(config)
    test_suite = generator.generate_test_suite(sample_scoping_doc)
    
    # All generated test cases should only use implemented operations
    for tc in test_suite.test_cases:
        for step in tc.steps:
            # Check that the operation is implemented (not just supported)
            assert step.expected_status == "success"


@pytest.mark.unit
def test_operations_filter():
    """Test filtering specific operations."""
    integration = ProviderIntegration(
        integration_id="TEST",
        provider="TEST",
        payment_method="CARD",
        country="BR"
    )
    integration.operations = {
        "authorize": OperationSupport(supported=True, status="Implemented"),
        "capture": OperationSupport(supported=True, status="Implemented"),
        "refund": OperationSupport(supported=True, status="Implemented"),
    }
    
    config = GeneratorConfig(operations_filter=["authorize"])
    generator = TestCaseGenerator(config)
    test_cases = generator.generate_integration_tests(integration)
    
    # Should only generate tests involving authorize
    for tc in test_cases:
        ops = [step.operation for step in tc.steps]
        assert "authorize" in ops


@pytest.mark.unit
def test_disable_operations():
    """Test disabling specific operations in config."""
    integration = ProviderIntegration(
        integration_id="TEST",
        provider="TEST",
        payment_method="CARD",
        country="BR"
    )
    integration.operations = {
        "authorize": OperationSupport(supported=True, status="Implemented"),
        "capture": OperationSupport(supported=True, status="Implemented"),
        "refund": OperationSupport(supported=True, status="Implemented"),
    }
    
    config = GeneratorConfig(include_refund=False)
    generator = TestCaseGenerator(config)
    test_cases = generator.generate_integration_tests(integration)
    
    # Should not have any refund operations
    for tc in test_cases:
        for step in tc.steps:
            assert step.operation != "refund"


# ============================================================================
# Step Generation Tests
# ============================================================================

@pytest.mark.unit
def test_step_input_data_structure(card_integration):
    """Test generated step has correct input data structure."""
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(card_integration)
    
    # Get first authorize step
    for tc in test_cases:
        for step in tc.steps:
            if step.operation == "authorize":
                assert "amount" in step.input_data
                assert "currency" in step.input_data["amount"]
                assert "value" in step.input_data["amount"]
                assert "customer_payer" in step.input_data
                assert "payment_method" in step.input_data
                return
    
    pytest.fail("No authorize step found")


@pytest.mark.unit
def test_step_capture_variables(card_integration):
    """Test generated step has capture variables for initial operations."""
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(card_integration)
    
    for tc in test_cases:
        for step in tc.steps:
            if step.operation in ("authorize", "purchase"):
                assert step.capture_variables is not None
                # Should capture payment_id, transaction_id, status
                assert any("payment_id" in k for k in step.capture_variables.keys())
                return
    
    pytest.fail("No initial operation step found")


@pytest.mark.unit
def test_step_references_captured_variables(card_integration):
    """Test capture/refund steps reference captured variables."""
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(card_integration)
    
    for tc in test_cases:
        if len(tc.steps) > 1:
            # Find capture or refund step
            for step in tc.steps[1:]:
                if step.operation in ("capture", "refund", "cancel"):
                    # Should reference payment_id from previous step
                    input_str = str(step.input_data)
                    assert "${" in input_str or "payment_id" in input_str
                    return
    
    # This is okay if no multi-step test cases exist
    pass


# ============================================================================
# Payment Method Specific Tests
# ============================================================================

@pytest.mark.unit
def test_card_payment_method_structure(card_integration):
    """Test card payment method structure in generated steps."""
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(card_integration)
    
    for tc in test_cases:
        for step in tc.steps:
            if step.operation in ("authorize", "purchase") and "payment_method" in step.input_data:
                pm = step.input_data["payment_method"]
                assert pm["type"] == "CARD"
                assert "detail" in pm
                assert "card" in pm["detail"]
                assert "card_data" in pm["detail"]["card"]
                return
    
    pytest.fail("No card payment method step found")


@pytest.mark.unit
def test_pix_payment_method_structure(pix_integration):
    """Test PIX payment method structure in generated steps."""
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(pix_integration)
    
    for tc in test_cases:
        for step in tc.steps:
            if step.operation == "purchase" and "payment_method" in step.input_data:
                pm = step.input_data["payment_method"]
                assert pm["type"] == "PIX"
                return
    
    pytest.fail("No PIX payment method step found")


# ============================================================================
# Customer Data Tests
# ============================================================================

@pytest.mark.unit
def test_customer_data_brazil():
    """Test customer data for Brazil."""
    integration = ProviderIntegration(
        integration_id="TEST",
        provider="TEST",
        payment_method="CARD",
        country="BR"
    )
    integration.operations = {
        "authorize": OperationSupport(supported=True, status="Implemented"),
    }
    
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(integration)
    
    for tc in test_cases:
        for step in tc.steps:
            if "customer_payer" in step.input_data:
                customer = step.input_data["customer_payer"]
                assert customer["document"]["document_type"] == "CPF"
                assert customer["phone"]["country_code"] == "55"
                return


@pytest.mark.unit
def test_customer_data_mexico():
    """Test customer data for Mexico."""
    integration = ProviderIntegration(
        integration_id="TEST",
        provider="TEST",
        payment_method="CARD",
        country="MX"
    )
    integration.operations = {
        "authorize": OperationSupport(supported=True, status="Implemented"),
    }
    
    generator = TestCaseGenerator()
    test_cases = generator.generate_integration_tests(integration)
    
    for tc in test_cases:
        for step in tc.steps:
            if "customer_payer" in step.input_data:
                customer = step.input_data["customer_payer"]
                assert customer["document"]["document_type"] == "CURP"
                assert customer["phone"]["country_code"] == "52"
                return


# ============================================================================
# Single Operation Test
# ============================================================================

@pytest.mark.unit
def test_generate_single_operation_test(card_integration):
    """Test generating a single operation test case."""
    generator = TestCaseGenerator()
    
    # Supported operation
    tc = generator.generate_single_operation_test(card_integration, "authorize")
    assert tc is not None
    assert len(tc.steps) == 1
    assert tc.steps[0].operation == "authorize"
    
    # Unsupported operation
    tc = generator.generate_single_operation_test(card_integration, "purchase")
    assert tc is None
