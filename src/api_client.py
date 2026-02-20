"""
API client for MATRIX.

Handles HTTP requests to payment provider APIs.
Supports both placeholder mode (for testing) and real Yuno Payment API.
"""

import copy
import os
import uuid
import requests
from datetime import datetime
from typing import Any, Dict, Optional
from colorama import Fore
from dotenv import load_dotenv

from src.models import Config, APIResponse

# Load environment variables
load_dotenv()


class APIClient:
    """
    HTTP client for payment provider APIs.

    Supports two modes:
    1. Placeholder mode: Returns mock responses for testing
    2. Yuno API mode: Makes real HTTP calls to Yuno Payment API
    """

    def __init__(self, config: Config):
        """
        Initialize API client.

        Args:
            config: Application configuration
        """
        self.config = config
        self.placeholder_mode = config.placeholder_mode

        # Load Yuno API credentials from environment
        self.yuno_public_key = os.getenv("YUNO_PUBLIC_API_KEY", "")
        self.yuno_private_key = os.getenv("YUNO_PRIVATE_SECRET_KEY", "")
        self.yuno_account_id = os.getenv("YUNO_ACCOUNT_ID", "")
        self.yuno_environment = os.getenv("YUNO_ENVIRONMENT", "sandbox")

        # Determine Yuno API base URL
        if hasattr(config.api, 'yuno'):
            if self.yuno_environment == "production":
                self.yuno_base_url = config.api.yuno.get("production_url", "https://api.y.uno/v1")
            else:
                self.yuno_base_url = config.api.yuno.get("sandbox_url", "https://api-sandbox.y.uno/v1")
        else:
            self.yuno_base_url = "https://api-sandbox.y.uno/v1"

        if self.placeholder_mode:
            print(f"{Fore.YELLOW}⚠ Running in PLACEHOLDER MODE - using mock API responses\n")
        else:
            if not self.yuno_public_key or not self.yuno_private_key:
                print(f"{Fore.RED}⚠ WARNING: Yuno API credentials not found in environment variables")
                print(f"{Fore.RED}  Please configure .env file with YUNO_PUBLIC_API_KEY and YUNO_PRIVATE_SECRET_KEY")
                print(f"{Fore.YELLOW}  Falling back to PLACEHOLDER MODE\n")
                self.placeholder_mode = True
            else:
                print(f"{Fore.GREEN}✓ Yuno API configured ({self.yuno_environment} environment)\n")

    def execute_operation(
        self,
        operation: str,
        provider: str,
        data: Dict[str, Any]
    ) -> APIResponse:
        """
        Execute an API operation.

        Args:
            operation: Operation type (authorize, capture, purchase, refund, etc.)
            provider: Provider identifier
            data: Operation input data

        Returns:
            APIResponse object

        Raises:
            ValueError: If operation is not recognized
        """
        operation = operation.lower()

        # Dispatch to specific operation methods
        operation_methods = {
            'authorize': self.authorize,
            'capture': self.capture,
            'purchase': self.purchase,
            'refund': self.refund,
            'partial_refund': self.refund,
            'cancel': self.cancel,
            'void': self.void,  # Alias for cancel
            'verify': self.verify,
            'tokenize': self.tokenize,
            'payment': self.payment  # Yuno-specific payment operation
        }

        if operation not in operation_methods:
            raise ValueError(f"Unknown operation: {operation}")

        return operation_methods[operation](provider, data)

    def _make_yuno_request(
        self,
        endpoint: str,
        method: str,
        data: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> APIResponse:
        """
        Make a real HTTP request to Yuno API.

        Args:
            endpoint: API endpoint path (e.g., "/payments")
            method: HTTP method (GET, POST, etc.)
            data: Request body data
            idempotency_key: Optional idempotency key, will generate if not provided

        Returns:
            APIResponse object
        """
        import json as _json
        url = f"{self.yuno_base_url}{endpoint}"

        # Generate idempotency key if not provided
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        headers = {
            "accept": "application/json",
            "charset": "utf-8",
            "content-type": "application/json",
            "public-api-key": self.yuno_public_key,
            "private-secret-key": self.yuno_private_key,
            "X-Idempotency-Key": idempotency_key
        }

        # Log the outgoing HTTP request
        print(f"{Fore.CYAN}[API REQUEST] {method} {url}{Fore.RESET}")
        print(f"{Fore.CYAN}[API REQUEST] Body: {_json.dumps(data, indent=2, default=str)}{Fore.RESET}")

        start_time = datetime.utcnow()

        try:
            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=self.config.api.timeout if hasattr(self.config.api, 'timeout') else 30
            )

            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Parse response body
            try:
                response_body = response.json()
            except ValueError:
                response_body = {"raw_response": response.text}

            # Log the HTTP response
            print(f"{Fore.BLUE}[API RESPONSE] Status: {response.status_code} ({response.reason}) - {duration_ms}ms{Fore.RESET}")
            print(f"{Fore.BLUE}[API RESPONSE] Body: {_json.dumps(response_body, indent=2, default=str)}{Fore.RESET}")

            return APIResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response_body,
                duration_ms=duration_ms,
                error=None if response.ok else f"HTTP {response.status_code}: {response.reason}",
                request_url=url
            )

        except requests.exceptions.Timeout:
            print(f"{Fore.RED}[API RESPONSE] TIMEOUT on {method} {url}{Fore.RESET}")
            return APIResponse(
                status_code=408,
                headers={},
                body={},
                error="Request timeout",
                request_url=url
            )
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}[API RESPONSE] REQUEST FAILED: {str(e)}{Fore.RESET}")
            return APIResponse(
                status_code=0,
                headers={},
                body={},
                error=f"Request failed: {str(e)}",
                request_url=url
            )

    def _replace_card_data_for_provider(self, provider: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace card data with provider-specific test card if configured.
        
        Only replaces direct card data - does not touch vaulted tokens or one-time tokens.
        If no provider-specific card is configured, returns data unchanged.
        
        Args:
            provider: Provider identifier
            data: Payment data that may contain card_data
            
        Returns:
            Data with card_data replaced if provider has a test card configured
        """
        # Skip if no provider test cards configured
        if not hasattr(self.config, 'provider_test_cards') or not self.config.provider_test_cards:
            return data
        
        provider_cards = self.config.provider_test_cards
        provider_key = provider.lower()
        
        # Check if provider has a test card configured
        if provider_key not in provider_cards:
            return data
        
        # Check if this is a token-based payment (skip replacement)
        payment_method = data.get("payment_method", {})
        
        # Check for vaulted_token at payment_method level
        if payment_method.get("vaulted_token"):
            return data
        
        detail = payment_method.get("detail", {})
        
        # Check for vaulted_token in detail.token
        if detail.get("token", {}).get("vaulted_token"):
            return data
        
        # Check if card_data exists (direct card payment)
        card = detail.get("card", {})
        if "card_data" not in card:
            return data
        
        # Replace card data with provider-specific test card
        test_card = provider_cards[provider_key]
        data["payment_method"]["detail"]["card"]["card_data"] = {
            "number": test_card.number,
            "expiration_month": test_card.expiration_month,
            "expiration_year": test_card.expiration_year,
            "security_code": test_card.security_code,
            "holder_name": test_card.holder_name
        }
        
        return data

    def create_customer(self, customer_data: Dict[str, Any]) -> APIResponse:
        """
        Create a Yuno customer from payer data.

        Used by the E2E flow to auto-create a customer when
        customer_payer.id is missing from the payment data.

        Args:
            customer_data: Dict with email, first_name, last_name, document,
                           phone, billing_address, etc.

        Returns:
            APIResponse whose body contains the 'id' field (Yuno customer UUID)
        """
        merchant_customer_id = f"matrix_e2e_{uuid.uuid4().hex[:12]}"
        email = customer_data.get("email", "matrix-e2e@y.uno")

        if self.placeholder_mode:
            return APIResponse(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body={
                    "id": str(uuid.uuid4()),
                    "merchant_customer_id": merchant_customer_id,
                    "email": email,
                    "first_name": customer_data.get("first_name"),
                    "last_name": customer_data.get("last_name"),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                },
                duration_ms=60,
                request_url=f"{self.yuno_base_url}/customers"
            )

        payload: Dict[str, Any] = {
            "merchant_customer_id": merchant_customer_id,
            "email": email,
        }

        for field in ("first_name", "last_name", "country", "gender",
                       "date_of_birth", "nationality", "document",
                       "phone", "billing_address", "shipping_address"):
            if field in customer_data and customer_data[field]:
                payload[field] = customer_data[field]

        return self._make_yuno_request("/customers", "POST", payload)

    def create_checkout_session(self, data: Dict[str, Any]) -> APIResponse:
        """
        Create a Yuno checkout session from payment data.

        Extracts customer_id, country, amount, and description from a standard
        payment JSON and calls POST /checkout/sessions.

        Args:
            data: Payment data containing customer_payer.id, country, amount, description

        Returns:
            APIResponse whose body contains the 'checkout_session' field
        """
        customer_id = (data.get("customer_payer") or {}).get("id")

        if not customer_id:
            return APIResponse(
                status_code=400,
                headers={},
                body={"error": "customer_payer.id is required for E2E SDK checkout sessions"},
                error="customer_payer.id is required for E2E SDK checkout sessions",
                request_url=f"{self.yuno_base_url}/checkout/sessions"
            )

        if self.placeholder_mode:
            session_id = str(uuid.uuid4())
            return APIResponse(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body={
                    "checkout_session": session_id,
                    "merchant_order_id": str(uuid.uuid4()),
                    "country": data.get("country", "US"),
                    "payment_description": data.get("description", "MATRIX E2E SDK Test"),
                    "customer_id": customer_id,
                    "amount": data.get("amount", {"currency": "USD", "value": 0}),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "workflow": "SDK_CHECKOUT",
                },
                duration_ms=80,
                request_url=f"{self.yuno_base_url}/checkout/sessions"
            )

        checkout_data = {
            "customer_id": customer_id,
            "merchant_order_id": str(uuid.uuid4()),
            "payment_description": data.get("description", "MATRIX E2E SDK Test"),
            "country": data.get("country", "US"),
            "amount": data.get("amount", {"currency": "USD", "value": 0}),
        }

        if self.yuno_account_id:
            checkout_data["account_id"] = self.yuno_account_id

        return self._make_yuno_request("/checkout/sessions", "POST", checkout_data)

    def e2e_create_payment(
        self,
        provider: str,
        data: Dict[str, Any],
        one_time_token: str,
        checkout_session: str
    ) -> APIResponse:
        """
        Create a payment using an OTT from the SDK Lite E2E flow.

        Transforms a standard DIRECT payment JSON into an SDK_CHECKOUT payment
        by replacing card_data with the one-time token.

        Args:
            provider: Provider identifier
            data: Original payment data (DIRECT workflow with card_data)
            one_time_token: OTT generated by the Yuno SDK Lite
            checkout_session: Checkout session ID

        Returns:
            APIResponse from the payment creation
        """
        payment_data = copy.deepcopy(data)

        payment_data["workflow"] = "SDK_CHECKOUT"
        payment_data["checkout"] = {"session": checkout_session}

        payment_data["payment_method"] = {
            "type": "CARD",
            "token": one_time_token,
        }

        return self.payment(provider, payment_data)

    def payment(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute a Yuno payment operation (authorize + capture in one step).

        The user's JSON payload is sent as-is, with the following modifications:
        1. account_id is added if not present (required by Yuno API)
        2. provider metadata is updated to match the provider being tested
        3. card_data is replaced with provider-specific test card (if configured)

        Args:
            provider: Provider identifier (can be passed in metadata)
            data: Payment data (follows Yuno API structure)

        Returns:
            APIResponse object
        """
        if self.placeholder_mode:
            return self._mock_payment(provider, data)

        # Only add account_id if not present (required by Yuno API)
        if "account_id" not in data and self.yuno_account_id:
            data["account_id"] = self.yuno_account_id

        # Always generate a unique merchant_order_id to prevent duplicate order errors
        # across providers and re-runs
        data["merchant_order_id"] = str(uuid.uuid4())

        # Replace card data with provider-specific test card (if configured)
        # This only affects direct card payments, not vaulted tokens or one-time tokens
        data = self._replace_card_data_for_provider(provider, data)

        # Update provider in metadata to match the provider being tested
        if provider and provider.lower() != "yuno":
            if "metadata" not in data:
                data["metadata"] = []
            
            # Update existing provider metadata or add new one
            provider_updated = False
            for m in data["metadata"]:
                if m.get("key") == "provider":
                    m["value"] = provider
                    provider_updated = True
                    break
            
            if not provider_updated:
                data["metadata"].append({"key": "provider", "value": provider})

        return self._make_yuno_request("/payments", "POST", data)

    def _mock_payment(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Generate mock Yuno payment response.

        Args:
            provider: Provider identifier
            data: Payment data

        Returns:
            Mock APIResponse matching Yuno API structure
        """
        payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        transaction_id = f"txn_{uuid.uuid4().hex[:12]}"

        # Determine if capture is enabled (default true for purchase)
        capture = True
        if "payment_method" in data and "detail" in data["payment_method"]:
            if "card" in data["payment_method"]["detail"]:
                capture = data["payment_method"]["detail"]["card"].get("capture", True)

        # Set status based on capture flag
        if capture:
            status = "SUCCEEDED"
            sub_status = "CAPTURED"
        else:
            status = "PENDING"
            sub_status = "AUTHORIZED"

        amount_data = data.get("amount", {"value": 0, "currency": "USD"})

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "id": payment_id,
                "status": status,
                "sub_status": sub_status,
                "amount": {
                    "value": amount_data.get("value", 0),
                    "currency": amount_data.get("currency", "USD"),
                    "captured": amount_data.get("value", 0) if capture else 0,
                    "refunded": 0
                },
                "merchant_order_id": data.get("merchant_order_id", f"order_{uuid.uuid4().hex[:8]}"),
                "description": data.get("description", "Test Payment"),
                "country": data.get("country", "US"),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "transactions": {
                    "id": transaction_id,
                    "type": "AUTHORIZE" if not capture else "PAYMENT",
                    "status": status,
                    "category": "CARD",
                    "amount": amount_data.get("value", 0),
                    "response_code": "SUCCEEDED",
                    "response_message": "Transaction successful",
                    "created_at": datetime.utcnow().isoformat() + "Z"
                },
                "provider": provider
            },
            duration_ms=180
        )

    def authorize(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute authorization operation.

        For Yuno API: Creates a payment with capture=false.
        The user's JSON is preserved - only sets capture=false if the card structure exists.

        Args:
            provider: Provider identifier
            data: Authorization data

        Returns:
            Authorization response
        """
        if not self.placeholder_mode:
            # For Yuno, authorization is a payment with capture=false
            # Only set capture=false if the user provided a card payment method
            # Don't force creation of nested structures that might not apply
            if "payment_method" in data:
                if "detail" in data["payment_method"]:
                    if "card" in data["payment_method"]["detail"]:
                        # User provided card details - set capture to false
                        data["payment_method"]["detail"]["card"]["capture"] = False

            return self.payment(provider, data)

        # Placeholder mode
        transaction_id = f"txn_{uuid.uuid4().hex[:12]}"
        auth_code = f"AUTH{uuid.uuid4().hex[:6].upper()}"

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "transaction_id": transaction_id,
                "status": "authorized",
                "auth_code": auth_code,
                "amount": data.get("amount", 0),
                "currency": data.get("currency", "USD"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "provider": provider
            },
            duration_ms=150
        )

    def capture(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute capture operation.

        For Yuno API: Captures a previously authorized payment
        Endpoint: POST /v1/payments/{payment_id}/transactions/{transaction_id}/capture

        Args:
            provider: Provider identifier
            data: Capture data (must include payment_id and transaction_id)
                - payment_id: The payment ID
                - transaction_id: The transaction ID
                - amount: Optional amount object with currency and value
                - merchant_reference: Reference for the capture (auto-generated if not provided)
                - reason: Reason for capture (default: PRODUCT_CONFIRMED)

        Returns:
            Capture response
        """
        payment_id = data.get("payment_id")
        transaction_id = data.get("transaction_id")
        
        # Build the expected URL even for error cases
        capture_url = f"{self.yuno_base_url}/payments/{payment_id or '{payment_id}'}/transactions/{transaction_id or '{transaction_id}'}/capture"
        
        if not self.placeholder_mode:
            if not payment_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "payment_id is required for capture"},
                    error="payment_id is required for capture",
                    request_url=capture_url
                )

            if not transaction_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "transaction_id is required for capture"},
                    error="transaction_id is required for capture",
                    request_url=capture_url
                )

            # Build capture request body per Yuno API spec
            capture_data = {
                "merchant_reference": data.get("merchant_reference", f"capture_{uuid.uuid4().hex[:8]}"),
                "reason": data.get("reason", "PRODUCT_CONFIRMED"),
                "amount": data.get("amount", {"currency": "USD", "value": 0})
            }

            # Include additional_data if provided
            if "additional_data" in data:
                capture_data["additional_data"] = data["additional_data"]

            return self._make_yuno_request(
                f"/payments/{payment_id}/transactions/{transaction_id}/capture",
                "POST",
                capture_data
            )

        # Placeholder mode
        mock_transaction_id = transaction_id or f"txn_{uuid.uuid4().hex[:12]}"
        mock_payment_id = payment_id or f"pay_{uuid.uuid4().hex[:16]}"

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "id": f"cap_{uuid.uuid4().hex[:12]}",
                "type": "CAPTURE",
                "status": "SUCCEEDED",
                "category": "CARD",
                "amount": data.get("amount", {"currency": "USD", "value": 0, "captured": 0, "refunded": 0}),
                "merchant_reference": data.get("merchant_reference", f"capture_{uuid.uuid4().hex[:8]}"),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "response_code": "SUCCEEDED",
                "response_message": "Transaction successful",
                "payment": {
                    "id": mock_payment_id,
                    "status": "SUCCEEDED",
                    "sub_status": "CAPTURED"
                },
                "provider": provider
            },
            duration_ms=120,
            request_url=f"{self.yuno_base_url}/payments/{mock_payment_id}/transactions/{mock_transaction_id}/capture"
        )

    def purchase(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute purchase operation (authorize + capture in one step).

        For Yuno API: Creates a payment with capture=true (default)
        For placeholder: Returns mock purchase

        Args:
            provider: Provider identifier
            data: Purchase data

        Returns:
            Purchase response
        """
        if not self.placeholder_mode:
            # For Yuno, purchase is a payment with capture=true (default)
            if "payment_method" not in data:
                data["payment_method"] = {}
            if "detail" not in data["payment_method"]:
                data["payment_method"]["detail"] = {}
            if "card" not in data["payment_method"]["detail"]:
                data["payment_method"]["detail"]["card"] = {}

            # Set capture to true for immediate capture
            data["payment_method"]["detail"]["card"]["capture"] = True

            return self.payment(provider, data)

        # Placeholder mode
        transaction_id = f"txn_{uuid.uuid4().hex[:12]}"

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "transaction_id": transaction_id,
                "status": "completed",
                "amount": data.get("amount", 0),
                "currency": data.get("currency", "USD"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "provider": provider
            },
            duration_ms=180
        )

    def refund(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute refund operation.

        For Yuno API: Creates a refund for a payment
        Endpoint: POST /v1/payments/{payment_id}/transactions/{transaction_id}/refund

        Args:
            provider: Provider identifier
            data: Refund data
                - payment_id: The payment ID
                - transaction_id: The transaction ID
                - merchant_reference: Reference for the refund (auto-generated if not provided)
                - reason: Reason for refund (DUPLICATE, FRAUDULENT, REQUESTED_BY_CUSTOMER)
                - description: Optional description
                - amount: Optional amount for partial refunds (omit for full refund)

        Returns:
            Refund response
        """
        import json as _json
        payment_id = data.get("payment_id")
        transaction_id = data.get("transaction_id")
        
        # Log refund input for troubleshooting
        is_partial = "amount" in data
        refund_type = "PARTIAL" if is_partial else "FULL"
        print(f"\n{Fore.YELLOW}{'='*60}")
        print(f"{Fore.YELLOW}[REFUND] Starting {refund_type} refund for provider: {provider}")
        print(f"{Fore.YELLOW}[REFUND] Input data received:")
        print(f"{Fore.YELLOW}  payment_id:    {payment_id}")
        print(f"{Fore.YELLOW}  transaction_id: {transaction_id}")
        print(f"{Fore.YELLOW}  reason:         {data.get('reason', 'N/A')}")
        print(f"{Fore.YELLOW}  amount:         {data.get('amount', 'N/A (full refund)')}")
        print(f"{Fore.YELLOW}  merchant_ref:   {data.get('merchant_reference', 'N/A (auto-generated)')}")
        print(f"{Fore.YELLOW}  All input keys: {list(data.keys())}")
        print(f"{Fore.YELLOW}{'='*60}{Fore.RESET}")
        
        # Build the expected URL even for error cases
        refund_url = f"{self.yuno_base_url}/payments/{payment_id or '{payment_id}'}/transactions/{transaction_id or '{transaction_id}'}/refund"
        
        if not self.placeholder_mode:
            if not payment_id:
                print(f"{Fore.RED}[REFUND] ERROR: payment_id is missing!{Fore.RESET}")
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "payment_id is required for refund"},
                    error="payment_id is required for refund",
                    request_url=refund_url
                )

            if not transaction_id:
                print(f"{Fore.RED}[REFUND] ERROR: transaction_id is missing!{Fore.RESET}")
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "transaction_id is required for refund"},
                    error="transaction_id is required for refund",
                    request_url=refund_url
                )

            # Build refund request body per Yuno API spec
            refund_data = {
                "merchant_reference": data.get("merchant_reference", f"refund_{uuid.uuid4().hex[:8]}")
            }

            # Add optional fields if provided
            if "reason" in data:
                refund_data["reason"] = data["reason"]
            else:
                refund_data["reason"] = "REQUESTED_BY_CUSTOMER"

            if "description" in data:
                refund_data["description"] = data["description"]

            # For partial refund, include amount
            if "amount" in data:
                refund_data["amount"] = data["amount"]

            print(f"{Fore.CYAN}[REFUND] Sending to Yuno API:")
            print(f"{Fore.CYAN}[REFUND] URL: POST {self.yuno_base_url}/payments/{payment_id}/transactions/{transaction_id}/refund")
            print(f"{Fore.CYAN}[REFUND] Request body: {_json.dumps(refund_data, indent=2, default=str)}{Fore.RESET}")

            response = self._make_yuno_request(
                f"/payments/{payment_id}/transactions/{transaction_id}/refund",
                "POST",
                refund_data
            )

            # Log refund result
            if response.is_success:
                print(f"{Fore.GREEN}[REFUND] SUCCESS - Status: {response.status_code}{Fore.RESET}")
            else:
                print(f"{Fore.RED}[REFUND] FAILED - Status: {response.status_code}")
                print(f"{Fore.RED}[REFUND] Error: {response.error}")
                print(f"{Fore.RED}[REFUND] Response body: {_json.dumps(response.body, indent=2, default=str)}{Fore.RESET}")

            return response

        # Placeholder mode
        mock_transaction_id = transaction_id or f"txn_{uuid.uuid4().hex[:12]}"
        mock_payment_id = payment_id or f"pay_{uuid.uuid4().hex[:16]}"
        refund_id = f"ref_{uuid.uuid4().hex[:12]}"

        # Determine if partial or full refund based on amount presence
        is_partial = "amount" in data
        refunded_amount = data.get("amount", {"currency": "USD", "value": 0})

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "id": mock_payment_id,
                "status": "REFUNDED" if not is_partial else "SUCCEEDED",
                "sub_status": "REFUNDED" if not is_partial else "PARTIALLY_REFUNDED",
                "amount": {
                    "captured": 0,
                    "currency": refunded_amount.get("currency", "USD"),
                    "refunded": refunded_amount.get("value", 0),
                    "value": refunded_amount.get("value", 0)
                },
                "transactions": {
                    "id": refund_id,
                    "type": "REFUND",
                    "status": "SUCCEEDED",
                    "category": "CARD",
                    "amount": refunded_amount.get("value", 0),
                    "response_code": "SUCCEEDED",
                    "response_message": "Transaction successful",
                    "reason": data.get("reason", "REQUESTED_BY_CUSTOMER"),
                    "merchant_reference": data.get("merchant_reference", f"refund_{uuid.uuid4().hex[:8]}"),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "updated_at": datetime.utcnow().isoformat() + "Z"
                },
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "provider": provider
            },
            duration_ms=160,
            request_url=f"{self.yuno_base_url}/payments/{mock_payment_id}/transactions/{mock_transaction_id}/refund"
        )

    def cancel(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute cancel operation.

        For Yuno API: Cancels a pending payment (authorized but not captured)
        Endpoint: POST /v1/payments/{payment_id}/transactions/{transaction_id}/cancel

        Args:
            provider: Provider identifier
            data: Cancel data
                - payment_id: The payment ID
                - transaction_id: The transaction ID
                - merchant_reference: Reference for the cancellation (auto-generated if not provided)
                - reason: Reason for cancellation (DUPLICATE, FRAUDULENT, REQUESTED_BY_CUSTOMER)
                - description: Optional description

        Returns:
            Cancel response
        """
        payment_id = data.get("payment_id")
        transaction_id = data.get("transaction_id")
        
        # Build the expected URL even for error cases
        cancel_url = f"{self.yuno_base_url}/payments/{payment_id or '{payment_id}'}/transactions/{transaction_id or '{transaction_id}'}/cancel"
        
        if not self.placeholder_mode:
            if not payment_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "payment_id is required for cancel"},
                    error="payment_id is required for cancel",
                    request_url=cancel_url
                )

            if not transaction_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "transaction_id is required for cancel"},
                    error="transaction_id is required for cancel",
                    request_url=cancel_url
                )

            # Build cancel request body per Yuno API spec
            cancel_data = {
                "merchant_reference": data.get("merchant_reference", f"cancel_{uuid.uuid4().hex[:8]}")
            }

            # Add optional fields if provided
            if "reason" in data:
                cancel_data["reason"] = data["reason"]
            else:
                cancel_data["reason"] = "REQUESTED_BY_CUSTOMER"

            if "description" in data:
                cancel_data["description"] = data["description"]

            return self._make_yuno_request(
                f"/payments/{payment_id}/transactions/{transaction_id}/cancel",
                "POST",
                cancel_data
            )

        # Placeholder mode
        mock_transaction_id = transaction_id or f"txn_{uuid.uuid4().hex[:12]}"
        mock_payment_id = payment_id or f"pay_{uuid.uuid4().hex[:16]}"
        cancel_id = f"cnl_{uuid.uuid4().hex[:12]}"

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "id": cancel_id,
                "type": "CANCEL",
                "status": "SUCCEEDED",
                "category": "CARD",
                "amount": data.get("amount", {"currency": "USD", "value": 0, "captured": 0, "refunded": 0}),
                "merchant_reference": data.get("merchant_reference", f"cancel_{uuid.uuid4().hex[:8]}"),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "response_code": "SUCCEEDED",
                "response_message": "Transaction successful",
                "payment": {
                    "id": mock_payment_id,
                    "status": "CANCELED",
                    "sub_status": "CANCELED"
                },
                "provider": provider
            },
            duration_ms=100,
            request_url=f"{self.yuno_base_url}/payments/{mock_payment_id}/transactions/{mock_transaction_id}/cancel"
        )

    def void(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute void operation (alias for cancel).

        For Yuno API: Voids (cancels) a payment - delegates to cancel operation

        Args:
            provider: Provider identifier
            data: Void data (must include payment_id and transaction_id)

        Returns:
            Void/Cancel response
        """
        # Void is an alias for cancel in Yuno API
        return self.cancel(provider, data)

    def verify(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute verification operation.

        Args:
            provider: Provider identifier
            data: Verification data

        Returns:
            Mock verification response
        """
        if not self.placeholder_mode:
            raise NotImplementedError("Real API integration not yet implemented")

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "status": "verified",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "provider": provider
            },
            duration_ms=90
        )

    def tokenize(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute tokenization operation.

        Args:
            provider: Provider identifier
            data: Tokenization data

        Returns:
            Mock tokenization response
        """
        if not self.placeholder_mode:
            raise NotImplementedError("Real API integration not yet implemented")

        token = f"tok_{uuid.uuid4().hex[:16]}"

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "token": token,
                "status": "tokenized",
                "card_last4": data.get("card_number", "0000")[-4:] if "card_number" in data else "****",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "provider": provider
            },
            duration_ms=110
        )
