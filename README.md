# MATRIX

**M**erchant **A**PI **T**est & **R**egression **I**ntegration e**X**erciser

Automated testing system for merchant API operations with comprehensive logging for certification proof.

## Features

- ✅ **CSV scoping document input** - Generate test cases from implementation scoping documents
- ✅ Automatic test case generation based on provider capabilities
- ✅ Variable passing between test steps using JSONPath
- ✅ Support for multiple payment operations (authorize, capture, purchase, refund, etc.)
- ✅ Comprehensive logging for certification proof
- ✅ Sensitive data masking (card numbers, API keys)
- ✅ Colored console output
- ✅ Web interface for test execution
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

MATRIX uses **CSV scoping documents** as input. These documents define which features and operations each provider/payment method combination supports, and MATRIX automatically generates appropriate test cases.

```bash
# Run with scoping document CSV
python main.py --scoping examples/sample_scoping_document.csv

# With generation options
python main.py --scoping scoping.csv --only-implemented --merchant-id my_merchant

# Filter specific operations
python main.py --scoping scoping.csv --operations authorize capture refund

# Custom environment and log directory
python main.py --scoping scoping.csv --environment sandbox --log-dir ./my_logs
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--scoping` | Path to scoping document CSV file | (required) |
| `--config` | Path to config file | `config/config.json` |
| `--log-dir` | Directory for log files | `logs` |
| `--merchant-id` | Merchant ID for generated tests | `matrix_test` |
| `--environment` | Environment (sandbox/production) | `sandbox` |
| `--suite-name` | Custom test suite name | Auto-generated |
| `--only-implemented` | Only test implemented operations | `false` |
| `--operations` | Specific operations to test | All supported |

### Scoping Document Format (CSV)

The scoping document CSV defines provider integrations and their supported operations. The format follows the implementation scoping document structure:

```csv
,Feature,PROVIDER_PAYMENT,,,ANOTHER_PROVIDER,,,
,Provider,PROVIDER_NAME,,,ANOTHER_NAME,,,
,Payment_Method,CARD,,,PIX,,,
,,INFORMATION,STATUS,ADDITIONAL INFO,INFORMATION,STATUS,ADDITIONAL INFO
,Country,Brazil,Supported,,Brazil,Supported,
,Authorize,TRUE,Implemented,,FALSE,Not Applicable,
,Capture,TRUE,Implemented,,FALSE,Not Applicable,
,Purchase,FALSE,Not Applicable,,TRUE,Implemented,
,Refund,TRUE,Implemented,,TRUE,Implemented,
```

**Key rows:**
- **Row 1**: Integration identifiers (e.g., `REDE_CARD`, `PAGBANK_PIX`)
- **Row 2**: Provider names (e.g., `REDE`, `PAGBANK`)
- **Row 3**: Payment methods (`CARD`, `PIX`, `BOLETO`)
- **Row 4**: Column headers (INFORMATION, STATUS, ADDITIONAL INFO for each integration)
- **Row 5+**: Feature rows

**Key columns per integration (3 columns each):**
- **INFORMATION**: Feature value (TRUE/FALSE, country name, etc.)
- **STATUS**: Implementation status (Implemented, Not Applicable, Not Implemented)
- **ADDITIONAL INFO**: Optional notes

**Supported operations:**
- `Verify`, `Authorize`, `Capture`, `Purchase`, `Refund`, `Cancel`
- `Partial_Capture`, `Partial_Refund`, `Multiple_Captures`, `Multiple_Refunds`

See [examples/sample_scoping_document.csv](examples/sample_scoping_document.csv) for a complete example.

### Generated Test Flows

Based on the scoping document, MATRIX generates appropriate test flows:

**For CARD payment methods:**
- `authorize_capture` - Authorize followed by capture
- `authorize_cancel` - Authorize followed by cancel/void
- `authorize_capture_refund` - Full payment lifecycle

**For PIX/BOLETO payment methods:**
- `purchase` - Direct purchase
- `purchase_refund` - Purchase followed by refund

### Web Interface

MATRIX provides a web interface for uploading scoping documents and executing tests:

```bash
# Start the web interface
python web.py

# Access at http://localhost:5000
```

**Web interface features:**
- Upload CSV scoping documents
- Configure generation options (merchant ID, environment, implemented-only filter)
- Select specific test cases to run
- Real-time execution progress with streaming results
- View detailed request/response logs
- Download execution reports

## Development

### Running Tests

```bash
# Run all tests with coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_scoping_parser.py -v

# Run with markers
pytest -m unit -v
```

### Test Coverage

Target: **85% overall coverage**

Current module coverage:
- models.py: 93%
- scoping_parser.py: 96%
- test_generator.py: 92%
- context.py: 97%
- logger.py: 94%
- api_client.py: 100%

### Project Structure

```
yuno-matrix/
├── src/
│   ├── models.py          # Pydantic data models
│   ├── scoping_parser.py  # CSV scoping document parser
│   ├── test_generator.py  # Test case generator from scoping docs
│   ├── context.py         # Variable context manager
│   ├── api_client.py      # API client (Yuno API + placeholder mode)
│   ├── logger.py          # Certification logger
│   └── executor.py        # Test execution orchestrator
├── tests/                 # Unit and integration tests
├── examples/              # Example scoping documents
│   └── sample_scoping_document.csv
├── logs/                  # Execution logs (gitignored)
├── config/
│   └── config.json        # Configuration with Yuno settings
├── .env.example          # Template for API credentials
├── .env                  # Your credentials (DO NOT COMMIT)
├── main.py               # CLI entry point
├── web.py                # Web interface
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
