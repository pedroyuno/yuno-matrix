"""
Scoping document CSV parser for MATRIX.

Parses implementation scoping documents that define which features/operations
each provider + payment method combination supports.
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field


class ScopingParseError(Exception):
    """Exception raised when scoping document parsing fails."""
    pass


@dataclass
class OperationSupport:
    """Support status for a specific operation."""
    supported: bool
    status: str  # e.g., "Implemented", "Not Applicable", "Not Supported"
    additional_info: Optional[str] = None


@dataclass
class ProviderIntegration:
    """Represents a provider + payment method integration."""
    integration_id: str  # e.g., "REDE_CARD"
    provider: str  # e.g., "REDE"
    payment_method: str  # e.g., "CARD", "PIX", "BOLETO"
    country: str = "BR"
    
    # Operation support
    operations: Dict[str, OperationSupport] = field(default_factory=dict)
    
    # Additional attributes from the scoping document
    attributes: Dict[str, OperationSupport] = field(default_factory=dict)
    
    def supports_operation(self, operation: str) -> bool:
        """Check if this integration supports a given operation."""
        op = self.operations.get(operation.lower())
        return op is not None and op.supported
    
    def get_supported_operations(self) -> List[str]:
        """Get list of supported operations."""
        return [op for op, support in self.operations.items() if support.supported]
    
    def is_implemented(self, operation: str) -> bool:
        """Check if an operation is implemented (not just supported)."""
        op = self.operations.get(operation.lower())
        return op is not None and op.supported and op.status.lower() == "implemented"


@dataclass
class ScopingDocument:
    """Represents a parsed scoping document."""
    integrations: List[ProviderIntegration] = field(default_factory=list)
    
    def get_integration(self, integration_id: str) -> Optional[ProviderIntegration]:
        """Get integration by ID."""
        for integration in self.integrations:
            if integration.integration_id == integration_id:
                return integration
        return None
    
    def get_integrations_by_provider(self, provider: str) -> List[ProviderIntegration]:
        """Get all integrations for a given provider."""
        return [i for i in self.integrations if i.provider.upper() == provider.upper()]
    
    def get_integrations_by_payment_method(self, payment_method: str) -> List[ProviderIntegration]:
        """Get all integrations for a given payment method."""
        return [i for i in self.integrations if i.payment_method.upper() == payment_method.upper()]


class ScopingParser:
    """Parser for scoping document CSV files."""
    
    # Known operations to look for in the scoping document
    KNOWN_OPERATIONS = {
        'verify', 'authorize', 'capture', 'purchase', 'refund', 'cancel',
        'partial_capture', 'partial_refund', 'multiple_captures', 'multiple_refunds',
        'checkout', 'redirect', 'external_refunds', 'tokenize'
    }
    
    # Known attributes (non-operation features)
    KNOWN_ATTRIBUTES = {
        'country', 'signed_contract_with_provider', 'already_integrated_with_yuno',
        'experience', 'card_type_accepted', 'installments', 'chargebacks',
        'network_tokens', 'recurring_payments', 'market_segment', 'processing_model',
        '3ds', 'split_payments', 'submerchants', 'soft_descriptor',
        'customizable_expiration_time_for_apms', 'applepay', 'googlepay', 
        'clicktopay', 'expected_go_live_by_the_merchant', 'additional_requirements',
        'conciliations'
    }
    
    @staticmethod
    def load_from_file(file_path: Union[str, Path]) -> ScopingDocument:
        """
        Load and parse a scoping document CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            ScopingDocument object
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ScopingParseError: If file cannot be parsed
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Scoping document not found: {file_path}")
        
        if not path.is_file():
            raise ScopingParseError(f"Path is not a file: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
        except IOError as e:
            raise ScopingParseError(f"Error reading file {file_path}: {str(e)}")
        
        return ScopingParser.parse_rows(rows)
    
    @staticmethod
    def load_from_string(csv_string: str) -> ScopingDocument:
        """
        Parse a CSV string into a ScopingDocument.
        
        Args:
            csv_string: CSV content as string
            
        Returns:
            ScopingDocument object
        """
        import io
        reader = csv.reader(io.StringIO(csv_string))
        rows = list(reader)
        return ScopingParser.parse_rows(rows)
    
    @staticmethod
    def parse_rows(rows: List[List[str]]) -> ScopingDocument:
        """
        Parse CSV rows into a ScopingDocument.
        
        Expected format:
        - Row 0: Feature/Integration identifiers (e.g., REDE_CARD, SAFRAPAY_CARD)
        - Row 1: Provider names (e.g., REDE, SAFRAPAY)
        - Row 2: Payment methods (e.g., CARD, PIX, BOLETO)
        - Row 3: Column headers (INFORMATION, STATUS, ADDITIONAL INFO)
        - Row 4+: Feature data
        """
        if len(rows) < 5:
            raise ScopingParseError("Scoping document must have at least 5 rows")
        
        # Parse header rows to identify integrations
        feature_row = rows[0]
        provider_row = rows[1]
        payment_method_row = rows[2]
        header_row = rows[3]
        
        # Find integration columns (groups of 3: INFORMATION, STATUS, ADDITIONAL INFO)
        integrations_map: Dict[int, ProviderIntegration] = {}
        
        # Skip the first two columns (usually empty or contain "Feature" label)
        col_idx = 2
        
        while col_idx < len(feature_row):
            integration_id = feature_row[col_idx].strip() if col_idx < len(feature_row) else ""
            
            if not integration_id or integration_id.upper() in ('INFORMATION', 'STATUS', 'ADDITIONAL INFO'):
                col_idx += 1
                continue
            
            provider = provider_row[col_idx].strip() if col_idx < len(provider_row) else ""
            payment_method = payment_method_row[col_idx].strip() if col_idx < len(payment_method_row) else ""
            
            if integration_id and provider:
                integration = ProviderIntegration(
                    integration_id=integration_id,
                    provider=provider,
                    payment_method=payment_method
                )
                integrations_map[col_idx] = integration
            
            # Each integration spans 3 columns
            col_idx += 3
        
        # Parse feature rows
        for row_idx in range(4, len(rows)):
            row = rows[row_idx]
            if len(row) < 2:
                continue
            
            # Feature name is in column 1 (index 1)
            feature_name = row[1].strip() if len(row) > 1 else ""
            if not feature_name:
                continue
            
            # Normalize feature name for matching
            normalized_feature = ScopingParser._normalize_feature_name(feature_name)
            
            # Parse values for each integration
            for start_col, integration in integrations_map.items():
                # Get INFORMATION, STATUS, ADDITIONAL INFO columns
                info_col = start_col
                status_col = start_col + 1
                additional_col = start_col + 2
                
                info_value = row[info_col].strip() if info_col < len(row) else ""
                status_value = row[status_col].strip() if status_col < len(row) else ""
                additional_value = row[additional_col].strip() if additional_col < len(row) else ""
                
                # Determine if this is an operation or attribute
                is_operation = normalized_feature in ScopingParser.KNOWN_OPERATIONS
                
                # Parse the support status
                supported = ScopingParser._parse_boolean(info_value)
                
                support = OperationSupport(
                    supported=supported,
                    status=status_value,
                    additional_info=additional_value if additional_value else None
                )
                
                if is_operation:
                    integration.operations[normalized_feature] = support
                else:
                    integration.attributes[normalized_feature] = support
                    
                    # Special handling for country
                    if normalized_feature == 'country' and info_value:
                        integration.country = ScopingParser._extract_country(info_value)
        
        return ScopingDocument(integrations=list(integrations_map.values()))
    
    @staticmethod
    def _normalize_feature_name(name: str) -> str:
        """Normalize feature name for consistent matching."""
        # Convert to lowercase, replace spaces with underscores
        normalized = name.lower().strip()
        normalized = normalized.replace(' ', '_')
        normalized = normalized.replace('-', '_')
        # Remove special characters
        normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
        return normalized
    
    @staticmethod
    def _parse_boolean(value: str) -> bool:
        """Parse a boolean value from the scoping document."""
        if not value:
            return False
        
        value_lower = value.lower().strip()
        
        # TRUE/FALSE values
        if value_lower in ('true', 'yes', '1'):
            return True
        if value_lower in ('false', 'no', '0'):
            return False
        
        # Check for "Yes, using..." type values
        if value_lower.startswith('yes'):
            return True
        
        # If it's not a clear boolean, check if it has meaningful content
        # that indicates support
        if value_lower and value_lower not in ('no', 'false', 'n/a', 'not applicable'):
            return True
        
        return False
    
    @staticmethod
    def _extract_country(value: str) -> str:
        """Extract country code from a value."""
        # Common country mappings
        country_map = {
            'brazil': 'BR',
            'brasil': 'BR',
            'mexico': 'MX',
            'méxico': 'MX',
            'colombia': 'CO',
            'argentina': 'AR',
            'chile': 'CL',
            'peru': 'PE',
            'perú': 'PE',
        }
        
        value_lower = value.lower().strip()
        
        # Check for direct country name
        for country_name, code in country_map.items():
            if country_name in value_lower:
                return code
        
        # Return the original value if no mapping found
        # (might already be a country code)
        return value.strip()[:2].upper() if value.strip() else 'BR'
