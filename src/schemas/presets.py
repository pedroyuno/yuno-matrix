"""
Payment request presets/templates for common scenarios.

These presets provide pre-filled payment data for common testing scenarios,
making it easier to quickly set up and run tests.
"""

from typing import Any, Dict, List


def get_presets() -> List[Dict[str, Any]]:
    """Return all available payment presets."""
    return [
        brazil_card_payment(),
        brazil_pix_payment(),
        mexico_card_payment(),
        colombia_card_payment(),
        installments_payment(),
        minimal_card_payment(),
    ]


def brazil_card_payment() -> Dict[str, Any]:
    """Brazil card payment with full customer data."""
    return {
        "id": "brazil_card",
        "name": "Brazil Card Payment",
        "description": "Complete card payment in Brazil with customer data",
        "country": "BR",
        "category": "card",
        "payload": {
            "account_id": "",  # User must fill
            "description": "Brazil Card Payment Test",
            "country": "BR",
            "merchant_order_id": "order_br_" + "001",
            "amount": {
                "currency": "BRL",
                "value": 100.00
            },
            "workflow": "DIRECT",
            "customer_payer": {
                "email": "customer@example.com",
                "first_name": "João",
                "last_name": "Silva",
                "document": {
                    "document_type": "CPF",
                    "document_number": "47033278802"
                },
                "billing_address": {
                    "address_line_1": "Rua Exemplo, 123",
                    "city": "São Paulo",
                    "state": "SP",
                    "zip_code": "01234-567",
                    "country": "BR",
                    "neighborhood": "Centro"
                },
                "phone": {
                    "country_code": "55",
                    "number": "11987654321"
                }
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
                            "holder_name": "JOAO SILVA"
                        }
                    }
                }
            }
        }
    }


def brazil_pix_payment() -> Dict[str, Any]:
    """Brazil PIX payment."""
    return {
        "id": "brazil_pix",
        "name": "Brazil PIX Payment",
        "description": "PIX instant payment in Brazil",
        "country": "BR",
        "category": "pix",
        "payload": {
            "account_id": "",
            "description": "Brazil PIX Payment Test",
            "country": "BR",
            "merchant_order_id": "order_pix_001",
            "amount": {
                "currency": "BRL",
                "value": 50.00
            },
            "workflow": "DIRECT",
            "customer_payer": {
                "email": "customer@example.com",
                "first_name": "Maria",
                "last_name": "Santos",
                "document": {
                    "document_type": "CPF",
                    "document_number": "12345678909"
                }
            },
            "payment_method": {
                "type": "PIX"
            }
        }
    }


def mexico_card_payment() -> Dict[str, Any]:
    """Mexico card payment."""
    return {
        "id": "mexico_card",
        "name": "Mexico Card Payment",
        "description": "Card payment in Mexico with customer data",
        "country": "MX",
        "category": "card",
        "payload": {
            "account_id": "",
            "description": "Mexico Card Payment Test",
            "country": "MX",
            "merchant_order_id": "order_mx_001",
            "amount": {
                "currency": "MXN",
                "value": 500.00
            },
            "workflow": "DIRECT",
            "customer_payer": {
                "email": "cliente@ejemplo.com",
                "first_name": "Carlos",
                "last_name": "González",
                "document": {
                    "document_type": "CURP",
                    "document_number": "GOGC850101HDFRRL09"
                },
                "billing_address": {
                    "address_line_1": "Calle Reforma 123",
                    "city": "Ciudad de México",
                    "state": "CDMX",
                    "zip_code": "06600",
                    "country": "MX"
                },
                "phone": {
                    "country_code": "52",
                    "number": "5512345678"
                }
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
                            "holder_name": "CARLOS GONZALEZ"
                        }
                    }
                }
            }
        }
    }


def colombia_card_payment() -> Dict[str, Any]:
    """Colombia card payment."""
    return {
        "id": "colombia_card",
        "name": "Colombia Card Payment",
        "description": "Card payment in Colombia",
        "country": "CO",
        "category": "card",
        "payload": {
            "account_id": "",
            "description": "Colombia Card Payment Test",
            "country": "CO",
            "merchant_order_id": "order_co_001",
            "amount": {
                "currency": "COP",
                "value": 100000.00
            },
            "workflow": "DIRECT",
            "customer_payer": {
                "email": "cliente@ejemplo.com",
                "first_name": "Pedro",
                "last_name": "Rodríguez",
                "document": {
                    "document_type": "CC",
                    "document_number": "1234567890"
                },
                "billing_address": {
                    "address_line_1": "Carrera 7 # 123-45",
                    "city": "Bogotá",
                    "state": "Bogotá D.C.",
                    "zip_code": "110111",
                    "country": "CO"
                },
                "phone": {
                    "country_code": "57",
                    "number": "3101234567"
                }
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
                            "holder_name": "PEDRO RODRIGUEZ"
                        }
                    }
                }
            }
        }
    }


def installments_payment() -> Dict[str, Any]:
    """Card payment with installments (Brazil)."""
    return {
        "id": "installments",
        "name": "Installments Payment",
        "description": "Card payment with 6 installments in Brazil",
        "country": "BR",
        "category": "card",
        "payload": {
            "account_id": "",
            "description": "Installments Payment Test",
            "country": "BR",
            "merchant_order_id": "order_inst_001",
            "amount": {
                "currency": "BRL",
                "value": 600.00
            },
            "workflow": "DIRECT",
            "customer_payer": {
                "email": "customer@example.com",
                "first_name": "Ana",
                "last_name": "Oliveira",
                "document": {
                    "document_type": "CPF",
                    "document_number": "98765432100"
                },
                "billing_address": {
                    "address_line_1": "Av. Paulista, 1000",
                    "city": "São Paulo",
                    "state": "SP",
                    "zip_code": "01310-100",
                    "country": "BR"
                },
                "phone": {
                    "country_code": "55",
                    "number": "11912345678"
                }
            },
            "payment_method": {
                "type": "CARD",
                "detail": {
                    "card": {
                        "capture": True,
                        "installments": 6,
                        "card_data": {
                            "number": "4111111111111111",
                            "expiration_month": 12,
                            "expiration_year": 27,
                            "security_code": "123",
                            "holder_name": "ANA OLIVEIRA"
                        }
                    }
                }
            }
        }
    }


def minimal_card_payment() -> Dict[str, Any]:
    """Minimal card payment with only required fields."""
    return {
        "id": "minimal",
        "name": "Minimal Card Payment",
        "description": "Card payment with minimum required fields",
        "country": "BR",
        "category": "card",
        "payload": {
            "account_id": "",
            "description": "Minimal Payment Test",
            "country": "BR",
            "merchant_order_id": "order_min_001",
            "amount": {
                "currency": "BRL",
                "value": 10.00
            },
            "workflow": "DIRECT",
            "payment_method": {
                "type": "CARD",
                "detail": {
                    "card": {
                        "capture": True,
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
        }
    }
