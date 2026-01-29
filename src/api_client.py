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
            'void': self.void,
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

        Args:
            provider: Provider identifier (can be passed in metadata)
            data: Payment data (follows Yuno API structure)

        Returns:
            APIResponse object
        """
        if self.placeholder_mode:
            return self._mock_payment(provider, data)

        # Ensure required fields are present
        if "account_id" not in data and self.yuno_account_id:
            data["account_id"] = self.yuno_account_id

        # Merge with default payment data from config if available
        if hasattr(self.config, 'default_payment_data'):
            default_data = self.config.default_payment_data
            # Merge default data with provided data (provided data takes precedence)
            for key, value in default_data.items():
                if key not in data:
                    data[key] = value

        # Add provider to metadata if specified
        if provider and provider.lower() != "yuno":
            if "metadata" not in data:
                data["metadata"] = []
            # Check if provider metadata already exists
            provider_exists = any(m.get("key") == "provider" for m in data["metadata"])
            if not provider_exists:
                data["metadata"].append({"key": "provider", "value": provider})

        return self._make_yuno_request("/payments", "POST", data)

    def _mock_payment(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Generate mock Yuno payment response.

        Args:
            provider: Provider identifier
            data: Payment data

        Returns:
            Mock APIResponse
        """
        payment_id = f"pay_{uuid.uuid4().hex[:16]}"
        transaction_id = f"txn_{uuid.uuid4().hex[:12]}"

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "id": payment_id,
                "transaction_id": transaction_id,
                "status": "SUCCEEDED",
                "amount": data.get("amount", {"value": 0, "currency": "USD"}),
                "merchant_order_id": data.get("merchant_order_id", f"order_{uuid.uuid4().hex[:8]}"),
                "description": data.get("description", "Test Payment"),
                "country": data.get("country", "US"),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "provider": provider
            },
            duration_ms=180
        )

    def authorize(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute authorization operation.

        For Yuno API: Creates a payment with capture=false
        For placeholder: Returns mock authorization

        Args:
            provider: Provider identifier
            data: Authorization data

        Returns:
            Authorization response
        """
        if not self.placeholder_mode:
            # For Yuno, authorization is a payment with capture=false
            if "payment_method" not in data:
                data["payment_method"] = {}
            if "detail" not in data["payment_method"]:
                data["payment_method"]["detail"] = {}
            if "card" not in data["payment_method"]["detail"]:
                data["payment_method"]["detail"]["card"] = {}

            # Set capture to false for authorization only
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
        For placeholder: Returns mock capture

        Args:
            provider: Provider identifier
            data: Capture data (must include payment_id or transaction_id)

        Returns:
            Capture response
        """
        if not self.placeholder_mode:
            # For Yuno, we need the payment ID to capture
            payment_id = data.get("payment_id") or data.get("transaction_id")
            if not payment_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={},
                    error="payment_id or transaction_id required for capture"
                )

            # Capture endpoint: POST /v1/payments/{payment_id}/capture
            capture_data = {
                "amount": data.get("amount")
            } if "amount" in data else {}

            return self._make_yuno_request(
                f"/payments/{payment_id}/capture",
                "POST",
                capture_data
            )

        # Placeholder mode
        transaction_id = data.get("transaction_id", f"txn_{uuid.uuid4().hex[:12]}")

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "transaction_id": transaction_id,
                "status": "captured",
                "amount": data.get("amount", 0),
                "currency": data.get("currency", "USD"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
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
        For placeholder: Returns mock refund

        Args:
            provider: Provider identifier
            data: Refund data (must include payment_id or transaction_id)

        Returns:
            Refund response
        """
        if not self.placeholder_mode:
            # For Yuno, we need the payment ID to refund
            payment_id = data.get("payment_id") or data.get("transaction_id")
            if not payment_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={},
                    error="payment_id or transaction_id required for refund"
                )

            # Refund endpoint: POST /v1/payments/{payment_id}/refund
            refund_data = {
                "amount": data.get("amount")
            } if "amount" in data else {}

            return self._make_yuno_request(
                f"/payments/{payment_id}/refund",
                "POST",
                refund_data
            )

        # Placeholder mode
        transaction_id = data.get("transaction_id", f"txn_{uuid.uuid4().hex[:12]}")
        refund_id = f"ref_{uuid.uuid4().hex[:12]}"

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "transaction_id": transaction_id,
                "refund_id": refund_id,
                "status": "refunded",
                "amount": data.get("amount", 0),
                "currency": data.get("currency", "USD"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "provider": provider
            },
            duration_ms=160
        )

    def void(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute void operation.

        For Yuno API: Voids (cancels) a payment
        For placeholder: Returns mock void

        Args:
            provider: Provider identifier
            data: Void data (must include payment_id or transaction_id)

        Returns:
            Void response
        """
        if not self.placeholder_mode:
            # For Yuno, we need the payment ID to void
            payment_id = data.get("payment_id") or data.get("transaction_id")
            if not payment_id:
                return APIResponse(
                    status_code=400,
                    headers={},
                    body={},
                    error="payment_id or transaction_id required for void"
                )

            # Void endpoint: POST /v1/payments/{payment_id}/void
            return self._make_yuno_request(
                f"/payments/{payment_id}/void",
                "POST",
                {}
            )

        # Placeholder mode
        transaction_id = data.get("transaction_id", f"txn_{uuid.uuid4().hex[:12]}")

        return APIResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body={
                "transaction_id": transaction_id,
                "status": "voided",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "provider": provider
            },
            duration_ms=100
        )

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
