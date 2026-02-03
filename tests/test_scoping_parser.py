"""
Unit tests for MATRIX scoping document parser.

Target coverage: 85%+
"""

import pytest
from pathlib import Path

from src.scoping_parser import (
    ScopingParser, ScopingParseError, 
    ScopingDocument, ProviderIntegration, OperationSupport
)


# ============================================================================
# Load From File Tests
# ============================================================================

@pytest.mark.unit
def test_load_valid_scoping_file():
    """Test loading a valid scoping document CSV file."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    assert isinstance(scoping_doc, ScopingDocument)
    assert len(scoping_doc.integrations) == 3


@pytest.mark.unit
def test_load_nonexistent_file():
    """Test loading non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError) as exc_info:
        ScopingParser.load_from_file("nonexistent_file.csv")
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.unit
def test_load_directory_path(tmp_path):
    """Test loading a directory path raises error."""
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()
    
    with pytest.raises(ScopingParseError) as exc_info:
        ScopingParser.load_from_file(dir_path)
    assert "not a file" in str(exc_info.value).lower()


@pytest.mark.unit
def test_load_insufficient_rows(tmp_path):
    """Test loading file with insufficient rows."""
    invalid_file = tmp_path / "short.csv"
    invalid_file.write_text("row1\nrow2\nrow3\n", encoding="utf-8")
    
    with pytest.raises(ScopingParseError) as exc_info:
        ScopingParser.load_from_file(invalid_file)
    assert "at least 5 rows" in str(exc_info.value).lower()


# ============================================================================
# Parse Integration Tests
# ============================================================================

@pytest.mark.unit
def test_parse_integration_identifiers():
    """Test parsing extracts correct integration identifiers."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    integration_ids = [i.integration_id for i in scoping_doc.integrations]
    assert "REDE_CARD" in integration_ids
    assert "SAFRAPAY_CARD" in integration_ids
    assert "PAGBANK_PIX" in integration_ids


@pytest.mark.unit
def test_parse_provider_names():
    """Test parsing extracts correct provider names."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    rede = scoping_doc.get_integration("REDE_CARD")
    assert rede is not None
    assert rede.provider == "REDE"
    
    safrapay = scoping_doc.get_integration("SAFRAPAY_CARD")
    assert safrapay is not None
    assert safrapay.provider == "SAFRAPAY"


@pytest.mark.unit
def test_parse_payment_methods():
    """Test parsing extracts correct payment methods."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    rede = scoping_doc.get_integration("REDE_CARD")
    assert rede.payment_method == "CARD"
    
    pagbank = scoping_doc.get_integration("PAGBANK_PIX")
    assert pagbank.payment_method == "PIX"


# ============================================================================
# Operation Support Tests
# ============================================================================

@pytest.mark.unit
def test_parse_card_operations():
    """Test parsing card operation support correctly."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    rede = scoping_doc.get_integration("REDE_CARD")
    assert rede.supports_operation("authorize")
    assert rede.supports_operation("capture")
    assert rede.supports_operation("refund")
    assert rede.supports_operation("cancel")
    assert not rede.supports_operation("purchase")


@pytest.mark.unit
def test_parse_pix_operations():
    """Test parsing PIX operation support correctly."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    pagbank = scoping_doc.get_integration("PAGBANK_PIX")
    assert pagbank.supports_operation("purchase")
    assert pagbank.supports_operation("refund")
    assert not pagbank.supports_operation("authorize")
    assert not pagbank.supports_operation("capture")


@pytest.mark.unit
def test_get_supported_operations():
    """Test getting list of supported operations."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    rede = scoping_doc.get_integration("REDE_CARD")
    ops = rede.get_supported_operations()
    
    assert "authorize" in ops
    assert "capture" in ops
    assert "refund" in ops


@pytest.mark.unit
def test_is_implemented():
    """Test checking if operation is implemented."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    rede = scoping_doc.get_integration("REDE_CARD")
    assert rede.is_implemented("authorize")
    assert rede.is_implemented("capture")
    
    safrapay = scoping_doc.get_integration("SAFRAPAY_CARD")
    # Cancel is supported but not implemented for SAFRAPAY
    assert safrapay.supports_operation("cancel")
    assert not safrapay.is_implemented("cancel")


# ============================================================================
# ScopingDocument Query Tests
# ============================================================================

@pytest.mark.unit
def test_get_integration_by_id():
    """Test getting integration by ID."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    integration = scoping_doc.get_integration("REDE_CARD")
    assert integration is not None
    assert integration.integration_id == "REDE_CARD"
    
    # Non-existent integration
    assert scoping_doc.get_integration("NONEXISTENT") is None


@pytest.mark.unit
def test_get_integrations_by_provider():
    """Test getting integrations by provider."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    rede_integrations = scoping_doc.get_integrations_by_provider("REDE")
    assert len(rede_integrations) == 1
    assert rede_integrations[0].integration_id == "REDE_CARD"


@pytest.mark.unit
def test_get_integrations_by_payment_method():
    """Test getting integrations by payment method."""
    test_file = Path("tests/fixtures/sample_scoping.csv")
    scoping_doc = ScopingParser.load_from_file(test_file)
    
    card_integrations = scoping_doc.get_integrations_by_payment_method("CARD")
    assert len(card_integrations) == 2
    
    pix_integrations = scoping_doc.get_integrations_by_payment_method("PIX")
    assert len(pix_integrations) == 1


# ============================================================================
# Load From String Tests
# ============================================================================

@pytest.mark.unit
def test_load_from_string():
    """Test parsing from CSV string."""
    csv_content = """,Feature,TEST_CARD,,,
,Provider,TESTPROV,,,
,Payment_Method,CARD,,,
,,INFORMATION,STATUS,ADDITIONAL INFO
,Country,Brazil,Supported,
,Authorize,TRUE,Implemented,
,Capture,TRUE,Implemented,
,Purchase,FALSE,Not Applicable,
,Refund,TRUE,Implemented,
"""
    
    scoping_doc = ScopingParser.load_from_string(csv_content)
    
    assert len(scoping_doc.integrations) == 1
    integration = scoping_doc.integrations[0]
    assert integration.integration_id == "TEST_CARD"
    assert integration.provider == "TESTPROV"
    assert integration.supports_operation("authorize")


# ============================================================================
# Helper Method Tests
# ============================================================================

@pytest.mark.unit
def test_normalize_feature_name():
    """Test feature name normalization."""
    assert ScopingParser._normalize_feature_name("Partial Capture") == "partial_capture"
    assert ScopingParser._normalize_feature_name("Card Type Accepted") == "card_type_accepted"
    assert ScopingParser._normalize_feature_name("3DS") == "3ds"


@pytest.mark.unit
def test_parse_boolean():
    """Test boolean parsing from various string formats."""
    assert ScopingParser._parse_boolean("TRUE") is True
    assert ScopingParser._parse_boolean("true") is True
    assert ScopingParser._parse_boolean("Yes") is True
    assert ScopingParser._parse_boolean("Yes, using Yuno's API") is True
    assert ScopingParser._parse_boolean("FALSE") is False
    assert ScopingParser._parse_boolean("false") is False
    assert ScopingParser._parse_boolean("No") is False
    assert ScopingParser._parse_boolean("") is False


@pytest.mark.unit
def test_extract_country():
    """Test country extraction from values."""
    assert ScopingParser._extract_country("Brazil") == "BR"
    assert ScopingParser._extract_country("Mexico") == "MX"
    assert ScopingParser._extract_country("Colombia") == "CO"
    assert ScopingParser._extract_country("BR") == "BR"
