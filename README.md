# MATRIX

**M**erchant **A**PI **T**est & **R**egression **I**ntegration e**X**erciser

Automated testing system for merchant API operations with comprehensive logging for certification proof.

## Features

- ✅ JSON-based test case definitions
- ✅ Variable passing between test steps using JSONPath
- ✅ Support for multiple payment operations (authorize, capture, purchase, refund, etc.)
- ✅ Comprehensive logging for certification proof
- ✅ Sensitive data masking (card numbers, API keys)
- ✅ Colored console output
- ✅ 90%+ test coverage on core modules

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development/testing
pip install -r requirements-dev.txt

# Set up Yuno API credentials
cp .env.example .env
# Edit .env and add your Yuno API keys
```

## Yuno API Configuration

### Setting Up Credentials

MATRIX integrates with the Yuno Payment API. To use real API calls:

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your credentials:**
   ```bash
   YUNO_PUBLIC_API_KEY=your_public_api_key_here
   YUNO_PRIVATE_SECRET_KEY=your_private_secret_key_here
   YUNO_ACCOUNT_ID=your_account_id_here
   YUNO_ENVIRONMENT=sandbox  # or "production"
   ```

3. **Set placeholder mode to false in config:**
   ```json
   {
     "placeholder_mode": false
   }
   ```

### Getting Yuno Credentials

Get your API keys from the [Yuno Dashboard](https://dashboard.y.uno):
- Navigate to Settings → API Keys
- Copy your Public API Key and Private Secret Key
- Find your Account ID in Account Settings

### Security Notes

- ⚠️ **NEVER** commit `.env` file to version control
- The `.env` file is already in `.gitignore`
- Use `.env.example` as a template for other team members
- Rotate credentials regularly
- Use sandbox credentials for testing

## Usage

### Running Tests

```bash
# Run with example test case
python main.py --testcase examples/sample_testcase.json

# Specify custom config
python main.py --testcase tests.json --config config/custom_config.json

# Custom log directory
python main.py --testcase tests.json --log-dir ./my_logs
```

### Test Case File Format

Test cases are defined in JSON format:

```json
{
  "version": "1.0",
  "metadata": {
    "test_suite_name": "Merchant Certification Tests",
    "merchant_id": "merchant_123",
    "environment": "sandbox",
    "created_at": "2026-01-29T10:00:00Z"
  },
  "test_cases": [
    {
      "id": "tc_001",
      "name": "Authorize and Capture Flow",
      "description": "Test authorization followed by capture",
      "steps": [
        {
          "step_id": 1,
          "operation": "authorize",
          "provider": "provider_a",
          "description": "Authorize payment",
          "input_data": {
            "amount": 100.00,
            "currency": "USD"
          },
          "capture_variables": {
            "transaction_id": "$.body.transaction_id"
          }
        },
        {
          "step_id": 2,
          "operation": "capture",
          "provider": "provider_a",
          "description": "Capture authorized payment",
          "input_data": {
            "transaction_id": "{{transaction_id}}",
            "amount": 100.00
          }
        }
      ]
    }
  ]
}
```

### Variable Substitution

- Use `{{variable_name}}` syntax to reference variables from previous steps
- Use JSONPath expressions to extract values from responses
- Example: `"transaction_id": "$.body.transaction_id"`

### Supported Operations

- `payment` - Yuno payment API call (recommended for Yuno integration)
- `authorize` - Payment authorization (Yuno: creates payment with capture=false)
- `capture` - Capture authorized payment (Yuno: POST /payments/{id}/capture)
- `purchase` - Direct purchase (auth + capture) (Yuno: creates payment with capture=true)
- `refund` - Refund a transaction (Yuno: POST /payments/{id}/refund)
- `void` - Void a transaction (Yuno: POST /payments/{id}/void)
- `verify` - Verification operation (placeholder only)
- `tokenize` - Card tokenization (placeholder only)

### Yuno Payment Example

See [examples/yuno_payment_testcase.json](examples/yuno_payment_testcase.json) for complete Yuno payment examples.

**Basic Yuno Payment:**
```json
{
  "step_id": 1,
  "operation": "payment",
  "provider": "safrapay",
  "description": "Create Yuno payment",
  "input_data": {
    "description": "Test Payment",
    "merchant_order_id": "order_123",
    "country": "BR",
    "amount": {
      "currency": "BRL",
      "value": 100
    },
    "customer_payer": {
      "email": "customer@example.com",
      "first_name": "John",
      "last_name": "Doe"
    },
    "payment_method": {
      "type": "CARD",
      "detail": {
        "card": {
          "capture": true,
          "installments": 1,
          "card_data": {
            "number": "4444585001234562",
            "expiration_month": 12,
            "expiration_year": 27,
            "security_code": "123",
            "holder_name": "John Doe"
          }
        }
      }
    }
  },
  "capture_variables": {
    "payment_id": "$.body.id",
    "transaction_id": "$.body.transaction_id"
  }
}
```

## Development

### Running Tests

```bash
# Run all tests with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_models.py -v

# Run with markers
pytest -m unit -v
```

### Test Coverage

Target: **85% overall coverage**

Current module coverage:
- models.py: 99%
- parser.py: 92%
- context.py: 97%
- logger.py: 94%
- api_client.py: 100%

### Project Structure

```
yuno-matrix/
├── src/
│   ├── models.py          # Pydantic data models
│   ├── parser.py          # JSON test case parser
│   ├── context.py         # Variable context manager
│   ├── api_client.py      # API client (Yuno API + placeholder mode)
│   ├── logger.py          # Certification logger
│   └── executor.py        # Test execution orchestrator
├── tests/                 # Unit and integration tests
├── examples/              # Example test case files
│   ├── sample_testcase.json       # Generic examples
│   └── yuno_payment_testcase.json # Yuno-specific examples
├── logs/                  # Execution logs (gitignored)
├── config/
│   └── config.json        # Configuration with Yuno settings
├── .env.example          # Template for API credentials
├── .env                  # Your credentials (DO NOT COMMIT)
├── main.py               # CLI entry point
└── README.md
```

## Operating Modes

MATRIX supports two operating modes:

### 1. Yuno API Mode (Real API Calls)

When properly configured with credentials, MATRIX makes real HTTP calls to the Yuno Payment API:

**Setup:**
```bash
# Configure credentials in .env
cp .env.example .env
# Edit .env with your Yuno API keys
```

```json
// Set in config/config.json
{
  "placeholder_mode": false
}
```

**Features:**
- ✅ Real HTTP requests to Yuno API
- ✅ Automatic authentication with API keys
- ✅ Idempotency key generation
- ✅ Full request/response logging
- ✅ Support for all Yuno payment operations
- ✅ Sandbox and production environments

### 2. Placeholder Mode (Mock Responses)

When credentials are not available or `placeholder_mode: true` is set, MATRIX uses mock responses:

**Features:**
- ✅ No API credentials required
- ✅ Realistic mock responses with generated IDs
- ✅ Fast execution for framework testing
- ✅ Same logging and variable passing as real mode

**Automatic Fallback:**
If `placeholder_mode: false` but credentials are missing, MATRIX automatically falls back to placeholder mode with a warning.

**Use Cases:**
- Framework development and testing
- CI/CD pipeline testing without API dependencies
- Demonstrating MATRIX capabilities without live accounts

## Logs

All test executions generate structured JSON logs in the `logs/` directory:

- Filename: `execution_YYYYMMDD_HHMMSS.json`
- Contains: All requests, responses, timestamps, and results
- Sensitive data: Automatically masked
- Use for: Certification proof, debugging, audit trails

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed
- `130` - Interrupted by user (Ctrl+C)

## License

Proprietary - Internal use only

## Support

For issues or questions, contact the development team.
