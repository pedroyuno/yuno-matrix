# Plan: Interactive Input for Create Payment API

## Overview

Replace static `input_data` in test case JSON files with three input methods:
1. **Interactive Input** (CURRENT FOCUS): UI form with all API parameters selectable
2. Paste JSON: Raw JSON payload input
3. Datadog Query: Retrieve payment requests from logs

---

## Current Status: Phase 1 Complete, Phases 2 & 3 Mostly Complete

### Goal
Create a UI that allows users to select which API parameters to send and input their values, based on the Yuno Create Payment API specification.

---

## Phase 1: Interactive Input Implementation ✅

### Step 1.1: Create API Schema Definition ✅
- [x] Create `/src/schemas/create_payment.py` with Pydantic models matching the Create Payment API
- [x] Define all required and optional fields with their types, constraints, and defaults
- [x] Include nested objects: `amount`, `customer_payer`, `payment_method`, `billing_address`, etc.

**Key fields from Yuno Create Payment API:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `account_id` | string | Yes | Unique account identifier |
| `description` | string | Yes | Payment description (3-255 chars) |
| `country` | string | Yes | ISO 3166-1 country code (2 chars) |
| `merchant_order_id` | string | Yes | Customer order ID (3-255 chars) |
| `amount.currency` | string | Yes | ISO 4217 currency (3 chars) |
| `amount.value` | number | Yes | Payment amount |
| `payment_method.type` | string | Yes | CARD, BANK_TRANSFER, etc. |
| `workflow` | enum | No | SDK_CHECKOUT, CHECKOUT, REDIRECT, DIRECT, SDK_SEAMLESS |
| `customer_payer` | object | No | Payer information |
| `additional_data` | object | No | Provider-specific data |
| `callback_url` | string | No | Redirect URL after payment |
| `metadata` | array | No | Custom key-value tags |

**Nested Objects:**
- `amount`: { currency, value }
- `customer_payer`: { id, email, first_name, last_name, document, billing_address, phone, ... }
- `payment_method`: { type, detail.card, detail.token, ... }
- `payment_method.detail.card`: { number, expiration_month, expiration_year, security_code, holder_name, ... }

### Step 1.2: Create Schema Metadata Generator ✅
- [x] Create `/src/schemas/schema_utils.py` to generate UI-friendly metadata from Pydantic models
- [x] Include field labels, types, validation rules, nested structure, enum options
- [x] Support marking fields as "commonly used" vs "advanced"

### Step 1.3: Create Interactive Form API Endpoints ✅
- [x] `GET /api/payment-schema` - Return the complete schema for the form builder
- [x] Include field definitions, nesting, validation rules, and groupings
- [x] Support field filtering by type/category

### Step 1.4: Build Interactive Form UI ✅
- [x] Create collapsible sections for object groups (Amount, Customer, Payment Method, etc.)
- [x] Add checkbox to enable/disable each field
- [x] Dynamic field inputs based on type (text, number, select for enums)
- [x] Show required vs optional fields clearly
- [x] Add validation feedback in real-time
- [x] Support nested object expansion/collapse

**UI Components Needed:**
```
┌─────────────────────────────────────────────────────────────┐
│ Create Payment Request Builder                              │
├─────────────────────────────────────────────────────────────┤
│ ▼ Required Fields                                           │
│   ☑ account_id     [________________________]               │
│   ☑ description    [________________________]               │
│   ☑ country        [BR ▼]                                   │
│   ☑ merchant_order_id [______________________]              │
│                                                             │
│ ▼ Amount (required)                                         │
│   ☑ currency       [BRL ▼]                                  │
│   ☑ value          [12.00______]                            │
│                                                             │
│ ▼ Payment Method (required)                                 │
│   ☑ type           [CARD ▼]                                 │
│   ▼ Card Details                                            │
│     ☐ verify       [ ]                                      │
│     ☑ installments [1__]                                    │
│     ☑ capture      [x]                                      │
│     ▼ Card Data                                             │
│       ☑ number     [4444585001234562]                       │
│       ☑ expiration_month [12]                               │
│       ☑ expiration_year  [27]                               │
│       ☑ security_code    [123]                              │
│       ☑ holder_name      [Test User]                        │
│                                                             │
│ ▶ Customer Payer (optional)                                 │
│ ▶ Additional Data (optional)                                │
│ ▶ Metadata (optional)                                       │
│                                                             │
│ [Preview JSON]  [Use This Payload]                          │
└─────────────────────────────────────────────────────────────┘
```

### Step 1.5: Integrate Form with Test Case Creation ✅
- [x] Allow building `input_data` via the interactive form
- [x] Store the constructed payload in test case step (via sessionStorage)
- [x] Support editing existing input_data through the form
- [x] Add "Preview JSON" button to see final payload

### Step 1.6: Add Presets/Templates ✅
- [x] Create common payment templates (Brazil Card, PIX, Mexico, Colombia, Installments, Minimal)
- [ ] Allow saving custom presets
- [x] Quick-fill from template

---

## Phase 2: JSON Paste Input 🔄 (Mostly Complete)
- [x] Add "Paste JSON" tab alongside interactive form
- [ ] JSON editor with syntax highlighting (currently plain textarea with monospace font)
- [x] Validate pasted JSON against schema (via `parseJsonInput()` calling `/api/validate-payment`)
- [x] Format JSON button for pretty-printing pasted input
- [ ] Parse and populate interactive form from pasted JSON (pasted JSON updates preview but does NOT populate the interactive form fields)

---

## Phase 3: Datadog Query Integration 🔄 (Mostly Complete)
- [x] Query Datadog logs for payment requests (via `/api/datadog/query` endpoint with `DatadogClient`)
- [x] Parse and import as test case input_data ("Use This Payload" saves to sessionStorage)
- [x] "Query Datadog" tab in builder with trace ID input and status check
- [x] `/api/datadog/status` endpoint to check if API keys are configured
- [x] Filter by date range (date_from, date_to)
- [ ] Filter by merchant
- [ ] Filter by payment status

---

## Files to Create/Modify

### New Files
- `/src/schemas/__init__.py`
- `/src/schemas/create_payment.py` - Pydantic models for Create Payment API
- `/src/schemas/schema_utils.py` - Schema-to-UI metadata generator

### Modified Files
- `/web.py` - Add new routes and form UI
- `/local_safrapay_test.json` - Remove `input_data` (deferred until UI ready)

---

## API Schema Reference

The Yuno Create Payment API schema (from https://docs.y.uno/reference/create-payment):

### Request Body Schema (POST /payments)

```json
{
  "type": "object",
  "required": ["account_id", "description", "country", "merchant_order_id", "amount", "payment_method"],
  "properties": {
    "account_id": { "type": "string" },
    "description": { "type": "string", "minLength": 3, "maxLength": 255 },
    "country": { "type": "string", "minLength": 2, "maxLength": 2 },
    "merchant_order_id": { "type": "string", "minLength": 3, "maxLength": 255 },
    "merchant_reference": { "type": "string", "minLength": 3, "maxLength": 255 },
    "workflow": { 
      "type": "string", 
      "enum": ["SDK_CHECKOUT", "CHECKOUT", "REDIRECT", "DIRECT", "SDK_SEAMLESS"],
      "default": "SDK_CHECKOUT"
    },
    "callback_url": { "type": "string", "minLength": 3, "maxLength": 526 },
    "amount": {
      "type": "object",
      "required": ["currency", "value"],
      "properties": {
        "currency": { "type": "string", "minLength": 3, "maxLength": 3 },
        "value": { "type": "number", "format": "float" }
      }
    },
    "customer_payer": {
      "type": "object",
      "properties": {
        "id": { "type": "string" },
        "email": { "type": "string", "format": "email" },
        "first_name": { "type": "string" },
        "last_name": { "type": "string" },
        "document": {
          "type": "object",
          "properties": {
            "document_type": { "type": "string" },
            "document_number": { "type": "string" }
          }
        },
        "billing_address": {
          "type": "object",
          "properties": {
            "address_line_1": { "type": "string" },
            "address_line_2": { "type": "string" },
            "city": { "type": "string" },
            "state": { "type": "string" },
            "zip_code": { "type": "string" },
            "country": { "type": "string" },
            "neighborhood": { "type": "string" }
          }
        },
        "phone": {
          "type": "object",
          "properties": {
            "country_code": { "type": "string" },
            "number": { "type": "string" }
          }
        }
      }
    },
    "payment_method": {
      "type": "object",
      "required": ["type"],
      "properties": {
        "type": { 
          "type": "string",
          "enum": ["CARD", "BANK_TRANSFER", "CASH", "BNPL", "WALLET", "VOUCHER"]
        },
        "detail": {
          "type": "object",
          "properties": {
            "card": {
              "type": "object",
              "properties": {
                "verify": { "type": "boolean" },
                "installments": { "type": "integer" },
                "capture": { "type": "boolean" },
                "card_data": {
                  "type": "object",
                  "properties": {
                    "number": { "type": "string" },
                    "expiration_month": { "type": "integer" },
                    "expiration_year": { "type": "integer" },
                    "security_code": { "type": "string" },
                    "holder_name": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "additional_data": { "type": "object" },
    "metadata": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "key": { "type": "string" },
          "value": { "type": "string" }
        }
      }
    }
  }
}
```

---

## Progress Tracking

| Step | Description | Status |
|------|-------------|--------|
| 1.1 | Create API Schema Definition | ✅ Complete |
| 1.2 | Create Schema Metadata Generator | ✅ Complete |
| 1.3 | Create Interactive Form API Endpoints | ✅ Complete |
| 1.4 | Build Interactive Form UI | ✅ Complete |
| 1.5 | Integrate Form with Test Case Creation | ✅ Complete |
| 1.6 | Add Presets/Templates | ✅ Complete (custom preset saving still pending) |
| 2.0 | JSON Paste Input | 🔄 Mostly Complete (syntax highlighting + form population pending) |
| 3.0 | Datadog Query Integration | 🔄 Mostly Complete (merchant/status filters pending) |

**Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Complete

## Phase 1 Complete!

All interactive input features have been implemented:

**Files Created:**
- `/src/schemas/__init__.py` - Schema module exports
- `/src/schemas/create_payment.py` - Pydantic models for Create Payment API
- `/src/schemas/schema_utils.py` - Schema-to-UI metadata generator
- `/src/schemas/presets.py` - Payment presets/templates
- `/src/datadog_client.py` - Datadog API client for log queries

**Files Modified:**
- `/web.py` - Added Payment Builder page, API endpoints, and integration

**Features Implemented:**
1. Interactive form with collapsible field groups
2. Checkbox-based field selection
3. Real-time JSON preview
4. Schema validation
5. Presets for common payment scenarios (Brazil Card, PIX, Mexico, Colombia, Installments, Minimal)
6. Integration with main test runner page
7. "Use This Payload" to save for test creation
8. "Quick Test from Builder" button on main page
9. "Paste JSON" tab with validation and formatting
10. "Query Datadog" tab with trace ID lookup, date filtering, and status check

**How to Access:**
- Start the server: `python web.py`
- Main page: http://localhost:5001/
- Payment Builder: http://localhost:5001/builder

**API Endpoints:**
- `GET /api/payment-schema` - Returns schema for form generation
- `GET /api/presets` - Returns available payment presets
- `POST /api/validate-payment` - Validates a payment payload
- `POST /api/datadog/query` - Query Datadog logs by trace_id
- `GET /api/datadog/status` - Check if Datadog API is configured

## Remaining Work

The following items are still pending across phases:

### Phase 1 Remaining
- [ ] Allow saving custom presets (Step 1.6)

### Phase 2 Remaining
- [ ] JSON editor with syntax highlighting (currently plain textarea)
- [ ] Parse pasted JSON and populate the interactive form fields (currently only updates preview)

### Phase 3 Remaining
- [ ] Filter Datadog queries by merchant
- [ ] Filter Datadog queries by payment status

---

## Notes

- Start with card payments for Brazil (BRL) as the primary use case
- The form should work for both creating new test cases and editing existing ones
- Keep backward compatibility with JSON files that have inline `input_data`
- Consider mobile-responsive design for the form

---

*Last Updated: 2026-02-06*
