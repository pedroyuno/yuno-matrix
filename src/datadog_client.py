"""
Datadog client for MATRIX.

Queries Datadog logs to retrieve payment request payloads by trace_id.
"""

import os
import sys
import json
import re
import requests
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv


def log(msg: str):
    """Print and flush immediately for real-time logging."""
    print(msg)
    sys.stdout.flush()

# Load environment variables
load_dotenv()


class DatadogClient:
    """
    Client for querying Datadog logs API.
    
    Retrieves payment request payloads from Datadog logs using trace_id.
    """
    
    DATADOG_API_URL = "https://api.datadoghq.com/api/v2/logs/events/search"
    
    def __init__(self, skip_dotenv: bool = False):
        """
        Initialize Datadog client with API credentials from environment.
        
        Args:
            skip_dotenv: If True, don't reload .env (for testing)
        """
        # Reload .env to ensure latest values (skip in tests)
        if not skip_dotenv:
            load_dotenv(override=True)
        
        self.api_key = os.getenv("DD_API_KEY", "")
        self.app_key = os.getenv("DD_APP_KEY", "")
        
        # Debug: show credential status (masked)
        if self.api_key:
            log(f"[Datadog] API Key loaded: {self.api_key[:8]}...{self.api_key[-4:]} ({len(self.api_key)} chars)")
        else:
            log("[Datadog] API Key: NOT FOUND")
            
        if self.app_key:
            log(f"[Datadog] App Key loaded: {self.app_key[:8]}...{self.app_key[-4:]} ({len(self.app_key)} chars)")
        else:
            log("[Datadog] App Key: NOT FOUND")
        
        if not self.api_key or not self.app_key:
            raise ValueError(
                "Datadog API credentials not configured. "
                "Please set DD_API_KEY and DD_APP_KEY environment variables."
            )
    
    def search_by_trace_id(
        self,
        trace_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search Datadog logs by trace_id and extract payment request payload.
        
        Args:
            trace_id: The trace ID to search for (UUID format)
            date_from: Start date in ISO 8601 format (e.g., "2026-01-23T00:00:00Z")
                      Defaults to 7 days ago
            date_to: End date in ISO 8601 format (e.g., "2026-01-23T23:59:59Z")
                    Defaults to now
        
        Returns:
            Dict containing:
                - success: bool
                - payload: The extracted payment request payload (if found)
                - logs_count: Number of logs found
                - error: Error message (if any)
        """
        # Validate trace_id format (UUID)
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, trace_id.lower()):
            return {
                "success": False,
                "payload": None,
                "logs_count": 0,
                "error": f"Invalid trace_id format. Expected UUID, got: {trace_id}"
            }
        
        # Set default date range (last 7 days)
        if not date_to:
            date_to = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        if not date_from:
            date_from = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Build the query
        # Note: @trace_id is the attribute syntax in Datadog (@ prefix for log attributes)
        query_body = {
            "filter": {
                "query": f"@trace_id:{trace_id} service:public-api",
                "from": date_from,
                "to": date_to
            },
            "page": {
                "limit": 1000
            },
            "sort": "timestamp"
        }
        
        headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key,
            "Content-Type": "application/json"
        }
        
        # Debug: log the request details
        log(f"[Datadog] Querying: {self.DATADOG_API_URL}")
        log(f"[Datadog] Query: {query_body['filter']['query']}")
        log(f"[Datadog] Date range: {date_from} to {date_to}")
        
        try:
            response = requests.post(
                self.DATADOG_API_URL,
                headers=headers,
                json=query_body,
                timeout=30
            )
            
            log(f"[Datadog] Response status: {response.status_code}")
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "payload": None,
                    "logs_count": 0,
                    "error": f"Datadog API error: {response.status_code} - {response.text}"
                }
            
            data = response.json()
            log(f"[Datadog] Response keys: {list(data.keys())}")
            
            logs = data.get("data", [])
            log(f"[Datadog] Number of logs in response: {len(logs)}")
            
            if not logs:
                log(f"[Datadog] No logs found in response!")
                log(f"[Datadog] Full response: {json.dumps(data, indent=2)[:2000]}")
                return {
                    "success": False,
                    "payload": None,
                    "logs_count": 0,
                    "error": f"No logs found for trace_id: {trace_id}",
                    "raw_logs": []
                }
            
            # Debug: Print raw logs structure
            log(f"\n[Datadog] ========== FOUND {len(logs)} LOGS ==========")
            for i, log_entry in enumerate(logs[:5]):  # Print first 5 logs
                log(f"\n[Datadog] === Log {i+1} ===")
                attrs = log_entry.get("attributes", {})
                log(f"[Datadog] Keys in attributes: {list(attrs.keys())}")
                
                # Print message if exists
                if "message" in attrs:
                    msg = attrs["message"]
                    log(f"[Datadog] Message (first 500 chars): {str(msg)[:500]}")
                
                # Print any http-related attributes
                if "http" in attrs:
                    log(f"[Datadog] HTTP attrs: {json.dumps(attrs['http'], indent=2)[:1000]}")
                
                # Print full attributes structure for first log
                if i == 0:
                    log(f"[Datadog] Full attributes (first log): {json.dumps(attrs, indent=2)[:2000]}")
            
            # Extract payment payload from logs
            log(f"[Datadog] Attempting to extract payment payload...")
            payload, error = self._extract_payment_payload(logs)
            
            if payload:
                log(f"[Datadog] SUCCESS: Found payment payload!")
            else:
                log(f"[Datadog] FAILED to extract payload: {error}")
            
            if payload:
                return {
                    "success": True,
                    "payload": payload,
                    "logs_count": len(logs),
                    "error": None,
                    "raw_logs": None  # Don't include raw logs on success
                }
            else:
                # Include raw logs for debugging when extraction fails
                return {
                    "success": False,
                    "payload": None,
                    "logs_count": len(logs),
                    "error": error or "Could not extract payment payload from logs",
                    "raw_logs": logs[:10]  # Return first 10 logs for debugging
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "payload": None,
                "logs_count": 0,
                "error": "Datadog API request timed out"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "payload": None,
                "logs_count": 0,
                "error": f"Datadog API request failed: {str(e)}"
            }
    
    def _extract_payment_payload(
        self,
        logs: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Extract payment request payload from Datadog log entries.
        
        Searches through logs for the payment request JSON payload.
        Prefers logs from the /v1/payments public API endpoint.
        
        Args:
            logs: List of Datadog log entries
        
        Returns:
            Tuple of (payload dict or None, error message or None)
        """
        # First pass: look for /v1/payments endpoint logs (preferred)
        # Second pass: accept any valid payment payload
        for prefer_public_api in [True, False]:
            for log_entry in logs:
                try:
                    result = self._try_extract_from_log(log_entry, prefer_public_api)
                    if result:
                        return result, None
                except Exception as e:
                    log(f"[Datadog] Error processing log entry: {e}")
                    continue
        
        return None, "No payment payload found in log entries"
    
    def _try_extract_from_log(
        self,
        log_entry: Dict[str, Any],
        prefer_public_api: bool
    ) -> Optional[Dict[str, Any]]:
        """
        Try to extract payment payload from a single log entry.
        
        Args:
            log_entry: Single Datadog log entry
            prefer_public_api: If True, only match /v1/payments endpoint logs
        
        Returns:
            Payment payload dict or None
        """
        attributes = log_entry.get("attributes", {})
        
        # 1. Check the nested path: attributes.attributes.attributes.request.body
        # This is the structure used by Yuno's public-api logs
        nested_attrs = attributes.get("attributes", {})
        if nested_attrs:
            deeper_attrs = nested_attrs.get("attributes", {})
            if deeper_attrs:
                request_data = deeper_attrs.get("request", {})
                if isinstance(request_data, dict):
                    url = request_data.get("url", "")
                    
                    # If preferring public API, skip non-matching URLs
                    if prefer_public_api and "/v1/payments" not in url:
                        return None
                    
                    # Check request.body (contains the actual payload as JSON string)
                    body = request_data.get("body")
                    if body:
                        payload = self._try_parse_json(body)
                        if payload and self._is_payment_payload(payload):
                            log(f"[Datadog] Found payload at attributes.attributes.attributes.request.body (url: {url})")
                            return payload
                    
                    # Also check if request itself is the payload
                    if self._is_payment_payload(request_data):
                        log(f"[Datadog] Found payload at attributes.attributes.attributes.request")
                        return request_data
                elif isinstance(request_data, str):
                    payload = self._try_parse_json(request_data)
                    if payload and self._is_payment_payload(payload):
                        if not prefer_public_api:
                            log(f"[Datadog] Found payload at attributes.attributes.attributes.request (string)")
                            return payload
        
        # Skip other paths if preferring public API (they don't have URL info)
        if prefer_public_api:
            return None
        
        # 2. Check common attribute paths where payload might be stored
        possible_paths = [
            attributes.get("http", {}).get("body"),
            attributes.get("http", {}).get("request_body"),
            attributes.get("request", {}).get("body"),
            attributes.get("request"),
            attributes.get("payload"),
            attributes.get("body"),
            nested_attrs.get("request", {}).get("body") if isinstance(nested_attrs.get("request"), dict) else None,
            nested_attrs.get("body"),
        ]
        
        for value in possible_paths:
            if value:
                payload = self._try_parse_json(value)
                if payload and self._is_payment_payload(payload):
                    log(f"[Datadog] Found payload in common path")
                    return payload
        
        # 3. Check the log message itself
        message = attributes.get("message", "")
        if message:
            payload = self._try_parse_json(message)
            if payload and self._is_payment_payload(payload):
                return payload
            
            # Try to extract JSON from within the message
            payload = self._extract_json_from_text(message)
            if payload and self._is_payment_payload(payload):
                return payload
        
        # 4. Check nested attributes for any JSON that looks like a payment
        for key, value in attributes.items():
            if isinstance(value, dict) and self._is_payment_payload(value):
                return value
            elif isinstance(value, str):
                parsed = self._try_parse_json(value)
                if parsed and self._is_payment_payload(parsed):
                    return parsed
        
        return None
    
    def _try_parse_json(self, value: Any) -> Optional[Dict[str, Any]]:
        """
        Try to parse a value as JSON.
        
        Args:
            value: Value to parse (string or dict)
        
        Returns:
            Parsed dict or None if parsing fails
        """
        if isinstance(value, dict):
            return value
        
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON object from a text string.
        
        Finds the first valid JSON object in the text.
        
        Args:
            text: Text that may contain JSON
        
        Returns:
            Extracted dict or None
        """
        # Find potential JSON start positions
        start_positions = [i for i, c in enumerate(text) if c == '{']
        
        for start in start_positions:
            # Try to find matching closing brace
            depth = 0
            for i, c in enumerate(text[start:], start):
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            json_str = text[start:i+1]
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict):
                                return parsed
                        except json.JSONDecodeError:
                            break
        
        return None
    
    def _is_payment_payload(self, data: Dict[str, Any]) -> bool:
        """
        Check if a dict looks like a Yuno payment request payload.
        
        Args:
            data: Dict to check
        
        Returns:
            True if it appears to be a payment payload
        """
        # Check for common payment payload fields
        payment_fields = [
            "amount",
            "payment_method",
            "country",
            "merchant_order_id",
            "customer_payer"
        ]
        
        # Require at least 2 payment-related fields
        matches = sum(1 for field in payment_fields if field in data)
        return matches >= 2


def get_datadog_client() -> Optional[DatadogClient]:
    """
    Factory function to get a DatadogClient instance.
    
    Returns:
        DatadogClient instance or None if not configured
    """
    try:
        return DatadogClient()
    except ValueError:
        return None
