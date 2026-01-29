"""
API client for MATRIX.

Handles HTTP requests to payment provider APIs.
Currently running in placeholder mode with mock responses.
"""

import uuid
from datetime import datetime
from typing import Any, Dict
from colorama import Fore

from src.models import Config, APIResponse


class APIClient:
    """
    HTTP client for payment provider APIs.

    Currently implements placeholder/mock mode for testing.
    Real API integration to be added later.
    """

    def __init__(self, config: Config):
        """
        Initialize API client.

        Args:
            config: Application configuration
        """
        self.config = config
        self.placeholder_mode = config.placeholder_mode

        if self.placeholder_mode:
            print(f"{Fore.YELLOW}⚠ Running in PLACEHOLDER MODE - using mock API responses\n")

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
            'tokenize': self.tokenize
        }

        if operation not in operation_methods:
            raise ValueError(f"Unknown operation: {operation}")

        return operation_methods[operation](provider, data)

    def authorize(self, provider: str, data: Dict[str, Any]) -> APIResponse:
        """
        Execute authorization operation.

        Args:
            provider: Provider identifier
            data: Authorization data

        Returns:
            Mock authorization response
        """
        if not self.placeholder_mode:
            raise NotImplementedError("Real API integration not yet implemented")

        # Generate mock response
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

        Args:
            provider: Provider identifier
            data: Capture data

        Returns:
            Mock capture response
        """
        if not self.placeholder_mode:
            raise NotImplementedError("Real API integration not yet implemented")

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
        Execute purchase operation (authorize + capture).

        Args:
            provider: Provider identifier
            data: Purchase data

        Returns:
            Mock purchase response
        """
        if not self.placeholder_mode:
            raise NotImplementedError("Real API integration not yet implemented")

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

        Args:
            provider: Provider identifier
            data: Refund data

        Returns:
            Mock refund response
        """
        if not self.placeholder_mode:
            raise NotImplementedError("Real API integration not yet implemented")

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

        Args:
            provider: Provider identifier
            data: Void data

        Returns:
            Mock void response
        """
        if not self.placeholder_mode:
            raise NotImplementedError("Real API integration not yet implemented")

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
