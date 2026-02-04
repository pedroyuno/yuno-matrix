"""
API client for MATRIX.

Handles HTTP requests to payment provider APIs.
Supports both placeholder mode (for testing) and real Yuno Payment API.
"""

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

            return APIResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response_body,
                duration_ms=duration_ms,
                error=None if response.ok else f"HTTP {response.status_code}: {response.reason}"
            )

        except requests.exceptions.Timeout:
            return APIResponse(
                status_code=408,
                headers={},
                body={},
                error="Request timeout"
            )
        except requests.exceptions.RequestException as e:
            return APIResponse(
                status_code=0,
                headers={},
                body={},
                error=f"Request failed: {str(e)}"
            )

    def payment(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute a Yuno payment operation (authorize + capture in one step).

        The user's JSON payload is sent as-is, with only two modifications:
        1. account_id is added if not present (required by Yuno API)
        2. provider metadata is updated to match the provider being tested

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
        if not self.placeholder_mode:
            payment_id = data.get("payment_id")
            transaction_id = data.get("transaction_id")

            if not payment_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "payment_id is required for capture"},
                    error="payment_id is required for capture"
                )

            if not transaction_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "transaction_id is required for capture"},
                    error="transaction_id is required for capture"
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
        mock_transaction_id = data.get("transaction_id", f"txn_{uuid.uuid4().hex[:12]}")
        mock_payment_id = data.get("payment_id", f"pay_{uuid.uuid4().hex[:16]}")

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
            duration_ms=120
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
        if not self.placeholder_mode:
            payment_id = data.get("payment_id")
            transaction_id = data.get("transaction_id")

            if not payment_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "payment_id is required for refund"},
                    error="payment_id is required for refund"
                )

            if not transaction_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "transaction_id is required for refund"},
                    error="transaction_id is required for refund"
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

            return self._make_yuno_request(
                f"/payments/{payment_id}/transactions/{transaction_id}/refund",
                "POST",
                refund_data
            )

        # Placeholder mode
        mock_transaction_id = data.get("transaction_id", f"txn_{uuid.uuid4().hex[:12]}")
        mock_payment_id = data.get("payment_id", f"pay_{uuid.uuid4().hex[:16]}")
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
            duration_ms=160
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
        if not self.placeholder_mode:
            payment_id = data.get("payment_id")
            transaction_id = data.get("transaction_id")

            if not payment_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "payment_id is required for cancel"},
                    error="payment_id is required for cancel"
                )

            if not transaction_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={"error": "transaction_id is required for cancel"},
                    error="transaction_id is required for cancel"
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
        mock_transaction_id = data.get("transaction_id", f"txn_{uuid.uuid4().hex[:12]}")
        mock_payment_id = data.get("payment_id", f"pay_{uuid.uuid4().hex[:16]}")
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
            duration_ms=100
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
