"""
Pydantic models for the Yuno Create Payment API.

Based on: https://docs.y.uno/reference/create-payment

These models define the complete structure of a Create Payment request,
including all nested objects and validation rules.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, EmailStr


# =============================================================================
# Enums
# =============================================================================

class WorkflowType(str, Enum):
    """Payment workflow types."""
    SDK_CHECKOUT = "SDK_CHECKOUT"
    CHECKOUT = "CHECKOUT"
    REDIRECT = "REDIRECT"
    DIRECT = "DIRECT"
    SDK_SEAMLESS = "SDK_SEAMLESS"


class PaymentMethodType(str, Enum):
    """Payment method types."""
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH = "CASH"
    BNPL = "BNPL"  # Buy Now Pay Later
    WALLET = "WALLET"
    VOUCHER = "VOUCHER"
    PIX = "PIX"
    BOLETO = "BOLETO"


class DocumentType(str, Enum):
    """Document types for customer identification."""
    CPF = "CPF"
    CNPJ = "CNPJ"
    RG = "RG"
    PASSPORT = "PASSPORT"
    DNI = "DNI"
    CURP = "CURP"
    RFC = "RFC"
    CC = "CC"
    CE = "CE"
    NIT = "NIT"
    RUT = "RUT"
    CI = "CI"
    OTHER = "OTHER"


class ItemCategory(str, Enum):
    """Order item categories."""
    PHYSICAL = "PHYSICAL"
    DIGITAL = "DIGITAL"
    SERVICES = "SERVICES"
    OTHERS = "OTHERS"


# =============================================================================
# Nested Models - Customer
# =============================================================================

class Phone(BaseModel):
    """Phone number details."""
    country_code: Optional[str] = Field(
        default=None,
        description="Phone country code (e.g., '55' for Brazil)",
        json_schema_extra={"ui_label": "Country Code", "ui_placeholder": "55"}
    )
    number: Optional[str] = Field(
        default=None,
        description="Phone number without country code",
        json_schema_extra={"ui_label": "Phone Number", "ui_placeholder": "11987654321"}
    )


class Document(BaseModel):
    """Customer identification document."""
    document_type: Optional[str] = Field(
        default=None,
        description="Type of identification document (CPF, CNPJ, PASSPORT, etc.)",
        json_schema_extra={
            "ui_label": "Document Type",
            "ui_options": [e.value for e in DocumentType]
        }
    )
    document_number: Optional[str] = Field(
        default=None,
        description="Document number",
        json_schema_extra={"ui_label": "Document Number", "ui_placeholder": "12345678900"}
    )


class BillingAddress(BaseModel):
    """Billing address details."""
    address_line_1: Optional[str] = Field(
        default=None,
        description="Primary address line",
        json_schema_extra={"ui_label": "Address Line 1", "ui_placeholder": "123 Main Street"}
    )
    address_line_2: Optional[str] = Field(
        default=None,
        description="Secondary address line (apartment, suite, etc.)",
        json_schema_extra={"ui_label": "Address Line 2", "ui_placeholder": "Apt 4B"}
    )
    city: Optional[str] = Field(
        default=None,
        description="City name",
        json_schema_extra={"ui_label": "City", "ui_placeholder": "São Paulo"}
    )
    state: Optional[str] = Field(
        default=None,
        description="State or province",
        json_schema_extra={"ui_label": "State", "ui_placeholder": "SP"}
    )
    zip_code: Optional[str] = Field(
        default=None,
        description="Postal/ZIP code",
        json_schema_extra={"ui_label": "ZIP Code", "ui_placeholder": "01234-567"}
    )
    country: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Country code (ISO 3166-1 alpha-2)",
        json_schema_extra={"ui_label": "Country", "ui_placeholder": "BR"}
    )
    neighborhood: Optional[str] = Field(
        default=None,
        description="Neighborhood or district",
        json_schema_extra={"ui_label": "Neighborhood", "ui_placeholder": "Centro"}
    )


class ShippingAddress(BaseModel):
    """Shipping address details."""
    address_line_1: Optional[str] = Field(
        default=None,
        description="Primary address line",
        json_schema_extra={"ui_label": "Address Line 1"}
    )
    address_line_2: Optional[str] = Field(
        default=None,
        description="Secondary address line",
        json_schema_extra={"ui_label": "Address Line 2"}
    )
    city: Optional[str] = Field(
        default=None,
        description="City name",
        json_schema_extra={"ui_label": "City"}
    )
    state: Optional[str] = Field(
        default=None,
        description="State or province",
        json_schema_extra={"ui_label": "State"}
    )
    zip_code: Optional[str] = Field(
        default=None,
        description="Postal/ZIP code",
        json_schema_extra={"ui_label": "ZIP Code"}
    )
    country: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Country code (ISO 3166-1 alpha-2)",
        json_schema_extra={"ui_label": "Country"}
    )
    neighborhood: Optional[str] = Field(
        default=None,
        description="Neighborhood or district",
        json_schema_extra={"ui_label": "Neighborhood"}
    )


class CustomerPayer(BaseModel):
    """Customer/payer information."""
    id: Optional[str] = Field(
        default=None,
        description="Customer unique identifier",
        json_schema_extra={"ui_label": "Customer ID"}
    )
    email: Optional[str] = Field(
        default=None,
        description="Customer email address",
        json_schema_extra={"ui_label": "Email", "ui_placeholder": "customer@example.com"}
    )
    first_name: Optional[str] = Field(
        default=None,
        description="Customer first name",
        json_schema_extra={"ui_label": "First Name", "ui_placeholder": "John"}
    )
    last_name: Optional[str] = Field(
        default=None,
        description="Customer last name",
        json_schema_extra={"ui_label": "Last Name", "ui_placeholder": "Doe"}
    )
    document: Optional[Document] = Field(
        default=None,
        description="Customer identification document",
        json_schema_extra={"ui_label": "Document", "ui_group": "customer_payer"}
    )
    billing_address: Optional[BillingAddress] = Field(
        default=None,
        description="Customer billing address",
        json_schema_extra={"ui_label": "Billing Address", "ui_group": "customer_payer"}
    )
    shipping_address: Optional[ShippingAddress] = Field(
        default=None,
        description="Customer shipping address",
        json_schema_extra={"ui_label": "Shipping Address", "ui_group": "customer_payer"}
    )
    phone: Optional[Phone] = Field(
        default=None,
        description="Customer phone number",
        json_schema_extra={"ui_label": "Phone", "ui_group": "customer_payer"}
    )
    gender: Optional[str] = Field(
        default=None,
        description="Customer gender",
        json_schema_extra={"ui_label": "Gender"}
    )
    date_of_birth: Optional[str] = Field(
        default=None,
        description="Customer date of birth (YYYY-MM-DD)",
        json_schema_extra={"ui_label": "Date of Birth", "ui_placeholder": "1990-01-15"}
    )
    nationality: Optional[str] = Field(
        default=None,
        description="Customer nationality (ISO 3166-1 alpha-2)",
        json_schema_extra={"ui_label": "Nationality", "ui_placeholder": "BR"}
    )


# =============================================================================
# Nested Models - Payment Method
# =============================================================================

class CardData(BaseModel):
    """Credit/debit card data."""
    number: Optional[str] = Field(
        default=None,
        description="Card number (PAN)",
        json_schema_extra={"ui_label": "Card Number", "ui_placeholder": "4111111111111111", "ui_sensitive": True}
    )
    expiration_month: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Card expiration month (1-12)",
        json_schema_extra={"ui_label": "Expiration Month", "ui_placeholder": "12"}
    )
    expiration_year: Optional[int] = Field(
        default=None,
        ge=0,
        le=99,
        description="Card expiration year (2-digit, e.g., 27 for 2027)",
        json_schema_extra={"ui_label": "Expiration Year", "ui_placeholder": "27"}
    )
    security_code: Optional[str] = Field(
        default=None,
        description="Card security code (CVV/CVC)",
        json_schema_extra={"ui_label": "Security Code (CVV)", "ui_placeholder": "123", "ui_sensitive": True}
    )
    holder_name: Optional[str] = Field(
        default=None,
        description="Cardholder name as printed on card",
        json_schema_extra={"ui_label": "Cardholder Name", "ui_placeholder": "JOHN DOE"}
    )


class CardDetail(BaseModel):
    """Card payment details."""
    verify: Optional[bool] = Field(
        default=False,
        description="Whether to verify the card without charging",
        json_schema_extra={"ui_label": "Verify Only"}
    )
    installments: Optional[int] = Field(
        default=1,
        ge=1,
        description="Number of installments for the payment",
        json_schema_extra={"ui_label": "Installments", "ui_placeholder": "1"}
    )
    capture: Optional[bool] = Field(
        default=True,
        description="Whether to capture the payment immediately",
        json_schema_extra={"ui_label": "Auto Capture"}
    )
    card_data: Optional[CardData] = Field(
        default=None,
        description="Card details for direct card input",
        json_schema_extra={"ui_label": "Card Data", "ui_group": "payment_method"}
    )
    soft_descriptor: Optional[str] = Field(
        default=None,
        description="Statement descriptor shown to cardholder",
        json_schema_extra={"ui_label": "Soft Descriptor", "ui_placeholder": "MYSTORE"}
    )


class TokenDetail(BaseModel):
    """Token-based payment details (for vaulted cards)."""
    vaulted_token: Optional[str] = Field(
        default=None,
        description="Vaulted payment token ID",
        json_schema_extra={"ui_label": "Vaulted Token"}
    )
    security_code: Optional[str] = Field(
        default=None,
        description="CVV for token payment (if required)",
        json_schema_extra={"ui_label": "Security Code", "ui_sensitive": True}
    )


class PaymentMethodDetail(BaseModel):
    """Payment method details container."""
    card: Optional[CardDetail] = Field(
        default=None,
        description="Card payment details",
        json_schema_extra={"ui_label": "Card Details", "ui_group": "payment_method"}
    )
    token: Optional[TokenDetail] = Field(
        default=None,
        description="Token payment details",
        json_schema_extra={"ui_label": "Token Details", "ui_group": "payment_method"}
    )


class PaymentMethod(BaseModel):
    """Payment method information."""
    type: str = Field(
        ...,
        description="Payment method type (CARD, BANK_TRANSFER, PIX, etc.)",
        json_schema_extra={
            "ui_label": "Payment Type",
            "ui_options": [e.value for e in PaymentMethodType],
            "ui_required": True
        }
    )
    detail: Optional[PaymentMethodDetail] = Field(
        default=None,
        description="Payment method specific details",
        json_schema_extra={"ui_label": "Payment Details", "ui_group": "payment_method"}
    )
    vaulted_token: Optional[str] = Field(
        default=None,
        description="Previously vaulted payment token",
        json_schema_extra={"ui_label": "Vaulted Token ID"}
    )


# =============================================================================
# Nested Models - Additional Data
# =============================================================================

class OrderItem(BaseModel):
    """Individual item in an order."""
    id: Optional[str] = Field(
        default=None,
        description="Item identifier",
        json_schema_extra={"ui_label": "Item ID"}
    )
    name: Optional[str] = Field(
        default=None,
        description="Item name",
        json_schema_extra={"ui_label": "Item Name"}
    )
    quantity: Optional[int] = Field(
        default=1,
        ge=1,
        description="Item quantity",
        json_schema_extra={"ui_label": "Quantity"}
    )
    unit_amount: Optional[float] = Field(
        default=None,
        description="Unit price of the item",
        json_schema_extra={"ui_label": "Unit Price"}
    )
    category: Optional[str] = Field(
        default=None,
        description="Item category",
        json_schema_extra={
            "ui_label": "Category",
            "ui_options": [e.value for e in ItemCategory]
        }
    )
    sku_code: Optional[str] = Field(
        default=None,
        description="Stock keeping unit code",
        json_schema_extra={"ui_label": "SKU Code"}
    )
    description: Optional[str] = Field(
        default=None,
        description="Item description",
        json_schema_extra={"ui_label": "Description"}
    )


class OrderData(BaseModel):
    """Order information for additional context."""
    items: Optional[List[OrderItem]] = Field(
        default=None,
        description="List of items in the order",
        json_schema_extra={"ui_label": "Order Items", "ui_group": "additional_data"}
    )
    sales_channel: Optional[str] = Field(
        default=None,
        description="Sales channel identifier",
        json_schema_extra={"ui_label": "Sales Channel"}
    )


class AdditionalData(BaseModel):
    """Additional data for provider-specific requirements."""
    order: Optional[OrderData] = Field(
        default=None,
        description="Order details",
        json_schema_extra={"ui_label": "Order Data", "ui_group": "additional_data"}
    )
    airline: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Airline-specific data",
        json_schema_extra={"ui_label": "Airline Data"}
    )
    lodging: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Lodging/hotel-specific data",
        json_schema_extra={"ui_label": "Lodging Data"}
    )


# =============================================================================
# Nested Models - Other
# =============================================================================

class Amount(BaseModel):
    """Payment amount details."""
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Currency code (ISO 4217, e.g., BRL, USD, MXN)",
        json_schema_extra={
            "ui_label": "Currency",
            "ui_placeholder": "BRL",
            "ui_required": True,
            "ui_options": ["BRL", "USD", "MXN", "COP", "CLP", "PEN", "ARS", "EUR"]
        }
    )
    value: float = Field(
        ...,
        gt=0,
        description="Payment amount value",
        json_schema_extra={"ui_label": "Amount", "ui_placeholder": "100.00", "ui_required": True}
    )


class MetadataItem(BaseModel):
    """Key-value metadata pair."""
    key: str = Field(
        ...,
        description="Metadata key",
        json_schema_extra={"ui_label": "Key"}
    )
    value: str = Field(
        ...,
        description="Metadata value",
        json_schema_extra={"ui_label": "Value"}
    )


class Checkout(BaseModel):
    """Checkout configuration."""
    sdk_action_type: Optional[str] = Field(
        default=None,
        description="SDK action type for checkout",
        json_schema_extra={"ui_label": "SDK Action Type"}
    )
    url_logo: Optional[str] = Field(
        default=None,
        description="Logo URL for checkout page",
        json_schema_extra={"ui_label": "Logo URL"}
    )
    url_background: Optional[str] = Field(
        default=None,
        description="Background image URL for checkout page",
        json_schema_extra={"ui_label": "Background URL"}
    )


class FraudScreening(BaseModel):
    """Fraud screening configuration."""
    enabled: Optional[bool] = Field(
        default=None,
        description="Whether fraud screening is enabled",
        json_schema_extra={"ui_label": "Enable Fraud Screening"}
    )
    provider: Optional[str] = Field(
        default=None,
        description="Fraud screening provider",
        json_schema_extra={"ui_label": "Provider"}
    )


class Subscription(BaseModel):
    """Subscription details for recurring payments."""
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription identifier",
        json_schema_extra={"ui_label": "Subscription ID"}
    )


# =============================================================================
# Main Request Model
# =============================================================================

class CreatePaymentRequest(BaseModel):
    """
    Complete Create Payment API request.
    
    Based on Yuno API: https://docs.y.uno/reference/create-payment
    
    Required fields:
    - account_id: Merchant account identifier
    - description: Payment description
    - country: Country code (ISO 3166-1)
    - merchant_order_id: Merchant's order reference
    - amount: Payment amount with currency
    - payment_method: Payment method details
    """
    
    # Required fields
    account_id: str = Field(
        ...,
        min_length=1,
        description="The unique identifier of the merchant account",
        json_schema_extra={"ui_label": "Account ID", "ui_required": True, "ui_group": "required"}
    )
    description: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="The description of the payment",
        json_schema_extra={
            "ui_label": "Description",
            "ui_placeholder": "Payment for Order #123",
            "ui_required": True,
            "ui_group": "required"
        }
    )
    country: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Country where the transaction must be processed (ISO 3166-1)",
        json_schema_extra={
            "ui_label": "Country",
            "ui_placeholder": "BR",
            "ui_required": True,
            "ui_group": "required",
            "ui_options": ["BR", "MX", "CO", "CL", "PE", "AR", "US"]
        }
    )
    merchant_order_id: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="The unique identifier of the customer's order",
        json_schema_extra={
            "ui_label": "Merchant Order ID",
            "ui_placeholder": "order_12345",
            "ui_required": True,
            "ui_group": "required"
        }
    )
    amount: Amount = Field(
        ...,
        description="Payment amount details",
        json_schema_extra={"ui_label": "Amount", "ui_required": True, "ui_group": "required"}
    )
    payment_method: PaymentMethod = Field(
        ...,
        description="Payment method information",
        json_schema_extra={"ui_label": "Payment Method", "ui_required": True, "ui_group": "payment_method"}
    )
    
    # Optional fields
    merchant_reference: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=255,
        description="Additional merchant reference to complement merchant_order_id",
        json_schema_extra={"ui_label": "Merchant Reference", "ui_group": "optional"}
    )
    workflow: Optional[str] = Field(
        default="DIRECT",
        description="The payment workflow",
        json_schema_extra={
            "ui_label": "Workflow",
            "ui_group": "optional",
            "ui_options": [e.value for e in WorkflowType]
        }
    )
    callback_url: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=526,
        description="URL to redirect customer after payment (required for DIRECT with redirection)",
        json_schema_extra={"ui_label": "Callback URL", "ui_placeholder": "https://mystore.com/callback", "ui_group": "optional"}
    )
    customer_payer: Optional[CustomerPayer] = Field(
        default=None,
        description="Customer/payer information",
        json_schema_extra={"ui_label": "Customer Payer", "ui_group": "customer_payer"}
    )
    additional_data: Optional[AdditionalData] = Field(
        default=None,
        description="Additional data for provider-specific requirements",
        json_schema_extra={"ui_label": "Additional Data", "ui_group": "additional_data"}
    )
    checkout: Optional[Checkout] = Field(
        default=None,
        description="Checkout configuration",
        json_schema_extra={"ui_label": "Checkout", "ui_group": "checkout"}
    )
    fraud_screening: Optional[FraudScreening] = Field(
        default=None,
        description="Fraud screening configuration",
        json_schema_extra={"ui_label": "Fraud Screening", "ui_group": "fraud"}
    )
    subscription: Optional[Subscription] = Field(
        default=None,
        description="Subscription details for recurring payments",
        json_schema_extra={"ui_label": "Subscription", "ui_group": "subscription"}
    )
    metadata: Optional[List[MetadataItem]] = Field(
        default=None,
        max_length=120,
        description="Custom key-value tags (up to 120 items)",
        json_schema_extra={"ui_label": "Metadata", "ui_group": "metadata"}
    )

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "account_id": "acc_12345",
                "description": "Test Payment",
                "country": "BR",
                "merchant_order_id": "order_001",
                "amount": {
                    "currency": "BRL",
                    "value": 100.00
                },
                "payment_method": {
                    "type": "CARD",
                    "detail": {
                        "card": {
                            "capture": True,
                            "installments": 1,
                            "card_data": {
                                "number": "4111111111111111",
                                "expiration_month": 12,
                                "expiration_year": 27,
                                "security_code": "123",
                                "holder_name": "JOHN DOE"
                            }
                        }
                    }
                },
                "workflow": "DIRECT"
            }
        }
