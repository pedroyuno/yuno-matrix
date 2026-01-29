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
```

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

- `authorize` - Payment authorization
- `capture` - Capture authorized payment
- `purchase` - Direct purchase (auth + capture)
- `refund` - Refund a transaction
- `void` - Void a transaction
- `verify` - Verification operation
- `tokenize` - Card tokenization

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
│   ├── api_client.py      # API client (placeholder mode)
│   ├── logger.py          # Certification logger
│   └── executor.py        # Test execution orchestrator
├── tests/                 # Unit and integration tests
├── examples/              # Example test case files
├── logs/                  # Execution logs (gitignored)
├── config/                # Configuration files
├── main.py               # CLI entry point
└── README.md
```

## Placeholder Mode

Currently running in **placeholder mode** with mock API responses. This allows testing the framework without actual API integration.

To implement real API calls:
1. Update `src/api_client.py` with actual HTTP requests
2. Add authentication/authorization logic
3. Set `placeholder_mode: false` in config
4. Configure provider base URLs

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
