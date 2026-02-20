"""
Test case generator for MATRIX.

Generates test suites from scoping documents using payment presets.
Organizes tests hierarchically: Payment Method → Provider → Test Cases.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import uuid

from src.scoping_parser import ScopingDocument, ProviderIntegration
from src.models import TestSuite, TestCase, Step, Metadata
from src.schemas.presets import get_presets


@dataclass
class GeneratorConfig:
    """Configuration for test case generation."""
    merchant_id: str = "matrix_test"
    environment: str = "sandbox"
    test_suite_name: Optional[str] = None
    
    # Default test amounts per currency
    test_amounts: Dict[str, float] = field(default_factory=lambda: {
        "BRL": 100.00,
        "MXN": 500.00,
        "COP": 100000.00,
        "ARS": 1000.00,
        "CLP": 50000.00,
        "PEN": 100.00,
        "USD": 50.00
    })
    
    # Country to currency mapping
    country_currency: Dict[str, str] = field(default_factory=lambda: {
        "BR": "BRL",
        "MX": "MXN", 
        "CO": "COP",
        "AR": "ARS",
        "CL": "CLP",
        "PE": "PEN",
        "US": "USD"
    })
    
    # Filter: only generate tests for specific operations (None = all)
    operations_filter: Optional[List[str]] = None
    
    # Filter: only generate tests for implemented operations
    only_implemented: bool = False
    
    # Include operations
    include_authorize: bool = True
    include_capture: bool = True
    include_purchase: bool = True
    include_refund: bool = True
    include_cancel: bool = True
    include_verify: bool = True
    include_partial_refund: bool = True


@dataclass
class ProviderTestGroup:
    """Group of test cases for a specific provider."""
    provider: str
    provider_id: str  # e.g., "rede", "safrapay"
    integration_id: str  # e.g., "REDE_CARD"
    test_cases: List[TestCase] = field(default_factory=list)


@dataclass
class PaymentMethodTestGroup:
    """Group of providers for a specific payment method."""
    payment_method: str  # e.g., "CARD", "PIX", "BOLETO"
    payment_method_id: str  # e.g., "card", "pix", "boleto"
    providers: List[ProviderTestGroup] = field(default_factory=list)
    
    def get_all_test_cases(self) -> List[TestCase]:
        """Get all test cases across all providers."""
        test_cases = []
        for provider in self.providers:
            test_cases.extend(provider.test_cases)
        return test_cases


@dataclass 
class HierarchicalTestSuite:
    """Test suite organized by Payment Method → Provider → Test Cases."""
    version: str
    metadata: Metadata
    payment_methods: List[PaymentMethodTestGroup] = field(default_factory=list)
    
    def get_all_test_cases(self) -> List[TestCase]:
        """Get all test cases flattened."""
        test_cases = []
        for pm in self.payment_methods:
            test_cases.extend(pm.get_all_test_cases())
        return test_cases
    
    def to_flat_test_suite(self) -> TestSuite:
        """Convert to flat TestSuite for execution."""
        return TestSuite(
            version=self.version,
            metadata=self.metadata,
            test_cases=self.get_all_test_cases()
        )
    
    def get_test_cases_by_payment_method(self, payment_method_id: str) -> List[TestCase]:
        """Get all test cases for a payment method."""
        for pm in self.payment_methods:
            if pm.payment_method_id == payment_method_id:
                return pm.get_all_test_cases()
        return []
    
    def get_test_cases_by_provider(self, payment_method_id: str, provider_id: str) -> List[TestCase]:
        """Get all test cases for a specific provider."""
        for pm in self.payment_methods:
            if pm.payment_method_id == payment_method_id:
                for provider in pm.providers:
                    if provider.provider_id == provider_id:
                        return provider.test_cases
        return []


class TestCaseGenerator:
    """Generates test cases from scoping documents."""
    
    # Operation flow definitions (what operations typically follow each other)
    OPERATION_FLOWS = {
        'authorize_capture': ['authorize', 'capture'],
        'authorize_cancel': ['authorize', 'cancel'],
        'purchase': ['purchase'],
        'purchase_refund': ['purchase', 'refund'],
        'authorize_capture_refund': ['authorize', 'capture', 'refund'],
        'purchase_partial_refund': ['purchase', 'partial_refund'],
        'authorize_capture_partial_refund': ['authorize', 'capture', 'partial_refund'],
    }
    
    def __init__(self, config: Optional[GeneratorConfig] = None):
        self.config = config or GeneratorConfig()
        self._presets = {p['id']: p for p in get_presets()}
    
    def generate_test_suite(self, scoping_doc: ScopingDocument) -> TestSuite:
        """
        Generate a flat test suite from a scoping document.
        
        Args:
            scoping_doc: Parsed scoping document
            
        Returns:
            TestSuite with generated test cases (flat structure)
        """
        hierarchical = self.generate_hierarchical_test_suite(scoping_doc)
        return hierarchical.to_flat_test_suite()
    
    def generate_hierarchical_test_suite(self, scoping_doc: ScopingDocument) -> HierarchicalTestSuite:
        """
        Generate a hierarchical test suite organized by Payment Method → Provider → Test Cases.
        
        Args:
            scoping_doc: Parsed scoping document
            
        Returns:
            HierarchicalTestSuite with organized test cases
        """
        # Group integrations by payment method
        payment_method_map: Dict[str, List[ProviderIntegration]] = {}
        
        for integration in scoping_doc.integrations:
            pm = integration.payment_method.upper()
            if pm not in payment_method_map:
                payment_method_map[pm] = []
            payment_method_map[pm].append(integration)
        
        # Build hierarchical structure
        payment_methods: List[PaymentMethodTestGroup] = []
        
        # Sort payment methods for consistent ordering
        for pm_name in sorted(payment_method_map.keys()):
            integrations = payment_method_map[pm_name]
            
            providers: List[ProviderTestGroup] = []
            
            # Sort providers within payment method
            for integration in sorted(integrations, key=lambda x: x.provider):
                test_cases = self.generate_integration_tests(integration)
                
                if test_cases:  # Only add if there are test cases
                    provider_group = ProviderTestGroup(
                        provider=integration.provider,
                        provider_id=integration.provider.lower().replace(' ', '_'),
                        integration_id=integration.integration_id,
                        test_cases=test_cases
                    )
                    providers.append(provider_group)
            
            if providers:  # Only add payment method if it has providers with tests
                pm_group = PaymentMethodTestGroup(
                    payment_method=pm_name,
                    payment_method_id=pm_name.lower(),
                    providers=providers
                )
                payment_methods.append(pm_group)
        
        # Generate metadata
        suite_name = self.config.test_suite_name or f"Generated Test Suite - {datetime.utcnow().strftime('%Y-%m-%d')}"
        
        metadata = Metadata(
            test_suite_name=suite_name,
            merchant_id=self.config.merchant_id,
            environment=self.config.environment,
            created_at=datetime.utcnow().isoformat() + "Z"
        )
        
        return HierarchicalTestSuite(
            version="1.0",
            metadata=metadata,
            payment_methods=payment_methods
        )
    
    def generate_integration_tests(self, integration: ProviderIntegration) -> List[TestCase]:
        """
        Generate test cases for a single integration.
        
        Args:
            integration: Provider integration definition
            
        Returns:
            List of test cases for this integration
        """
        test_cases = []
        supported_ops = integration.get_supported_operations()
        
        # Filter operations based on config
        if self.config.operations_filter:
            supported_ops = [op for op in supported_ops if op in self.config.operations_filter]
        
        if self.config.only_implemented:
            supported_ops = [op for op in supported_ops if integration.is_implemented(op)]
        
        # Generate test flows based on supported operations
        flows_to_test = self._determine_test_flows(supported_ops, integration)
        
        for flow_name, operations in flows_to_test.items():
            test_case = self._create_test_case(integration, flow_name, operations)
            if test_case:
                test_cases.append(test_case)
        
        return test_cases
    
    def _determine_test_flows(self, supported_ops: List[str], integration: ProviderIntegration) -> Dict[str, List[str]]:
        """Determine which test flows to generate based on supported operations."""
        flows = {}
        
        # Card-specific flows
        if integration.payment_method.upper() == 'CARD':
            # Authorize + Capture flow
            if 'authorize' in supported_ops and 'capture' in supported_ops:
                if self.config.include_authorize and self.config.include_capture:
                    flows['authorize_capture'] = ['authorize', 'capture']
            
            # Authorize + Cancel flow
            if 'authorize' in supported_ops and 'cancel' in supported_ops:
                if self.config.include_authorize and self.config.include_cancel:
                    flows['authorize_cancel'] = ['authorize', 'cancel']
            
            # Authorize only (if no capture support)
            if 'authorize' in supported_ops and 'capture' not in supported_ops:
                if self.config.include_authorize:
                    flows['authorize'] = ['authorize']
            
            # Full authorize-capture-refund flow
            if 'authorize' in supported_ops and 'capture' in supported_ops and 'refund' in supported_ops:
                if self.config.include_authorize and self.config.include_capture and self.config.include_refund:
                    flows['authorize_capture_refund'] = ['authorize', 'capture', 'refund']
        
        # Purchase flow (for PIX, BOLETO, or CARD with direct purchase)
        if 'purchase' in supported_ops:
            if self.config.include_purchase:
                flows['purchase'] = ['purchase']
            
            # Purchase + Refund flow
            if 'refund' in supported_ops and self.config.include_refund:
                flows['purchase_refund'] = ['purchase', 'refund']
        
        # Partial refund flows
        if 'partial_refund' in supported_ops and self.config.include_partial_refund:
            if integration.payment_method.upper() == 'CARD':
                if 'authorize' in supported_ops and 'capture' in supported_ops:
                    if self.config.include_authorize and self.config.include_capture:
                        flows['authorize_capture_partial_refund'] = ['authorize', 'capture', 'partial_refund']
            
            if 'purchase' in supported_ops and self.config.include_purchase:
                flows['purchase_partial_refund'] = ['purchase', 'partial_refund']
        
        # Verify flow (for card verification)
        if 'verify' in supported_ops and self.config.include_verify:
            flows['verify'] = ['verify']
        
        return flows
    
    def _create_test_case(self, integration: ProviderIntegration, flow_name: str, operations: List[str]) -> Optional[TestCase]:
        """Create a test case for a specific flow."""
        provider = integration.provider.lower()
        payment_method = integration.payment_method.lower()
        
        test_case_id = f"tc_{integration.integration_id.lower()}_{flow_name}"
        test_case_name = f"{integration.provider} {integration.payment_method} - {flow_name.replace('_', ' ').title()}"
        description = f"Test {' -> '.join(operations)} flow for {integration.provider} {integration.payment_method}"
        
        steps = []
        for idx, operation in enumerate(operations, start=1):
            step = self._create_step(integration, operation, idx)
            if step:
                steps.append(step)
        
        if not steps:
            return None
        
        return TestCase(
            id=test_case_id,
            name=test_case_name,
            description=description,
            steps=steps
        )
    
    def _create_step(self, integration: ProviderIntegration, operation: str, step_id: int) -> Optional[Step]:
        """Create a step for a specific operation."""
        input_data = self._get_input_data(integration, operation, step_id)
        
        # Define capture variables based on operation
        capture_vars = self._get_capture_variables(integration, operation)
        
        return Step(
            step_id=step_id,
            operation=operation,
            provider=integration.provider.lower(),
            description=f"Execute {operation} with {integration.provider}",
            input_data=input_data,
            capture_variables=capture_vars,
            expected_status="success"
        )
    
    def _get_input_data(self, integration: ProviderIntegration, operation: str, step_id: int) -> Dict[str, Any]:
        """Get input data for an operation based on payment method and preset."""
        country = integration.country
        currency = self.config.country_currency.get(country, "BRL")
        amount = self.config.test_amounts.get(currency, 100.00)
        
        payment_method = integration.payment_method.upper()
        
        # Base input data
        input_data: Dict[str, Any] = {
            "description": f"{integration.provider} {operation.title()} Test",
            "merchant_order_id": f"order_{integration.integration_id.lower()}_{step_id:03d}",
            "country": country,
            "amount": {
                "currency": currency,
                "value": amount
            },
            "workflow": "DIRECT"
        }
        
        # Operations that reference previous step results
        if operation in ('capture', 'refund', 'partial_refund', 'cancel'):
            var_prefix = integration.integration_id.lower().replace('_', '')
            
            # Base data for post-authorization operations
            post_auth_input: Dict[str, Any] = {
                "payment_id": f"${{{var_prefix}_payment_id}}",
                "transaction_id": f"${{{var_prefix}_transaction_id}}",
                "merchant_reference": f"{operation}_{integration.integration_id.lower()}_{step_id:03d}"
            }
            
            if operation == 'capture':
                # Capture requires: merchant_reference, reason, amount
                post_auth_input["reason"] = "PRODUCT_CONFIRMED"
                post_auth_input["amount"] = {
                    "currency": f"${{{var_prefix}_amount_currency}}",
                    "value": f"${{{var_prefix}_amount_value}}"
                }
            elif operation == 'refund':
                post_auth_input["reason"] = "REQUESTED_BY_CUSTOMER"
                post_auth_input["amount"] = {
                    "currency": f"${{{var_prefix}_amount_currency}}",
                    "value": f"${{{var_prefix}_amount_value}}"
                }
            elif operation == 'partial_refund':
                partial_amount = round(amount * 0.5, 2)
                post_auth_input["reason"] = "REQUESTED_BY_CUSTOMER"
                post_auth_input["amount"] = {
                    "currency": f"${{{var_prefix}_amount_currency}}",
                    "value": partial_amount
                }
            elif operation == 'cancel':
                # Cancel requires: merchant_reference, reason
                post_auth_input["reason"] = "REQUESTED_BY_CUSTOMER"
            
            return post_auth_input
        
        # Add customer data for payment operations
        input_data["customer_payer"] = self._get_customer_data(country)
        
        # Add payment method specific data
        if payment_method == "CARD":
            input_data["payment_method"] = self._get_card_payment_method(operation)
        elif payment_method == "PIX":
            input_data["payment_method"] = {"type": "PIX"}
        elif payment_method == "BOLETO":
            input_data["payment_method"] = {"type": "BOLETO"}
        else:
            input_data["payment_method"] = {"type": payment_method}
        
        # Add metadata
        input_data["metadata"] = [
            {"key": "provider", "value": integration.provider.lower()},
            {"key": "payment_method", "value": payment_method.lower()},
            {"key": "generated_by", "value": "matrix"}
        ]
        
        return input_data
    
    def _get_customer_data(self, country: str) -> Dict[str, Any]:
        """Get customer data based on country."""
        # Default Brazil customer
        # NOTE: Do NOT include "id" field - Yuno will create the customer if it doesn't exist
        # If you need to use an existing customer, set the ID from an environment variable or config
        customer = {
            "email": "test@y.uno",
            "first_name": "Test",
            "last_name": "User",
            "document": {
                "document_type": "CPF",
                "document_number": "47033278802"
            },
            "billing_address": {
                "address_line_1": "Test Street, 123",
                "city": "São Paulo",
                "state": "SP",
                "zip_code": "01234-567",
                "country": country,
                "neighborhood": "Centro"
            },
            "phone": {
                "country_code": "55",
                "number": "11987654321"
            }
        }
        
        # Adjust document type based on country
        if country == "MX":
            customer["document"]["document_type"] = "CURP"
            customer["document"]["document_number"] = "GOGC850101HDFRRL09"
            customer["phone"]["country_code"] = "52"
        elif country == "CO":
            customer["document"]["document_type"] = "CC"
            customer["document"]["document_number"] = "1234567890"
            customer["phone"]["country_code"] = "57"
        elif country == "AR":
            customer["document"]["document_type"] = "DNI"
            customer["document"]["document_number"] = "12345678"
            customer["phone"]["country_code"] = "54"
        
        return customer
    
    def _get_card_payment_method(self, operation: str) -> Dict[str, Any]:
        """Get card payment method data."""
        # Determine if this is a capture operation
        capture = operation.lower() in ('purchase', 'capture')
        
        return {
            "type": "CARD",
            "detail": {
                "card": {
                    "verify": operation.lower() == 'verify',
                    "installments": 1,
                    "capture": capture if operation.lower() != 'authorize' else False,
                    "card_data": {
                        "number": "4111111111111111",
                        "expiration_month": 12,
                        "expiration_year": 27,
                        "security_code": "123",
                        "holder_name": "TEST USER"
                    }
                }
            }
        }
    
    def _get_capture_variables(self, integration: ProviderIntegration, operation: str) -> Optional[Dict[str, str]]:
        """Get capture variables for an operation."""
        prefix = integration.integration_id.lower().replace('_', '')
        
        if operation in ('authorize', 'purchase', 'verify'):
            return {
                f"{prefix}_payment_id": "$.body.id",
                f"{prefix}_transaction_id": "$.body.transactions.id",
                f"{prefix}_status": "$.body.status",
                f"{prefix}_amount_value": "$.body.amount.value",
                f"{prefix}_amount_currency": "$.body.amount.currency"
            }
        
        if operation == 'capture':
            # After capture, the refund must target the CAPTURE transaction ID ($.body.id),
            # not the original AUTHORIZE transaction ID.
            return {
                f"{prefix}_transaction_id": "$.body.id",
            }
        
        return None
    
    def generate_single_operation_test(
        self, 
        integration: ProviderIntegration, 
        operation: str
    ) -> Optional[TestCase]:
        """Generate a single operation test case."""
        if not integration.supports_operation(operation):
            return None
        
        return self._create_test_case(integration, operation, [operation])
