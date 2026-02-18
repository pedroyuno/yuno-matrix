#!/usr/bin/env python3
"""MATRIX Web Interface - Simple web UI for test case execution."""

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify, send_file, Response

load_dotenv()

from src.scoping_parser import ScopingParser, ScopingParseError
from src.test_generator import TestCaseGenerator, GeneratorConfig
from src.api_client import APIClient
from src.logger import CertificationLogger
from src.context import ExecutionContext, ContextError
from src.models import Config, TestSuite, TestCase, Step, StepResult, TestCaseResult, APIRequest, ProviderTestCard
from src.schemas import CreatePaymentRequest, get_presets
from src.schemas.schema_utils import schema_to_json
from src.datadog_client import DatadogClient, get_datadog_client

app = Flask(__name__)

# Store uploaded test suites in memory (for simplicity)
uploaded_suites = {}

# Store provider test cards per suite (suite_id -> {provider_id: ProviderTestCard})
provider_test_cards_storage = {}

# Temporary storage for E2E SDK sessions (e2e_session_id -> session data)
e2e_sessions = {}

def load_config(config_path: str = "config/config.json") -> Config:
    """Load configuration from file."""
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return Config(**config_data)
    except FileNotFoundError:
        return Config()
    except Exception:
        return Config()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MATRIX - Test Runner</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f7fa;
            color: #333;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        h1 {
            font-size: 2.5rem;
            font-weight: 600;
            color: #1a1a2e;
            margin-bottom: 8px;
        }
        
        .subtitle {
            color: #666;
            font-size: 1rem;
        }
        
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            padding: 24px;
            margin-bottom: 24px;
        }
        
        .card h2 {
            font-size: 1.1rem;
            color: #1a1a2e;
            margin-bottom: 16px;
            font-weight: 600;
        }
        
        .upload-area {
            border: 2px dashed #d0d5dd;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .upload-area:hover {
            border-color: #4f46e5;
            background: #f8f9ff;
        }
        
        .upload-area.dragover {
            border-color: #4f46e5;
            background: #f0f0ff;
        }
        
        .upload-area input[type="file"] {
            display: none;
        }
        
        .upload-icon {
            font-size: 2rem;
            margin-bottom: 12px;
        }
        
        .upload-text {
            color: #666;
        }
        
        .upload-text strong {
            color: #4f46e5;
        }
        
        /* Hierarchy Styles */
        .hierarchy-group {
            margin-bottom: 8px;
        }
        
        .hierarchy-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 12px 16px;
            cursor: pointer;
            user-select: none;
            border-radius: 8px;
            transition: background 0.2s;
        }
        
        .hierarchy-header:hover {
            background: #f3f4f6;
        }
        
        .payment-method-header {
            background: #e0e7ff;
            font-weight: 600;
            font-size: 1.05rem;
        }
        
        .payment-method-header:hover {
            background: #c7d2fe;
        }
        
        .provider-header {
            background: #f3f4f6;
            margin-left: 24px;
            font-weight: 500;
        }
        
        .provider-header:hover {
            background: #e5e7eb;
        }
        
        .hierarchy-checkbox {
            flex-shrink: 0;
        }
        
        .hierarchy-checkbox input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: #4f46e5;
        }
        
        .hierarchy-expand-icon {
            font-size: 0.8rem;
            transition: transform 0.2s;
            color: #666;
        }
        
        .hierarchy-group.expanded > .hierarchy-header .hierarchy-expand-icon {
            transform: rotate(90deg);
        }
        
        .hierarchy-number {
            color: #666;
            font-weight: 500;
            min-width: 40px;
        }
        
        .hierarchy-name {
            flex: 1;
        }
        
        .hierarchy-count {
            color: #888;
            font-size: 0.85rem;
            font-weight: normal;
        }

        .e2e-sdk-btn {
            background: #7c3aed;
            color: white;
            border: none;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.72rem;
            font-weight: 600;
            cursor: pointer;
            margin-left: 8px;
            letter-spacing: 0.3px;
            transition: background 0.2s;
        }
        .e2e-sdk-btn:hover { background: #6d28d9; }
        .e2e-sdk-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .hierarchy-children {
            display: none;
            padding-left: 24px;
        }
        
        .hierarchy-group.expanded > .hierarchy-children {
            display: block;
        }
        
        .provider-group .hierarchy-children {
            padding-left: 16px;
        }
        
        .provider-group .test-case {
            margin-left: 24px;
        }
        
        .test-case-index {
            color: #888;
            font-size: 0.85rem;
            margin-right: 8px;
            min-width: 50px;
        }
        
        .test-case {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-bottom: 12px;
            transition: all 0.3s;
            overflow: hidden;
        }
        
        .test-case.running {
            border-color: #4f46e5;
            background: #f8f9ff;
        }
        
        .test-case.passed {
            border-color: #10b981;
            background: #ecfdf5;
        }
        
        .test-case.failed {
            border-color: #ef4444;
            background: #fef2f2;
        }
        
        .test-case.error {
            border-color: #f59e0b;
            background: #fef3c7;
        }
        
        .test-case-summary {
            padding: 16px;
            cursor: pointer;
            user-select: none;
            display: flex;
            gap: 12px;
            align-items: flex-start;
        }
        
        .test-case-summary:hover {
            background: rgba(0,0,0,0.02);
        }
        
        .test-case-checkbox {
            flex-shrink: 0;
            margin-top: 2px;
        }
        
        .test-case-checkbox input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: #4f46e5;
        }
        
        .test-case-content {
            flex: 1;
            min-width: 0;
        }
        
        .selection-controls {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 12px;
            padding: 8px 12px;
            background: #f9fafb;
            border-radius: 6px;
            font-size: 0.9rem;
        }
        
        .selection-controls label {
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            color: #4f46e5;
            font-weight: 500;
        }
        
        .selection-controls input[type="checkbox"] {
            width: 16px;
            height: 16px;
            cursor: pointer;
            accent-color: #4f46e5;
        }
        
        .selection-count {
            color: #666;
            margin-left: auto;
        }
        
        .test-case-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .test-case-name {
            font-weight: 600;
            color: #1a1a2e;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .test-case-id {
            font-size: 0.85rem;
            color: #888;
            font-family: monospace;
        }
        
        .test-case-desc {
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }
        
        .steps-info {
            font-size: 0.85rem;
            color: #888;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .expand-icon {
            transition: transform 0.2s;
            font-size: 0.75rem;
            color: #888;
        }
        
        .test-case.expanded .expand-icon {
            transform: rotate(90deg);
        }
        
        .test-case-duration {
            font-size: 0.85rem;
            color: #666;
            margin-left: auto;
            margin-right: 12px;
        }
        
        .status-icon {
            font-size: 1.1rem;
        }
        
        .test-case-details {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
            background: rgba(0,0,0,0.02);
            border-top: 1px solid rgba(0,0,0,0.05);
        }
        
        .test-case.expanded .test-case-details {
            max-height: 2000px;
        }
        
        .test-case-details-inner {
            padding: 16px;
        }
        
        .step-detail {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            margin-bottom: 12px;
            overflow: hidden;
        }
        
        .step-detail:last-child {
            margin-bottom: 0;
        }
        
        .step-detail-header {
            padding: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 500;
            background: #f9fafb;
            border-bottom: 1px solid #e5e7eb;
        }
        
        .step-number {
            background: #4f46e5;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        .step-detail.success .step-number { background: #059669; }
        .step-detail.failure .step-number { background: #dc2626; }
        .step-detail.error .step-number { background: #d97706; }
        
        .step-operation {
            background: #e5e7eb;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-family: monospace;
            color: #4f46e5;
        }
        
        .step-provider {
            font-size: 0.8rem;
            color: #888;
            margin-left: auto;
        }
        
        .step-detail-body {
            padding: 12px;
            font-size: 0.85rem;
        }
        
        .step-description {
            color: #666;
            margin-bottom: 12px;
        }
        
        .step-section {
            margin-bottom: 12px;
        }
        
        .step-section:last-child {
            margin-bottom: 0;
        }
        
        .step-section-label {
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }
        
        .step-data {
            background: #1a1a2e;
            color: #a5f3fc;
            padding: 10px 12px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 0.8rem;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .collapsible-section {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            overflow: hidden;
        }
        
        .collapsible-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 12px;
            background: #f9fafb;
            cursor: pointer;
            user-select: none;
            font-size: 0.8rem;
            font-weight: 500;
            color: #4f46e5;
        }
        
        .collapsible-header:hover {
            background: #f3f4f6;
        }
        
        .collapsible-header .collapse-icon {
            font-size: 0.7rem;
            transition: transform 0.2s;
        }
        
        .collapsible-section.open .collapse-icon {
            transform: rotate(90deg);
        }
        
        .collapsible-content {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }
        
        .collapsible-section.open .collapsible-content {
            max-height: 500px;
        }
        
        .collapsible-content .step-data {
            border-radius: 0;
            margin: 0;
        }
        
        .step-result-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        
        .step-result-badge.success {
            background: #d1fae5;
            color: #059669;
        }
        
        .step-result-badge.failure {
            background: #fee2e2;
            color: #dc2626;
        }
        
        .step-result-badge.error {
            background: #fef3c7;
            color: #d97706;
        }
        
        .step-error-msg {
            background: #fee2e2;
            color: #dc2626;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            margin-top: 8px;
        }
        
        .btn-glean-troubleshoot {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-top: 10px;
            padding: 8px 16px;
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 0.82rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            font-family: inherit;
        }
        
        .btn-glean-troubleshoot:hover {
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
        }
        
        .btn-glean-troubleshoot svg {
            width: 16px;
            height: 16px;
            fill: currentColor;
        }
        
        .capture-vars {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        
        .capture-var {
            background: #e0e7ff;
            color: #4338ca;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-family: monospace;
        }
        
        .capture-var.captured {
            background: #d1fae5;
            color: #059669;
            border: 1px solid #10b981;
        }
        
        .quick-info {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 8px;
            margin-bottom: 12px;
        }
        
        .quick-info-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.8rem;
        }
        
        .quick-info-label {
            color: #6b7280;
            min-width: 80px;
            font-weight: 500;
        }
        
        .quick-info-value {
            font-family: monospace;
            color: #1f2937;
            background: #f3f4f6;
            padding: 4px 8px;
            border-radius: 4px;
            word-break: break-all;
        }
        
        a.quick-info-link {
            color: #2563eb;
            text-decoration: none;
        }
        
        a.quick-info-link:hover {
            text-decoration: underline;
            color: #1d4ed8;
        }
        
        .copy-btn {
            background: none;
            border: 1px solid #d1d5db;
            border-radius: 4px;
            padding: 4px 8px;
            cursor: pointer;
            font-size: 0.7rem;
            color: #6b7280;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: all 0.15s ease;
        }
        
        .copy-btn:hover {
            background: #f3f4f6;
            border-color: #9ca3af;
            color: #374151;
        }
        
        .copy-btn.copied {
            background: #d1fae5;
            border-color: #10b981;
            color: #059669;
        }
        
        .response-status-row {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .response-status-badge {
            background: #1a1a2e;
            color: #a5f3fc;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
            font-family: monospace;
        }
        
        .response-substatus-badge {
            background: #fef3c7;
            color: #92400e;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 500;
            font-family: monospace;
        }
        
        .http-status-code {
            color: #888;
            font-size: 0.8rem;
            font-family: monospace;
        }
        
        .http-status-code.error {
            color: #dc2626;
            font-weight: 600;
        }
        
        .btn {
            display: inline-block;
            padding: 12px 24px;
            font-size: 1rem;
            font-weight: 500;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: #4f46e5;
            color: white;
        }
        
        .btn-primary:hover {
            background: #4338ca;
        }
        
        .btn-primary:disabled {
            background: #a5a3f3;
            cursor: not-allowed;
        }
        
        .btn-secondary {
            background: #e5e7eb;
            color: #333;
        }
        
        .btn-secondary:hover {
            background: #d1d5db;
        }
        
        .btn-success {
            background: #059669;
            color: white;
        }
        
        .btn-success:hover {
            background: #047857;
        }
        
        .actions {
            display: flex;
            gap: 12px;
            margin-top: 20px;
        }
        
        .step-list {
            margin-top: 12px;
            font-size: 0.9rem;
            padding-left: 8px;
            border-left: 2px solid #e5e7eb;
        }
        
        .step-item {
            padding: 6px 0 6px 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .step-success { color: #059669; }
        .step-failure { color: #dc2626; }
        .step-error { color: #d97706; }
        .step-pending { color: #888; }
        
        .summary-card {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 12px;
            text-align: center;
            margin-bottom: 24px;
        }
        
        @media (max-width: 768px) {
            .summary-card {
                grid-template-columns: repeat(3, 1fr);
            }
        }
        
        .summary-item {
            padding: 16px;
            background: #f9fafb;
            border-radius: 8px;
        }
        
        .summary-value {
            font-size: 2rem;
            font-weight: 600;
            color: #1a1a2e;
        }
        
        .summary-label {
            font-size: 0.85rem;
            color: #666;
            margin-top: 4px;
        }
        
        .summary-item.passed .summary-value { color: #059669; }
        .summary-item.failed .summary-value { color: #dc2626; }
        .summary-item.errors .summary-value { color: #d97706; }
        .summary-item.approved .summary-value { color: #0891b2; }
        .summary-item.declined .summary-value { color: #be185d; }
        
        .spinner-small {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #e5e7eb;
            border-top-color: #4f46e5;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .hidden {
            display: none !important;
        }
        
        .error-message {
            background: #fef2f2;
            border: 1px solid #fecaca;
            color: #dc2626;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 16px;
        }
        
        .metadata {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 16px;
            font-size: 0.9rem;
        }
        
        .metadata-item {
            background: #f9fafb;
            padding: 12px;
            border-radius: 6px;
        }
        
        .metadata-label {
            color: #666;
            font-size: 0.8rem;
            margin-bottom: 4px;
        }
        
        .metadata-value {
            color: #1a1a2e;
            font-weight: 500;
        }
        
        .execution-status {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 12px 16px;
            background: #f0f0ff;
            border-radius: 8px;
            margin-bottom: 16px;
            color: #4f46e5;
            font-weight: 500;
        }
        
        /* Inline Provider Card Input Styles */
        .provider-card-inputs {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
            margin: 12px 0 12px 40px;
            display: none;
        }
        
        .provider-card-inputs.visible {
            display: block;
        }
        
        .provider-card-inputs-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .provider-card-inputs-title::before {
            content: "💳";
        }
        
        .card-inputs-grid {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr 1.5fr;
            gap: 10px;
            align-items: end;
        }
        
        .card-input-field {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        
        .card-input-field label {
            font-size: 0.75rem;
            color: #64748b;
            font-weight: 500;
        }
        
        .card-input-field input {
            padding: 8px 10px;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            font-size: 0.85rem;
            background: white;
        }
        
        .card-input-field input:focus {
            outline: none;
            border-color: #4f46e5;
            box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.1);
        }
        
        .card-input-field input::placeholder {
            color: #94a3b8;
        }
        
        @media (max-width: 900px) {
            .card-inputs-grid {
                grid-template-columns: 1fr 1fr;
            }
            .card-inputs-grid .card-input-field:first-child {
                grid-column: 1 / -1;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>MATRIX</h1>
            <p class="subtitle">Merchant API Test & Regression Integration eXerciser</p>
        </header>
        
        <!-- Upload Section -->
        <div class="card" id="upload-section">
            <h2>Create or Load Test Case</h2>
            
            <!-- Quick Actions -->
            <div style="display: flex; gap: 12px; margin-bottom: 20px;">
                <a href="/builder" class="btn btn-primary" style="text-decoration: none; display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.2rem;">+</span> Build Payment Request
                </a>
                <button class="btn btn-secondary" id="quick-test-btn" onclick="createQuickTest()">
                    Quick Test from Builder
                </button>
            </div>
            
            <!-- Saved Payload Notice -->
            <div id="saved-payload-notice" class="hidden" style="background: #d1fae5; border: 1px solid #10b981; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #059669;">You have a saved payment payload. It will be used for all test cases.</span>
                <div style="display: flex; gap: 8px;">
                    <button onclick="viewBuilderPayload()" style="background: #059669; border: none; color: white; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">View/Edit</button>
                    <button onclick="clearBuilderPayload(); document.getElementById('saved-payload-notice').classList.add('hidden');" style="background: none; border: 1px solid #10b981; color: #059669; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">Clear</button>
                </div>
            </div>
            
            <div style="text-align: center; color: #888; margin: 16px 0;">— or —</div>
            
            <h3 style="font-size: 1rem; color: #666; margin-bottom: 12px;">Upload Scoping Document</h3>
            <div class="upload-area" id="upload-area">
                <input type="file" id="file-input" accept=".csv">
                <div class="upload-icon">📄</div>
                <p class="upload-text">
                    <strong>Click to upload</strong> or drag and drop<br>
                    <small>CSV scoping document</small>
                </p>
            </div>
            <div id="upload-error" class="error-message hidden"></div>
            
            <!-- CSV Options (shown when CSV is detected) -->
            <div id="csv-options" class="hidden" style="margin-top: 16px; padding: 16px; background: #f9fafb; border-radius: 8px;">
                <h4 style="font-size: 0.9rem; color: #666; margin-bottom: 12px;">Scoping Document Options</h4>
                <p id="csv-filename" style="font-size: 0.85rem; color: #4f46e5; margin-bottom: 12px;"></p>
                <div style="display: grid; gap: 12px;">
                    <label style="display: flex; align-items: center; gap: 8px;">
                        <input type="checkbox" id="only-implemented" checked>
                        <span>Only test implemented operations</span>
                    </label>
                    <div>
                        <label style="display: block; margin-bottom: 4px; font-size: 0.85rem; color: #666;">Merchant ID:</label>
                        <input type="text" id="merchant-id" value="matrix_test" style="width: 100%; padding: 8px; border: 1px solid #d0d5dd; border-radius: 6px;">
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 4px; font-size: 0.85rem; color: #666;">Environment:</label>
                        <select id="environment-select" style="width: 100%; padding: 8px; border: 1px solid #d0d5dd; border-radius: 6px;">
                            <option value="sandbox" selected>Sandbox</option>
                            <option value="production">Production</option>
                        </select>
                    </div>
                    <div style="display: flex; gap: 8px; margin-top: 8px;">
                        <button class="btn btn-primary" id="csv-upload-btn" style="flex: 1;">Generate Test Cases</button>
                        <button class="btn btn-secondary" id="csv-cancel-btn">Cancel</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Test Cases Section -->
        <div class="card hidden" id="testcases-section">
            <h2>Test Suite</h2>
            <div class="metadata" id="metadata"></div>
            <div id="payload-active-notice" class="hidden" style="background: #d1fae5; border: 1px solid #10b981; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #059669;">Using saved payment payload for all test cases.</span>
                <button onclick="clearBuilderPayload(); document.getElementById('payload-active-notice').classList.add('hidden');" style="background: none; border: 1px solid #10b981; color: #059669; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">Clear</button>
            </div>
            <div id="execution-status" class="execution-status hidden">
                <span class="spinner-small"></span>
                <span id="status-text">Running tests...</span>
            </div>
            <div id="summary" class="summary-card hidden"></div>
            <div id="selection-controls" class="selection-controls">
                <label>
                    <input type="checkbox" id="select-all" checked onchange="toggleSelectAll()">
                    Select All
                </label>
                <span class="selection-count" id="selection-count"></span>
            </div>
            <div id="testcases-list"></div>
            <div class="actions" id="actions">
                <button class="btn btn-primary" id="run-btn">Run Selected Tests</button>
                <button class="btn btn-secondary" id="clear-btn">Clear</button>
            </div>
            <div class="actions hidden" id="post-actions">
                <button class="btn btn-primary" id="download-btn">Download Logs</button>
                <button class="btn btn-secondary" id="run-again-btn">Run Again</button>
                <button class="btn btn-secondary" id="new-test-btn">New Test</button>
            </div>
        </div>
    </div>
    
    <script>
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');
        const uploadSection = document.getElementById('upload-section');
        const uploadError = document.getElementById('upload-error');
        const testcasesSection = document.getElementById('testcases-section');
        const testcasesList = document.getElementById('testcases-list');
        const metadataDiv = document.getElementById('metadata');
        const summaryDiv = document.getElementById('summary');
        const executionStatus = document.getElementById('execution-status');
        const statusText = document.getElementById('status-text');
        const actions = document.getElementById('actions');
        const postActions = document.getElementById('post-actions');
        
        let currentSuiteId = null;
        let currentSuite = null;
        let currentHierarchy = null;  // Hierarchical structure: Payment Method -> Provider -> Test Cases
        let currentExecutionId = null;
        let testResults = {};
        let summary = { total: 0, passed: 0, failed: 0, errors: 0, approved: 0, declined: 0 };
        let selectedTestCases = new Set();
        let providerTestCards = {};  // {providerId: {number, expiration_month, expiration_year, security_code, holder_name}}
        
        // Glean configuration (injected from backend)
        const GLEAN_DOMAIN = '{{ glean_domain }}';
        const GLEAN_AGENT_ID = '{{ glean_agent_id }}';
        
        // Find the payment method name for a given test case ID from the hierarchy
        function getPaymentMethodForTestCase(testCaseId) {
            if (!currentHierarchy) return '';
            for (const pm of currentHierarchy) {
                for (const provider of pm.providers) {
                    for (const tc of provider.test_cases) {
                        if (tc.id === testCaseId) return pm.name;
                    }
                }
            }
            return '';
        }
        
        // Find the provider name for a given test case ID and step from the hierarchy
        function getProviderForTestCase(testCaseId) {
            if (!currentHierarchy) return '';
            for (const pm of currentHierarchy) {
                for (const provider of pm.providers) {
                    for (const tc of provider.test_cases) {
                        if (tc.id === testCaseId) return provider.name;
                    }
                }
            }
            return '';
        }
        
        // Open Glean troubleshoot chat in a new tab
        function openGleanTroubleshoot(provider, paymentMethod, responseBody, paymentId, traceId) {
            if (!GLEAN_DOMAIN) {
                alert('Glean domain not configured. Please set GLEAN_DOMAIN in your .env file.');
                return;
            }
            
            const responseText = typeof responseBody === 'string' 
                ? responseBody 
                : JSON.stringify(responseBody, null, 2);
            
            let context = '';
            if (paymentId) context += `\nPayment ID: ${paymentId}`;
            if (traceId) context += `\nTrace ID: ${traceId}`;
            
            const initialMessage = `I am making a certification with the merchant and ${provider} ${paymentMethod} transactions fails with the following response:\n${responseText}${context}\nCan you please validate what can be missing and generate a recommendation for the merchant?\nPlease use Yuno internal documentation.`;
            
            const params = new URLSearchParams();
            params.set('domain', GLEAN_DOMAIN);
            params.set('mode', 'fullscreen');
            params.set('initialMessage', initialMessage);
            if (GLEAN_AGENT_ID) params.set('agentId', GLEAN_AGENT_ID);
            
            window.open('/glean-chat?' + params.toString(), '_blank');
        }
        
        // Convenience: troubleshoot a specific failed step by test case ID and step ID
        function troubleshootStep(testCaseId, stepId) {
            const result = testResults[testCaseId];
            const stepResult = result?.steps?.find(s => s.step_id === stepId);
            if (!stepResult?.response_body) {
                alert('No response data available for this step.');
                return;
            }
            
            const paymentMethod = getPaymentMethodForTestCase(testCaseId);
            const provider = getProviderForTestCase(testCaseId);
            const paymentId = stepResult.response_body?.payment?.id || stepResult.response_body?.id || '';
            const traceId = stepResult.response_headers?.['x-trace-id'] || '';
            openGleanTroubleshoot(provider, paymentMethod, stepResult.response_body, paymentId, traceId);
        }
        
        // Inline Provider Card Input Functions
        function renderProviderCardInputs(providerId, paymentMethodId) {
            const card = providerTestCards[providerId] || {};
            return `
                <div class="provider-card-inputs" id="card-inputs-${paymentMethodId}-${providerId}">
                    <div class="provider-card-inputs-title">Test Card for this Provider</div>
                    <div class="card-inputs-grid">
                        <div class="card-input-field">
                            <label>Card Number</label>
                            <input type="text" id="card-number-${providerId}" 
                                   value="${card.number || ''}" 
                                   placeholder="4111111111111111"
                                   onchange="updateProviderCard('${providerId}')">
                        </div>
                        <div class="card-input-field">
                            <label>Month</label>
                            <input type="number" id="card-exp-month-${providerId}" 
                                   value="${card.expiration_month || ''}" 
                                   placeholder="12" min="1" max="12"
                                   onchange="updateProviderCard('${providerId}')">
                        </div>
                        <div class="card-input-field">
                            <label>Year</label>
                            <input type="number" id="card-exp-year-${providerId}" 
                                   value="${card.expiration_year || ''}" 
                                   placeholder="27"
                                   onchange="updateProviderCard('${providerId}')">
                        </div>
                        <div class="card-input-field">
                            <label>CVV</label>
                            <input type="text" id="card-cvv-${providerId}" 
                                   value="${card.security_code || ''}" 
                                   placeholder="123" maxlength="4"
                                   onchange="updateProviderCard('${providerId}')">
                        </div>
                        <div class="card-input-field">
                            <label>Holder Name</label>
                            <input type="text" id="card-holder-${providerId}" 
                                   value="${card.holder_name || ''}" 
                                   placeholder="TEST USER"
                                   onchange="updateProviderCard('${providerId}')">
                        </div>
                    </div>
                </div>
            `;
        }
        
        function updateProviderCard(providerId) {
            const numberEl = document.getElementById(`card-number-${providerId}`);
            if (!numberEl) return;
            
            const number = numberEl.value.trim();
            if (number) {
                providerTestCards[providerId] = {
                    number: number,
                    expiration_month: parseInt(document.getElementById(`card-exp-month-${providerId}`)?.value) || 12,
                    expiration_year: parseInt(document.getElementById(`card-exp-year-${providerId}`)?.value) || 27,
                    security_code: document.getElementById(`card-cvv-${providerId}`)?.value.trim() || '123',
                    holder_name: document.getElementById(`card-holder-${providerId}`)?.value.trim() || 'TEST USER'
                };
            } else {
                delete providerTestCards[providerId];
            }
            
            // Save to sessionStorage
            sessionStorage.setItem('provider_test_cards', JSON.stringify(providerTestCards));
        }
        
        function showProviderCardInputs(paymentMethodId, providerId) {
            const inputsEl = document.getElementById(`card-inputs-${paymentMethodId}-${providerId}`);
            if (inputsEl) {
                inputsEl.classList.add('visible');
            }
        }
        
        function hideProviderCardInputs(paymentMethodId, providerId) {
            const inputsEl = document.getElementById(`card-inputs-${paymentMethodId}-${providerId}`);
            if (inputsEl) {
                inputsEl.classList.remove('visible');
            }
        }
        
        function updateCardInputsVisibility() {
            // Show/hide card inputs based on selected providers
            if (!currentHierarchy) return;
            
            currentHierarchy.forEach(pm => {
                if (pm.id.toUpperCase() === 'CARD') {
                    pm.providers.forEach(provider => {
                        const providerTestIds = provider.test_cases.map(tc => tc.id);
                        const isSelected = providerTestIds.some(id => selectedTestCases.has(id));
                        
                        if (isSelected) {
                            showProviderCardInputs(pm.id, provider.id);
                        } else {
                            hideProviderCardInputs(pm.id, provider.id);
                        }
                    });
                }
            });
        }
        
        // Load saved provider test cards on page load
        function loadSavedProviderCards() {
            const saved = sessionStorage.getItem('provider_test_cards');
            if (saved) {
                try {
                    providerTestCards = JSON.parse(saved);
                } catch (e) {
                    providerTestCards = {};
                }
            }
        }
        
        // Check for saved payload from builder on page load
        document.addEventListener('DOMContentLoaded', () => {
            const savedPayload = sessionStorage.getItem('payment_payload');
            if (savedPayload) {
                document.getElementById('saved-payload-notice').classList.remove('hidden');
            }
            // Load saved provider test cards
            loadSavedProviderCards();
        });
        
        // Builder integration functions
        function createQuickTest() {
            const savedPayload = sessionStorage.getItem('payment_payload');
            if (!savedPayload) {
                // Redirect to builder if no payload saved
                window.location.href = '/builder';
                return;
            }
            useBuilderPayload();
        }
        
        function useBuilderPayload() {
            const savedPayload = sessionStorage.getItem('payment_payload');
            if (!savedPayload) {
                uploadError.textContent = 'No saved payload found. Please use the Payment Builder first.';
                uploadError.classList.remove('hidden');
                return;
            }
            
            try {
                const payload = JSON.parse(savedPayload);
                
                // Create a minimal test suite with the payload
                const testSuite = {
                    version: "1.0",
                    metadata: {
                        test_suite_name: "Quick Test from Builder",
                        merchant_id: payload.account_id || "builder_test",
                        environment: "sandbox",
                        created_at: new Date().toISOString()
                    },
                    test_cases: [
                        {
                            id: "tc_quick_" + Date.now(),
                            name: "Payment Request Test",
                            description: payload.description || "Test payment from builder",
                            steps: [
                                {
                                    step_id: 1,
                                    operation: "payment",
                                    provider: extractProvider(payload),
                                    description: "Execute payment request",
                                    input_data: payload,
                                    capture_variables: {
                                        payment_id: "$.body.id",
                                        transaction_id: "$.body.transactions.id",
                                        status: "$.body.status"
                                    },
                                    expected_status: "success"
                                }
                            ]
                        }
                    ]
                };
                
                // Submit to upload endpoint
                const formData = new FormData();
                const blob = new Blob([JSON.stringify(testSuite)], { type: 'application/json' });
                formData.append('file', blob, 'quick_test.json');
                
                fetch('/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        uploadError.textContent = data.error;
                        uploadError.classList.remove('hidden');
                        return;
                    }
                    
                    currentSuiteId = data.suite_id;
                    currentSuite = data.test_suite;
                    selectedTestCases = new Set(data.test_suite.test_cases.map(tc => tc.id));
                    displayTestSuite(data.test_suite);
                    updateSelectionCount();
                    
                    // Clear the saved payload
                    clearBuilderPayload();
                })
                .catch(error => {
                    uploadError.textContent = 'Failed to create test: ' + error.message;
                    uploadError.classList.remove('hidden');
                });
                
            } catch (e) {
                uploadError.textContent = 'Invalid saved payload: ' + e.message;
                uploadError.classList.remove('hidden');
            }
        }
        
        function clearBuilderPayload() {
            sessionStorage.removeItem('payment_payload');
            document.getElementById('saved-payload-notice').classList.add('hidden');
        }
        
        function viewBuilderPayload() {
            // Navigate to builder - the payload will be loaded there from sessionStorage
            window.location.href = '/builder';
        }
        
        function extractProvider(payload) {
            // Try to extract provider from metadata or use default
            if (payload.metadata && Array.isArray(payload.metadata)) {
                const providerMeta = payload.metadata.find(m => m.key === 'provider');
                if (providerMeta) return providerMeta.value;
            }
            return 'yuno';
        }
        
        // File upload handling
        uploadArea.addEventListener('click', () => fileInput.click());
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) handleFile(file);
        });
        
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) handleFile(file);
        });
        
        // Scoping document options handling
        const scopingOptions = document.getElementById('csv-options');
        const scopingFilename = document.getElementById('csv-filename');
        let pendingFile = null;
        
        function showScopingOptions(file) {
            pendingFile = file;
            scopingFilename.textContent = `File: ${file.name}`;
            scopingOptions.classList.remove('hidden');
        }
        
        function hideScopingOptions() {
            scopingOptions.classList.add('hidden');
            pendingFile = null;
        }
        
        // Upload button handlers
        document.getElementById('csv-upload-btn').addEventListener('click', () => {
            if (pendingFile) {
                processFile(pendingFile);
            }
        });
        
        document.getElementById('csv-cancel-btn').addEventListener('click', () => {
            hideScopingOptions();
            fileInput.value = '';
        });
        
        async function handleFile(file) {
            // Validate CSV file
            if (!file.name.toLowerCase().endsWith('.csv')) {
                uploadError.textContent = 'Invalid file format. Please upload a CSV scoping document.';
                uploadError.classList.remove('hidden');
                return;
            }
            
            // Show options first
            if (scopingOptions.classList.contains('hidden')) {
                showScopingOptions(file);
                return;
            }
        }
        
        async function processFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('only_implemented', document.getElementById('only-implemented').checked);
            formData.append('merchant_id', document.getElementById('merchant-id').value);
            formData.append('environment', document.getElementById('environment-select').value);
            
            uploadError.classList.add('hidden');
            hideScopingOptions();
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.error) {
                    uploadError.textContent = data.error;
                    uploadError.classList.remove('hidden');
                    return;
                }
                
                currentSuiteId = data.suite_id;
                currentSuite = data.test_suite;
                currentHierarchy = data.hierarchy;
                
                // Flatten test cases and select all by default
                const allTestCases = [];
                currentHierarchy.forEach(pm => {
                    pm.providers.forEach(provider => {
                        provider.test_cases.forEach(tc => {
                            allTestCases.push(tc);
                        });
                    });
                });
                currentSuite.test_cases = allTestCases;
                selectedTestCases = new Set(allTestCases.map(tc => tc.id));
                
                // Automatically apply saved payload from builder to all test cases
                const savedPayload = sessionStorage.getItem('payment_payload');
                if (savedPayload) {
                    try {
                        const payload = JSON.parse(savedPayload);
                        // Apply deep copy to first step of each test case to avoid shared references
                        // (currentSuite.test_cases and hierarchy test cases share the same objects)
                        currentSuite.test_cases.forEach(tc => {
                            if (tc.steps.length > 0) {
                                tc.steps[0].input_data = JSON.parse(JSON.stringify(payload));
                            }
                        });
                        // Show the notice in the test cases section
                        document.getElementById('payload-active-notice').classList.remove('hidden');
                    } catch (e) {
                        console.error('Failed to apply saved payload:', e);
                    }
                }
                
                displayHierarchicalTestSuite();
                updateSelectionCount();
                
            } catch (error) {
                uploadError.textContent = 'Failed to upload file: ' + error.message;
                uploadError.classList.remove('hidden');
            }
        }
        
        
        function displayHierarchicalTestSuite() {
            // Display metadata
            metadataDiv.innerHTML = `
                <div class="metadata-item">
                    <div class="metadata-label">Suite Name</div>
                    <div class="metadata-value">${currentSuite.metadata.test_suite_name}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Environment</div>
                    <div class="metadata-value">${currentSuite.metadata.environment}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Merchant ID</div>
                    <div class="metadata-value">${currentSuite.metadata.merchant_id}</div>
                </div>
            `;
            
            // Display hierarchical test cases
            let html = '';
            let pmIndex = 0;
            
            currentHierarchy.forEach(pm => {
                pmIndex++;
                const pmTestCount = pm.providers.reduce((sum, p) => sum + p.test_cases.length, 0);
                const pmTestIds = [];
                pm.providers.forEach(p => p.test_cases.forEach(tc => pmTestIds.push(tc.id)));
                const pmAllSelected = pmTestIds.every(id => selectedTestCases.has(id));
                const pmSomeSelected = pmTestIds.some(id => selectedTestCases.has(id));
                
                html += `
                    <div class="hierarchy-group payment-method-group" id="pm-${pm.id}">
                        <div class="hierarchy-header payment-method-header" onclick="toggleHierarchyGroup('pm-${pm.id}')">
                            <div class="hierarchy-checkbox" onclick="event.stopPropagation()">
                                <input type="checkbox" 
                                       id="cb-pm-${pm.id}" 
                                       ${pmAllSelected ? 'checked' : ''} 
                                       ${pmSomeSelected && !pmAllSelected ? 'indeterminate' : ''}
                                       onchange="togglePaymentMethodSelection('${pm.id}')">
                            </div>
                            <span class="hierarchy-expand-icon">▶</span>
                            <span class="hierarchy-number">${pmIndex}.</span>
                            <span class="hierarchy-name">${pm.name}</span>
                            <span class="hierarchy-count">${pmTestCount} tests</span>
                        </div>
                        <div class="hierarchy-children">
                `;
                
                let providerIndex = 0;
                pm.providers.forEach(provider => {
                    providerIndex++;
                    const providerTestIds = provider.test_cases.map(tc => tc.id);
                    const providerAllSelected = providerTestIds.every(id => selectedTestCases.has(id));
                    const providerSomeSelected = providerTestIds.some(id => selectedTestCases.has(id));
                    const isCardProvider = pm.id.toUpperCase() === 'CARD';
                    const showCardInputs = isCardProvider && providerSomeSelected;
                    
                    html += `
                        <div class="hierarchy-group provider-group" id="provider-${pm.id}-${provider.id}">
                            <div class="hierarchy-header provider-header" onclick="toggleHierarchyGroup('provider-${pm.id}-${provider.id}')">
                                <div class="hierarchy-checkbox" onclick="event.stopPropagation()">
                                    <input type="checkbox" 
                                           id="cb-provider-${pm.id}-${provider.id}" 
                                           ${providerAllSelected ? 'checked' : ''} 
                                           ${providerSomeSelected && !providerAllSelected ? 'indeterminate' : ''}
                                           onchange="toggleProviderSelection('${pm.id}', '${provider.id}')">
                                </div>
                                <span class="hierarchy-expand-icon">▶</span>
                                <span class="hierarchy-number">${pmIndex}.${providerIndex}</span>
                                <span class="hierarchy-name">${provider.name}</span>
                                <span class="hierarchy-count">${provider.test_cases.length} tests</span>
                                ${isCardProvider ? `<button class="e2e-sdk-btn" onclick="event.stopPropagation(); startE2ETest('${provider.id}', '${provider.test_cases[0]?.id || ''}')" title="Run E2E SDK Lite test for ${provider.name}">E2E SDK</button>` : ''}
                            </div>
                            ${isCardProvider ? renderProviderCardInputs(provider.id, pm.id).replace('class="provider-card-inputs"', `class="provider-card-inputs${showCardInputs ? ' visible' : ''}"`) : ''}
                            <div class="hierarchy-children">
                    `;
                    
                    let tcIndex = 0;
                    provider.test_cases.forEach(tc => {
                        tcIndex++;
                        html += renderTestCaseHtml(tc, `${pmIndex}.${providerIndex}.${tcIndex}`);
                    });
                    
                    html += `
                            </div>
                        </div>
                    `;
                });
                
                html += `
                        </div>
                    </div>
                `;
            });
            
            testcasesList.innerHTML = html;
            
            // Set indeterminate state for checkboxes
            currentHierarchy.forEach(pm => {
                const pmTestIds = [];
                pm.providers.forEach(p => p.test_cases.forEach(tc => pmTestIds.push(tc.id)));
                const pmAllSelected = pmTestIds.every(id => selectedTestCases.has(id));
                const pmSomeSelected = pmTestIds.some(id => selectedTestCases.has(id));
                const pmCb = document.getElementById(`cb-pm-${pm.id}`);
                if (pmCb) pmCb.indeterminate = pmSomeSelected && !pmAllSelected;
                
                pm.providers.forEach(provider => {
                    const providerTestIds = provider.test_cases.map(tc => tc.id);
                    const providerAllSelected = providerTestIds.every(id => selectedTestCases.has(id));
                    const providerSomeSelected = providerTestIds.some(id => selectedTestCases.has(id));
                    const providerCb = document.getElementById(`cb-provider-${pm.id}-${provider.id}`);
                    if (providerCb) providerCb.indeterminate = providerSomeSelected && !providerAllSelected;
                });
            });
            
            testcasesSection.classList.remove('hidden');
            uploadSection.classList.add('hidden');
        }
        
        function renderTestCaseHtml(tc, indexStr) {
            const result = testResults[tc.id];
            let statusClass = '';
            let statusIcon = '';
            let durationHtml = '';
            
            if (result) {
                statusClass = result.status === 'pass' ? 'passed' : 
                              result.status === 'fail' ? 'failed' : 'error';
                statusIcon = result.status === 'pass' ? '✓' : 
                            result.status === 'fail' ? '✗' : '⚠';
                durationHtml = `<span class="test-case-duration">${result.duration_ms}ms</span>`;
            }
            
            const stepsDetailsHtml = tc.steps.map(step => {
                const stepResult = result?.steps?.find(s => s.step_id === step.step_id);
                const stepStatusClass = stepResult ? stepResult.status : '';
                const stepResultBadge = stepResult ? `
                    <span class="step-result-badge ${stepResult.status}">${stepResult.status.toUpperCase()}</span>
                    ${stepResult.duration_ms ? `<span style="color:#888;font-size:0.8rem;margin-left:8px">${stepResult.duration_ms}ms</span>` : ''}
                ` : '';
                
                const responseStatusHtml = stepResult?.response_status ? `
                    <div class="step-section">
                        <div class="step-section-label">API Response</div>
                        <div class="response-status-row">
                            <span class="response-status-badge">${stepResult.response_status}</span>
                            ${stepResult.response_substatus ? `<span class="response-substatus-badge">${stepResult.response_substatus}</span>` : ''}
                            ${stepResult.http_status_code ? `<span class="http-status-code">HTTP ${stepResult.http_status_code}</span>` : ''}
                        </div>
                    </div>
                ` : '';
                
                const requestHtml = step.input_data && Object.keys(step.input_data).length > 0 
                    ? `<div class="step-section">
                        <div class="collapsible-section" onclick="this.classList.toggle('open')">
                            <div class="collapsible-header">
                                <span class="collapse-icon">▶</span>
                                Request
                            </div>
                            <div class="collapsible-content">
                                <div class="step-data">${JSON.stringify(step.input_data, null, 2)}</div>
                            </div>
                        </div>
                       </div>` 
                    : '';
                
                const responseHtml = stepResult?.response_body 
                    ? `<div class="step-section">
                        <div class="collapsible-section" onclick="this.classList.toggle('open')">
                            <div class="collapsible-header">
                                <span class="collapse-icon">▶</span>
                                Response
                            </div>
                            <div class="collapsible-content">
                                <div class="step-data">${JSON.stringify(stepResult.response_body, null, 2)}</div>
                            </div>
                        </div>
                       </div>` 
                    : '';
                
                // Build quick info section with payment_id and x-trace-id
                let quickInfoHtml = '';
                const paymentId = stepResult?.response_body?.payment?.id || stepResult?.response_body?.id;
                const xTraceId = stepResult?.response_headers?.['x-trace-id'];
                if (paymentId || xTraceId) {
                    let items = '';
                    if (paymentId) {
                        items += `<div class="quick-info-item">
                            <span class="quick-info-label">Payment ID</span>
                            <a class="quick-info-value quick-info-link" href="https://dashboard.y.uno/payments/details/${paymentId}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${paymentId}</a>
                            <button class="copy-btn" onclick="event.stopPropagation(); copyValue('${paymentId}', this)">Copy</button>
                        </div>`;
                    }
                    if (xTraceId) {
                        const ddToTs = Date.now();
                        const ddFromTs = ddToTs - 86400000;
                        const ddUrl = `https://app.datadoghq.com/logs?query=%40trace_id%3A${xTraceId}&agg_m=count&agg_m_source=base&agg_t=count&cols=host%2Cservice&fromUser=true&messageDisplay=inline&refresh_mode=sliding&storage=hot&stream_sort=desc&viz=stream&from_ts=${ddFromTs}&to_ts=${ddToTs}&live=true`;
                        items += `<div class="quick-info-item">
                            <span class="quick-info-label">X-Trace-ID</span>
                            <a class="quick-info-value quick-info-link" href="${ddUrl}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${xTraceId}</a>
                            <button class="copy-btn" onclick="event.stopPropagation(); copyValue('${xTraceId}', this)">Copy</button>
                        </div>`;
                    }
                    quickInfoHtml = `<div class="quick-info">${items}</div>`;
                }
                
                // Filter out JSONPath "did not match" errors from display
                const shouldShowError = stepResult?.error_message && 
                    !stepResult.error_message.includes('did not match any values');
                const errorHtml = shouldShowError
                    ? `<div class="step-error-msg">${stepResult.error_message}</div>` 
                    : '';
                
                // Glean troubleshoot button for failed/declined steps
                const stepResponseUpper = (stepResult?.response_status || '').toUpperCase();
                const isDeclinedOrFailed = stepResult?.status === 'failure' 
                    || ['DECLINED', 'REJECTED', 'FAILED'].includes(stepResponseUpper);
                const gleanBtnHtml = (isDeclinedOrFailed && stepResult?.response_body && GLEAN_DOMAIN)
                    ? `<button class="btn-glean-troubleshoot" onclick="event.stopPropagation(); troubleshootStep('${tc.id}', ${step.step_id})">
                        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                        Troubleshoot on Glean
                       </button>`
                    : '';
                
                return `
                    <div class="step-detail ${stepStatusClass}">
                        <div class="step-detail-header">
                            <span class="step-number">${step.step_id}</span>
                            <span class="step-operation">${step.operation}</span>
                            <span style="color:#1a1a2e">${step.description}</span>
                            <span class="step-provider">${step.provider}</span>
                            ${stepResultBadge}
                        </div>
                        <div class="step-detail-body">
                            ${requestHtml}
                            ${responseStatusHtml}
                            ${quickInfoHtml}
                            ${responseHtml}
                            ${errorHtml}
                            ${gleanBtnHtml}
                        </div>
                    </div>
                `;
            }).join('');
            
            const isSelected = selectedTestCases.has(tc.id);
            
            return `
                <div class="test-case ${statusClass}" id="tc-${tc.id}">
                    <div class="test-case-summary">
                        <div class="test-case-checkbox" onclick="event.stopPropagation()">
                            <input type="checkbox" 
                                   id="cb-${tc.id}" 
                                   ${isSelected ? 'checked' : ''} 
                                   onchange="toggleTestCaseSelection('${tc.id}')">
                        </div>
                        <div class="test-case-content" onclick="toggleTestCase('${tc.id}')">
                            <div class="test-case-header">
                                <span class="test-case-index">${indexStr}</span>
                                <span class="test-case-name">
                                    ${statusIcon ? `<span class="status-icon">${statusIcon}</span>` : ''}
                                    ${tc.name}
                                </span>
                                ${durationHtml}
                            </div>
                            <div class="test-case-desc">${tc.description}</div>
                            <div class="steps-info">
                                <span class="expand-icon">▶</span>
                                ${tc.steps.length} step${tc.steps.length !== 1 ? 's' : ''}: ${tc.steps.map(s => s.operation).join(' → ')}
                            </div>
                        </div>
                    </div>
                    <div class="test-case-details">
                        <div class="test-case-details-inner">
                            ${stepsDetailsHtml}
                        </div>
                    </div>
                </div>
            `;
        }
        
        function displayTestSuite(suite, showResults = false) {
            // Legacy function - redirect to hierarchical display if hierarchy exists
            if (currentHierarchy) {
                displayHierarchicalTestSuite();
                return;
            }
            
            // Fallback for non-hierarchical data
            // Display metadata
            metadataDiv.innerHTML = `
                <div class="metadata-item">
                    <div class="metadata-label">Suite Name</div>
                    <div class="metadata-value">${suite.metadata.test_suite_name}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Environment</div>
                    <div class="metadata-value">${suite.metadata.environment}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Merchant ID</div>
                    <div class="metadata-value">${suite.metadata.merchant_id}</div>
                </div>
            `;
            
            // Display test cases
            testcasesList.innerHTML = suite.test_cases.map((tc, idx) => renderTestCaseHtml(tc, `${idx + 1}`)).join('');
            
            testcasesSection.classList.remove('hidden');
            uploadSection.classList.add('hidden');
        }
        
        function displayTestSuiteOld(suite, showResults = false) {
            // Display metadata
            metadataDiv.innerHTML = `
                <div class="metadata-item">
                    <div class="metadata-label">Suite Name</div>
                    <div class="metadata-value">${suite.metadata.test_suite_name}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Environment</div>
                    <div class="metadata-value">${suite.metadata.environment}</div>
                </div>
                <div class="metadata-item">
                    <div class="metadata-label">Merchant ID</div>
                    <div class="metadata-value">${suite.metadata.merchant_id}</div>
                </div>
            `;
            
            // Display test cases
            testcasesList.innerHTML = suite.test_cases.map(tc => {
                const result = testResults[tc.id];
                let statusClass = '';
                let statusIcon = '';
                let durationHtml = '';
                
                if (result) {
                    statusClass = result.status === 'pass' ? 'passed' : 
                                  result.status === 'fail' ? 'failed' : 'error';
                    statusIcon = result.status === 'pass' ? '✓' : 
                                result.status === 'fail' ? '✗' : '⚠';
                    durationHtml = `<span class="test-case-duration">${result.duration_ms}ms</span>`;
                }
                
                // Build step details HTML
                const stepsDetailsHtml = tc.steps.map((step, idx) => {
                    const stepResult = result?.steps?.find(s => s.step_id === step.step_id);
                    const stepStatusClass = stepResult ? stepResult.status : '';
                    const stepResultBadge = stepResult ? `
                        <span class="step-result-badge ${stepResult.status}">${stepResult.status.toUpperCase()}</span>
                        ${stepResult.duration_ms ? `<span style="color:#888;font-size:0.8rem;margin-left:8px">${stepResult.duration_ms}ms</span>` : ''}
                    ` : '';
                    
                    // Build response status section
                    const responseStatusHtml = stepResult?.response_status ? `
                        <div class="step-section">
                            <div class="step-section-label">API Response</div>
                            <div class="response-status-row">
                                <span class="response-status-badge">${stepResult.response_status}</span>
                                ${stepResult.response_substatus ? `<span class="response-substatus-badge">${stepResult.response_substatus}</span>` : ''}
                                ${stepResult.http_status_code ? `<span class="http-status-code">HTTP ${stepResult.http_status_code}</span>` : ''}
                            </div>
                        </div>
                    ` : '';
                    
                    const requestHtml = step.input_data && Object.keys(step.input_data).length > 0 
                        ? `<div class="step-section">
                            <div class="collapsible-section" onclick="this.classList.toggle('open')">
                                <div class="collapsible-header">
                                    <span class="collapse-icon">▶</span>
                                    Request
                                </div>
                                <div class="collapsible-content">
                                    <div class="step-data">${JSON.stringify(step.input_data, null, 2)}</div>
                                </div>
                            </div>
                           </div>` 
                        : '';
                    
                    const responseHtml = stepResult?.response_body 
                        ? `<div class="step-section">
                            <div class="collapsible-section" onclick="this.classList.toggle('open')">
                                <div class="collapsible-header">
                                    <span class="collapse-icon">▶</span>
                                    Response
                                </div>
                                <div class="collapsible-content">
                                    <div class="step-data">${JSON.stringify(stepResult.response_body, null, 2)}</div>
                                </div>
                            </div>
                           </div>` 
                        : '';
                    
                    // Build quick info section with payment_id and x-trace-id
                    let quickInfoHtml = '';
                    const paymentId = stepResult?.response_body?.payment?.id || stepResult?.response_body?.id;
                    const xTraceId = stepResult?.response_headers?.['x-trace-id'];
                    if (paymentId || xTraceId) {
                        let items = '';
                        if (paymentId) {
                            items += `<div class="quick-info-item">
                                <span class="quick-info-label">Payment ID</span>
                                <a class="quick-info-value quick-info-link" href="https://dashboard.y.uno/payments/details/${paymentId}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${paymentId}</a>
                                <button class="copy-btn" onclick="event.stopPropagation(); copyValue('${paymentId}', this)">Copy</button>
                            </div>`;
                        }
                        if (xTraceId) {
                            const ddToTs = Date.now();
                            const ddFromTs = ddToTs - 86400000;
                            const ddUrl = `https://app.datadoghq.com/logs?query=%40trace_id%3A${xTraceId}&agg_m=count&agg_m_source=base&agg_t=count&cols=host%2Cservice&fromUser=true&messageDisplay=inline&refresh_mode=sliding&storage=hot&stream_sort=desc&viz=stream&from_ts=${ddFromTs}&to_ts=${ddToTs}&live=true`;
                            items += `<div class="quick-info-item">
                                <span class="quick-info-label">X-Trace-ID</span>
                                <a class="quick-info-value quick-info-link" href="${ddUrl}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${xTraceId}</a>
                                <button class="copy-btn" onclick="event.stopPropagation(); copyValue('${xTraceId}', this)">Copy</button>
                            </div>`;
                        }
                        quickInfoHtml = `<div class="quick-info">${items}</div>`;
                    }
                    
                    // Filter out JSONPath "did not match" errors from display
                    const shouldShowError = stepResult?.error_message && 
                        !stepResult.error_message.includes('did not match any values');
                    const errorHtml = shouldShowError
                        ? `<div class="step-error-msg">${stepResult.error_message}</div>` 
                        : '';
                    
                    return `
                        <div class="step-detail ${stepStatusClass}">
                            <div class="step-detail-header">
                                <span class="step-number">${step.step_id}</span>
                                <span class="step-operation">${step.operation}</span>
                                <span style="color:#1a1a2e">${step.description}</span>
                                <span class="step-provider">${step.provider}</span>
                                ${stepResultBadge}
                            </div>
                            <div class="step-detail-body">
                                ${requestHtml}
                                ${responseStatusHtml}
                                ${quickInfoHtml}
                                ${responseHtml}
                                ${errorHtml}
                            </div>
                        </div>
                    `;
                }).join('');
                
                const isSelected = selectedTestCases.has(tc.id);
                
                return `
                    <div class="test-case ${statusClass}" id="tc-${tc.id}">
                        <div class="test-case-summary">
                            <div class="test-case-checkbox" onclick="event.stopPropagation()">
                                <input type="checkbox" 
                                       id="cb-${tc.id}" 
                                       ${isSelected ? 'checked' : ''} 
                                       onchange="toggleTestCaseSelection('${tc.id}')">
                            </div>
                            <div class="test-case-content" onclick="toggleTestCase('${tc.id}')">
                                <div class="test-case-header">
                                    <span class="test-case-name">
                                        ${statusIcon ? `<span class="status-icon">${statusIcon}</span>` : ''}
                                        ${tc.name}
                                    </span>
                                    ${durationHtml}
                                    <span class="test-case-id">${tc.id}</span>
                                </div>
                                <div class="test-case-desc">${tc.description}</div>
                                <div class="steps-info">
                                    <span class="expand-icon">▶</span>
                                    ${tc.steps.length} step${tc.steps.length !== 1 ? 's' : ''}: ${tc.steps.map(s => s.operation).join(' → ')}
                                </div>
                            </div>
                        </div>
                        <div class="test-case-details">
                            <div class="test-case-details-inner">
                                ${stepsDetailsHtml}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
            
            testcasesSection.classList.remove('hidden');
            uploadSection.classList.add('hidden');
        }
        
        function toggleTestCase(tcId) {
            const element = document.getElementById(`tc-${tcId}`);
            if (element) {
                element.classList.toggle('expanded');
            }
        }
        
        function copyValue(value, btn) {
            navigator.clipboard.writeText(value).then(() => {
                const originalText = btn.innerHTML;
                btn.innerHTML = '✓ Copied';
                btn.classList.add('copied');
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.classList.remove('copied');
                }, 1500);
            });
        }
        
        function toggleHierarchyGroup(groupId) {
            const element = document.getElementById(groupId);
            if (element) {
                element.classList.toggle('expanded');
            }
        }
        
        function toggleTestCaseSelection(tcId) {
            if (selectedTestCases.has(tcId)) {
                selectedTestCases.delete(tcId);
            } else {
                selectedTestCases.add(tcId);
            }
            updateHierarchyCheckboxes();
            updateSelectionCount();
            updateSelectAllCheckbox();
            updateCardInputsVisibility();
        }
        
        function togglePaymentMethodSelection(pmId) {
            const pm = currentHierarchy.find(p => p.id === pmId);
            if (!pm) return;
            
            const pmTestIds = [];
            pm.providers.forEach(provider => {
                provider.test_cases.forEach(tc => pmTestIds.push(tc.id));
            });
            
            const allSelected = pmTestIds.every(id => selectedTestCases.has(id));
            
            if (allSelected) {
                // Deselect all
                pmTestIds.forEach(id => selectedTestCases.delete(id));
            } else {
                // Select all
                pmTestIds.forEach(id => selectedTestCases.add(id));
            }
            
            // Update checkboxes
            pmTestIds.forEach(id => {
                const cb = document.getElementById(`cb-${id}`);
                if (cb) cb.checked = selectedTestCases.has(id);
            });
            
            updateHierarchyCheckboxes();
            updateSelectionCount();
            updateSelectAllCheckbox();
            updateCardInputsVisibility();
        }
        
        function toggleProviderSelection(pmId, providerId) {
            const pm = currentHierarchy.find(p => p.id === pmId);
            if (!pm) return;
            
            const provider = pm.providers.find(p => p.id === providerId);
            if (!provider) return;
            
            const providerTestIds = provider.test_cases.map(tc => tc.id);
            const allSelected = providerTestIds.every(id => selectedTestCases.has(id));
            
            if (allSelected) {
                // Deselect all
                providerTestIds.forEach(id => selectedTestCases.delete(id));
            } else {
                // Select all
                providerTestIds.forEach(id => selectedTestCases.add(id));
            }
            
            // Update test case checkboxes
            providerTestIds.forEach(id => {
                const cb = document.getElementById(`cb-${id}`);
                if (cb) cb.checked = selectedTestCases.has(id);
            });
            
            updateHierarchyCheckboxes();
            updateSelectionCount();
            updateSelectAllCheckbox();
            updateCardInputsVisibility();
        }
        
        function updateHierarchyCheckboxes() {
            if (!currentHierarchy) return;
            
            currentHierarchy.forEach(pm => {
                // Update provider checkboxes
                pm.providers.forEach(provider => {
                    const providerTestIds = provider.test_cases.map(tc => tc.id);
                    const providerAllSelected = providerTestIds.every(id => selectedTestCases.has(id));
                    const providerSomeSelected = providerTestIds.some(id => selectedTestCases.has(id));
                    
                    const providerCb = document.getElementById(`cb-provider-${pm.id}-${provider.id}`);
                    if (providerCb) {
                        providerCb.checked = providerAllSelected;
                        providerCb.indeterminate = providerSomeSelected && !providerAllSelected;
                    }
                });
                
                // Update payment method checkbox
                const pmTestIds = [];
                pm.providers.forEach(p => p.test_cases.forEach(tc => pmTestIds.push(tc.id)));
                const pmAllSelected = pmTestIds.every(id => selectedTestCases.has(id));
                const pmSomeSelected = pmTestIds.some(id => selectedTestCases.has(id));
                
                const pmCb = document.getElementById(`cb-pm-${pm.id}`);
                if (pmCb) {
                    pmCb.checked = pmAllSelected;
                    pmCb.indeterminate = pmSomeSelected && !pmAllSelected;
                }
            });
        }
        
        function toggleSelectAll() {
            const selectAllCheckbox = document.getElementById('select-all');
            if (selectAllCheckbox.checked) {
                // Select all
                currentSuite.test_cases.forEach(tc => selectedTestCases.add(tc.id));
            } else {
                // Deselect all
                selectedTestCases.clear();
            }
            // Update individual checkboxes
            currentSuite.test_cases.forEach(tc => {
                const cb = document.getElementById(`cb-${tc.id}`);
                if (cb) cb.checked = selectAllCheckbox.checked;
            });
            updateHierarchyCheckboxes();
            updateSelectionCount();
            updateCardInputsVisibility();
        }
        
        function updateSelectAllCheckbox() {
            const selectAllCheckbox = document.getElementById('select-all');
            if (currentSuite) {
                const allSelected = currentSuite.test_cases.every(tc => selectedTestCases.has(tc.id));
                const someSelected = currentSuite.test_cases.some(tc => selectedTestCases.has(tc.id));
                selectAllCheckbox.checked = allSelected;
                selectAllCheckbox.indeterminate = someSelected && !allSelected;
            }
        }
        
        function updateSelectionCount() {
            const countEl = document.getElementById('selection-count');
            if (countEl && currentSuite) {
                const total = currentSuite.test_cases.length;
                const selected = selectedTestCases.size;
                countEl.textContent = `${selected} of ${total} selected`;
            }
        }
        
        function getSelectedTestCaseIds() {
            return Array.from(selectedTestCases);
        }
        
        function updateSummary() {
            summaryDiv.innerHTML = `
                <div class="summary-item">
                    <div class="summary-value">${summary.total}</div>
                    <div class="summary-label">Test Cases</div>
                </div>
                <div class="summary-item passed">
                    <div class="summary-value">${summary.passed}</div>
                    <div class="summary-label">Passed</div>
                </div>
                <div class="summary-item failed">
                    <div class="summary-value">${summary.failed}</div>
                    <div class="summary-label">Failed</div>
                </div>
                <div class="summary-item errors">
                    <div class="summary-value">${summary.errors}</div>
                    <div class="summary-label">Errors</div>
                </div>
                <div class="summary-item approved">
                    <div class="summary-value">${summary.approved}</div>
                    <div class="summary-label">Approved</div>
                </div>
                <div class="summary-item declined">
                    <div class="summary-value">${summary.declined}</div>
                    <div class="summary-label">Declined</div>
                </div>
            `;
            summaryDiv.classList.remove('hidden');
        }
        
        function updateTestCaseUI(tc) {
            const element = document.getElementById(`tc-${tc.test_case_id}`);
            if (!element) return;
            
            const statusClass = tc.status === 'pass' ? 'passed' : 
                              tc.status === 'fail' ? 'failed' : 'error';
            const statusIcon = tc.status === 'pass' ? '✓' : 
                              tc.status === 'fail' ? '✗' : '⚠';
            
            element.classList.remove('running', 'passed', 'failed', 'error');
            element.classList.add(statusClass);
            
            // Update the name with icon
            const nameEl = element.querySelector('.test-case-name');
            if (nameEl) {
                const existingIcon = nameEl.querySelector('.status-icon');
                if (existingIcon) {
                    existingIcon.textContent = statusIcon;
                } else {
                    nameEl.insertAdjacentHTML('afterbegin', `<span class="status-icon">${statusIcon}</span>`);
                }
                // Remove spinner if present
                const spinner = nameEl.querySelector('.spinner-small');
                if (spinner) spinner.remove();
            }
            
            // Add duration
            const header = element.querySelector('.test-case-header');
            if (header) {
                let durationEl = header.querySelector('.test-case-duration');
                if (!durationEl) {
                    const idEl = header.querySelector('.test-case-id');
                    if (idEl) {
                        idEl.insertAdjacentHTML('beforebegin', `<span class="test-case-duration">${tc.duration_ms}ms</span>`);
                    }
                } else {
                    durationEl.textContent = `${tc.duration_ms}ms`;
                }
            }
            
            // Update step details with results
            if (tc.steps && tc.steps.length > 0) {
                const stepDetails = element.querySelectorAll('.step-detail');
                tc.steps.forEach(stepResult => {
                    const stepEl = stepDetails[stepResult.step_id - 1];
                    if (!stepEl) {
                        console.error('[DEBUG] stepEl not found for step_id', stepResult.step_id);
                        return;
                    }
                    
                    stepEl.classList.remove('success', 'failure', 'error');
                    stepEl.classList.add(stepResult.status);
                    
                    // Add result badge to header
                    const headerEl = stepEl.querySelector('.step-detail-header');
                    if (!headerEl) {
                        console.error('[DEBUG] headerEl not found for step', stepResult.step_id);
                        return;
                    }
                    
                    let badge = headerEl.querySelector('.step-result-badge');
                    if (!badge) {
                        headerEl.insertAdjacentHTML('beforeend', `
                            <span class="step-result-badge ${stepResult.status}">${stepResult.status.toUpperCase()}</span>
                            ${stepResult.duration_ms ? `<span style="color:#888;font-size:0.8rem;margin-left:8px">${stepResult.duration_ms}ms</span>` : ''}
                        `);
                    }
                    
                        // Update the Request section with the actual request body sent to the API
                        if (stepResult.request_body) {
                            const bodyEl = stepEl.querySelector('.step-detail-body');
                            if (bodyEl) {
                                const requestSection = bodyEl.querySelector('.step-section .collapsible-content .step-data');
                                if (requestSection) {
                                    requestSection.textContent = JSON.stringify(stepResult.request_body, null, 2);
                                }
                            }
                        }
                        
                        // Add response status and body sections
                        console.log('[DEBUG] Step', stepResult.step_id, 'response_status:', stepResult.response_status, 'response_body:', stepResult.response_body);
                        if (stepResult.response_status || stepResult.response_body) {
                            const bodyEl = stepEl.querySelector('.step-detail-body');
                            console.log('[DEBUG] Step', stepResult.step_id, 'bodyEl found:', bodyEl !== null);
                            
                            if (!bodyEl) {
                                console.error('[DEBUG] bodyEl not found for step', stepResult.step_id);
                                return;
                            }
                            
                            // Add response status row if not present
                            if (!bodyEl.querySelector('.response-status-row')) {
                                // Show status section if we have response_status OR http_status_code
                                if (stepResult.response_status || stepResult.http_status_code) {
                                    const statusHtml = `
                                        <div class="step-section response-status-section">
                                            <div class="step-section-label">API Response</div>
                                            <div class="response-status-row">
                                                ${stepResult.response_status ? `<span class="response-status-badge">${stepResult.response_status}</span>` : ''}
                                                ${stepResult.response_substatus ? `<span class="response-substatus-badge">${stepResult.response_substatus}</span>` : ''}
                                                ${stepResult.http_status_code ? `<span class="http-status-code ${stepResult.http_status_code >= 400 ? 'error' : ''}"">HTTP ${stepResult.http_status_code}</span>` : ''}
                                            </div>
                                        </div>
                                    `;
                                    const requestStepSection = bodyEl.querySelector('.step-section');
                                    if (requestStepSection) {
                                        requestStepSection.insertAdjacentHTML('afterend', statusHtml);
                                    } else {
                                        bodyEl.insertAdjacentHTML('afterbegin', statusHtml);
                                    }
                                    console.log('[DEBUG] Added response status section');
                                }
                            }
                            
                            // Add collapsible response body if not present
                            console.log('[DEBUG] Step', stepResult.step_id, 'response_body exists:', !!stepResult.response_body, 'response-body-section exists:', !!bodyEl.querySelector('.response-body-section'));
                            if (stepResult.response_body && !bodyEl.querySelector('.response-body-section')) {
                                console.log('[DEBUG] Adding response body section for step', stepResult.step_id);
                                const responseBodyHtml = `
                                    <div class="step-section response-body-section">
                                        <div class="collapsible-section" onclick="this.classList.toggle('open')">
                                            <div class="collapsible-header">
                                                <span class="collapse-icon">▶</span>
                                                Response
                                            </div>
                                            <div class="collapsible-content">
                                                <div class="step-data">${JSON.stringify(stepResult.response_body, null, 2)}</div>
                                            </div>
                                        </div>
                                    </div>
                                `;
                                const statusSection = bodyEl.querySelector('.response-status-section');
                                const requestStepSection = bodyEl.querySelector('.step-section');
                                console.log('[DEBUG] statusSection:', !!statusSection, 'requestStepSection:', !!requestStepSection);
                                if (statusSection) {
                                    statusSection.insertAdjacentHTML('afterend', responseBodyHtml);
                                    console.log('[DEBUG] Inserted after statusSection');
                                } else if (requestStepSection) {
                                    requestStepSection.insertAdjacentHTML('afterend', responseBodyHtml);
                                    console.log('[DEBUG] Inserted after requestStepSection');
                                } else {
                                    bodyEl.insertAdjacentHTML('afterbegin', responseBodyHtml);
                                    console.log('[DEBUG] Inserted at beginning of bodyEl');
                                }
                            }
                        }
                        
                        // Update quick info section with payment_id and x-trace-id
                        const paymentId = stepResult.response_body?.payment?.id || stepResult.response_body?.id;
                        const xTraceId = stepResult.response_headers?.['x-trace-id'];
                        if (paymentId || xTraceId) {
                            const bodyEl = stepEl.querySelector('.step-detail-body');
                            // Check if quick-info section already exists
                            let quickInfoSection = bodyEl.querySelector('.quick-info');
                            
                            let items = '';
                            if (paymentId) {
                                items += `<div class="quick-info-item">
                                    <span class="quick-info-label">Payment ID</span>
                                    <a class="quick-info-value quick-info-link" href="https://dashboard.y.uno/payments/details/${paymentId}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${paymentId}</a>
                                    <button class="copy-btn" onclick="event.stopPropagation(); copyValue('${paymentId}', this)">Copy</button>
                                </div>`;
                            }
                            if (xTraceId) {
                                const ddToTs = Date.now();
                                const ddFromTs = ddToTs - 86400000;
                                const ddUrl = `https://app.datadoghq.com/logs?query=%40trace_id%3A${xTraceId}&agg_m=count&agg_m_source=base&agg_t=count&cols=host%2Cservice&fromUser=true&messageDisplay=inline&refresh_mode=sliding&storage=hot&stream_sort=desc&viz=stream&from_ts=${ddFromTs}&to_ts=${ddToTs}&live=true`;
                                items += `<div class="quick-info-item">
                                    <span class="quick-info-label">X-Trace-ID</span>
                                    <a class="quick-info-value quick-info-link" href="${ddUrl}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${xTraceId}</a>
                                    <button class="copy-btn" onclick="event.stopPropagation(); copyValue('${xTraceId}', this)">Copy</button>
                                </div>`;
                            }
                            const quickInfoHtml = `<div class="quick-info">${items}</div>`;
                            
                            if (quickInfoSection) {
                                quickInfoSection.outerHTML = quickInfoHtml;
                            } else {
                                // Insert after response status section or at end
                                const statusSection = bodyEl.querySelector('.response-status-section');
                                if (statusSection) {
                                    statusSection.insertAdjacentHTML('afterend', quickInfoHtml);
                                } else {
                                    bodyEl.insertAdjacentHTML('beforeend', quickInfoHtml);
                                }
                            }
                        }
                        
                        // Add error message if present (filter out JSONPath "did not match" errors)
                        if (stepResult.error_message && !stepResult.error_message.includes('did not match any values')) {
                            const errBodyEl = stepEl.querySelector('.step-detail-body');
                            if (errBodyEl && !errBodyEl.querySelector('.step-error-msg')) {
                                errBodyEl.insertAdjacentHTML('beforeend', `
                                    <div class="step-error-msg">${stepResult.error_message}</div>
                                `);
                            }
                        }
                        
                        // Add "Troubleshoot on Glean" button for failed/declined steps
                        const respStatusUpper = (stepResult.response_status || '').toUpperCase();
                        const isStepDeclinedOrFailed = stepResult.status === 'failure' 
                            || ['DECLINED', 'REJECTED', 'FAILED'].includes(respStatusUpper);
                        if (isStepDeclinedOrFailed && stepResult.response_body && GLEAN_DOMAIN) {
                            const gleanBodyEl = stepEl.querySelector('.step-detail-body');
                            if (gleanBodyEl && !gleanBodyEl.querySelector('.btn-glean-troubleshoot')) {
                                gleanBodyEl.insertAdjacentHTML('beforeend', `
                                    <button class="btn-glean-troubleshoot" onclick="event.stopPropagation(); troubleshootStep('${tc.test_case_id}', ${stepResult.step_id})">
                                        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                                        Troubleshoot on Glean
                                    </button>
                                `);
                            }
                        }
                });
            }
        }
        
        function markTestCaseRunning(tcId) {
            const element = document.getElementById(`tc-${tcId}`);
            if (!element) return;
            
            element.classList.add('running');
            const nameEl = element.querySelector('.test-case-name');
            if (nameEl) {
                const existingIcon = nameEl.querySelector('.status-icon');
                const spinner = nameEl.querySelector('.spinner-small');
                if (!spinner) {
                    if (existingIcon) {
                        existingIcon.outerHTML = '<span class="spinner-small"></span>';
                    } else {
                        nameEl.insertAdjacentHTML('afterbegin', '<span class="spinner-small"></span>');
                    }
                }
            }
        }
        
        document.getElementById('run-btn').addEventListener('click', async () => {
            if (!currentSuiteId) return;
            
            // Check if any test cases are selected
            const selectedIds = getSelectedTestCaseIds();
            if (selectedIds.length === 0) {
                uploadError.textContent = 'Please select at least one test case to execute.';
                uploadError.classList.remove('hidden');
                return;
            }
            
            uploadError.classList.add('hidden');
            
            // Reset state
            testResults = {};
            summary = { total: selectedIds.length, passed: 0, failed: 0, errors: 0, approved: 0, declined: 0 };
            
            // Show execution status
            executionStatus.classList.remove('hidden');
            actions.classList.add('hidden');
            postActions.classList.add('hidden');
            summaryDiv.classList.add('hidden');
            
            // Save expanded state before re-rendering
            const expandedIds = new Set();
            document.querySelectorAll('.hierarchy-group.expanded, .test-case.expanded').forEach(el => {
                expandedIds.add(el.id);
            });
            
            // Reset test case displays
            displayTestSuite(currentSuite);
            
            // Restore expanded state after re-rendering
            expandedIds.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.classList.add('expanded');
            });
            
            // Check if we have a saved payload from the Builder
            const savedPayload = sessionStorage.getItem('payment_payload');
            
            // Function to start the actual execution
            const startExecution = () => {
                const idsParam = encodeURIComponent(selectedIds.join(','));
                const eventSource = new EventSource(`/execute-stream?suite_id=${currentSuiteId}&test_case_ids=${idsParam}`);
                setupEventSource(eventSource);
            };
            
            // Collect provider test cards from inline inputs
            const collectProviderCards = () => {
                if (!currentHierarchy) return;
                
                currentHierarchy.forEach(pm => {
                    if (pm.id.toUpperCase() === 'CARD') {
                        pm.providers.forEach(provider => {
                            const providerTestIds = provider.test_cases.map(tc => tc.id);
                            const isSelected = providerTestIds.some(id => selectedTestCases.has(id));
                            
                            if (isSelected) {
                                // Collect card data from inline inputs if present
                                const numberEl = document.getElementById(`card-number-${provider.id}`);
                                if (numberEl && numberEl.value.trim()) {
                                    providerTestCards[provider.id] = {
                                        number: numberEl.value.trim(),
                                        expiration_month: parseInt(document.getElementById(`card-exp-month-${provider.id}`)?.value) || 12,
                                        expiration_year: parseInt(document.getElementById(`card-exp-year-${provider.id}`)?.value) || 27,
                                        security_code: document.getElementById(`card-cvv-${provider.id}`)?.value.trim() || '123',
                                        holder_name: document.getElementById(`card-holder-${provider.id}`)?.value.trim() || 'TEST USER'
                                    };
                                }
                            }
                        });
                    }
                });
                
                // Save to sessionStorage
                sessionStorage.setItem('provider_test_cards', JSON.stringify(providerTestCards));
            };
            
            // Function to send provider test cards to backend
            const sendProviderCards = async () => {
                // First collect cards from inline inputs
                collectProviderCards();
                
                if (Object.keys(providerTestCards).length > 0) {
                    try {
                        const response = await fetch('/api/update-provider-cards', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ suite_id: currentSuiteId, cards: providerTestCards })
                        });
                        const data = await response.json();
                        if (data.error) {
                            console.error('Failed to apply provider cards:', data.error);
                        } else {
                            console.log('Provider cards applied:', data.message);
                        }
                    } catch (error) {
                        console.error('Error applying provider cards:', error);
                    }
                }
            };
            
            // Send provider cards first, then payload, then start execution
            await sendProviderCards();
            
            // If we have a saved payload, send it to the backend first
            if (savedPayload) {
                try {
                    const payload = JSON.parse(savedPayload);
                    fetch('/api/update-payload', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ suite_id: currentSuiteId, payload: payload })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            console.error('Failed to apply payload:', data.error);
                        } else {
                            console.log('Payload applied:', data.message);
                        }
                        startExecution();
                    })
                    .catch(error => {
                        console.error('Error applying payload:', error);
                        startExecution();
                    });
                } catch (e) {
                    console.error('Invalid saved payload:', e);
                    startExecution();
                }
            } else {
                startExecution();
            }
        });
        
        function setupEventSource(eventSource) {
            
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'start') {
                    currentExecutionId = data.execution_id;
                    summary.total = data.total;
                    statusText.textContent = `Running ${data.total} test case${data.total !== 1 ? 's' : ''}...`;
                    updateSummary();
                }
                else if (data.type === 'test_case_start') {
                    statusText.textContent = `Running: ${data.test_case_name}`;
                    markTestCaseRunning(data.test_case_id);
                }
                else if (data.type === 'test_case_result') {
                    const tc = data.result;
                    testResults[tc.test_case_id] = tc;
                    
                    // Update test case summary
                    if (tc.status === 'pass') summary.passed++;
                    else if (tc.status === 'fail') summary.failed++;
                    else summary.errors++;
                    
                    // Count approved/declined transactions from step responses
                    if (tc.steps) {
                        tc.steps.forEach(step => {
                            if (step.response_status) {
                                const status = step.response_status.toUpperCase();
                                if (status === 'SUCCEEDED' || status === 'APPROVED' || status === 'CAPTURED') {
                                    summary.approved++;
                                } else if (status === 'DECLINED' || status === 'REJECTED' || status === 'FAILED') {
                                    summary.declined++;
                                }
                            }
                        });
                    }
                    
                    updateSummary();
                    updateTestCaseUI(tc);
                }
                else if (data.type === 'complete') {
                    eventSource.close();
                    executionStatus.classList.add('hidden');
                    actions.classList.add('hidden');
                    postActions.classList.remove('hidden');
                }
                else if (data.type === 'error') {
                    eventSource.close();
                    executionStatus.classList.add('hidden');
                    actions.classList.remove('hidden');
                    uploadError.textContent = data.message;
                    uploadError.classList.remove('hidden');
                }
            };
            
            eventSource.onerror = () => {
                eventSource.close();
                executionStatus.classList.add('hidden');
                actions.classList.remove('hidden');
            };
        }
        
        document.getElementById('download-btn').addEventListener('click', () => {
            if (currentExecutionId) {
                window.location.href = `/download/${currentExecutionId}`;
            }
        });
        
        document.getElementById('clear-btn').addEventListener('click', () => {
            currentSuiteId = null;
            currentSuite = null;
            testResults = {};
            testcasesSection.classList.add('hidden');
            uploadSection.classList.remove('hidden');
            uploadError.classList.add('hidden');
            fileInput.value = '';
        });
        
        document.getElementById('run-again-btn').addEventListener('click', () => {
            testResults = {};
            summary = { total: 0, passed: 0, failed: 0, errors: 0, approved: 0, declined: 0 };
            postActions.classList.add('hidden');
            actions.classList.remove('hidden');
            summaryDiv.classList.add('hidden');
            displayTestSuite(currentSuite);
        });
        
        document.getElementById('new-test-btn').addEventListener('click', () => {
            currentSuiteId = null;
            currentSuite = null;
            currentExecutionId = null;
            testResults = {};
            testcasesSection.classList.add('hidden');
            uploadSection.classList.remove('hidden');
            uploadError.classList.add('hidden');
            fileInput.value = '';
        });

        async function startE2ETest(providerId, testCaseId) {
            if (!currentSuiteId) {
                alert('No test suite loaded');
                return;
            }
            if (!testCaseId) {
                alert('No test case found for this provider');
                return;
            }

            const btn = event.target;
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = 'Starting...';

            try {
                const res = await fetch('/e2e/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        suite_id: currentSuiteId,
                        test_case_id: testCaseId,
                        provider: providerId
                    })
                });
                const data = await res.json();

                if (!res.ok) {
                    let msg = data.error || 'Unknown error';
                    if (data.details) {
                        const detail = typeof data.details === 'string'
                            ? data.details
                            : JSON.stringify(data.details, null, 2);
                        msg += '\\n\\nDetails:\\n' + detail;
                    }
                    alert('E2E start failed: ' + msg);
                    return;
                }

                window.open('/e2e/checkout/' + data.e2e_session_id, '_blank');
            } catch (err) {
                alert('E2E start error: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the main page."""
    return render_template_string(
        HTML_TEMPLATE,
        glean_domain=os.getenv('GLEAN_DOMAIN', ''),
        glean_agent_id=os.getenv('GLEAN_AGENT_ID', '')
    )


# =============================================================================
# Glean Chat - Standalone troubleshooting page
# =============================================================================

GLEAN_CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MATRIX - Troubleshoot on Glean</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { height: 100%; overflow: hidden; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #fff;
        }
        #chat-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        .chat-placeholder {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            text-align: center;
            padding: 40px;
            color: #656d76;
        }
        .chat-placeholder h3 { font-size: 18px; margin-bottom: 8px; color: #333; }
        .chat-placeholder p { font-size: 13px; max-width: 400px; line-height: 1.6; }
        .spinner {
            width: 36px; height: 36px;
            border: 3px solid #e5e7eb;
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 16px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div id="chat-container">
        <div class="chat-placeholder" id="placeholder">
            <div class="spinner"></div>
            <h3>Connecting to Glean...</h3>
            <p>Loading the AI assistant to help troubleshoot this payment.</p>
        </div>
    </div>

    <script>
        (function boot() {
            const params = new URLSearchParams(window.location.search);
            const domain = params.get('domain');

            if (!domain) {
                document.getElementById('placeholder').innerHTML =
                    '<h3>Configuration Error</h3><p>No Glean domain configured. Set <strong>GLEAN_DOMAIN</strong> in your .env file and restart.</p>';
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://' + domain + '/embedded-search-latest.min.js';
            script.defer = true;

            script.onload = function() {
                const container = document.getElementById('chat-container');
                var placeholder = document.getElementById('placeholder');
                if (placeholder) placeholder.remove();

                var options = {};
                var msg = params.get('initialMessage');
                var agent = params.get('agentId');
                var theme = params.get('themeVariant');

                if (msg) options.initialMessage = msg;
                if (agent) options.agentId = agent;
                if (theme) options.themeVariant = theme;

                try {
                    var SDK = window.EmbeddedSearch || window.GleanWebSDK;
                    SDK.renderChat(container, options);
                } catch (e) {
                    console.error('Glean Chat error:', e);
                    container.innerHTML = '<div class="chat-placeholder"><h3>Chat Error</h3><p>' + e.message + '</p></div>';
                }
            };

            script.onerror = function() {
                document.getElementById('chat-container').innerHTML =
                    '<div class="chat-placeholder"><h3>Connection Failed</h3><p>Could not load the Glean SDK from <strong>' + domain + '</strong>.</p></div>';
            };

            document.head.appendChild(script);
        })();
    </script>
</body>
</html>
"""


@app.route('/glean-chat')
def glean_chat():
    """Serve the standalone Glean chat page for payment troubleshooting."""
    return render_template_string(GLEAN_CHAT_TEMPLATE)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle scoping document CSV upload and generate test suite."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = file.filename.lower()
    
    # Only accept CSV files
    if not filename.endswith('.csv'):
        return jsonify({'error': 'Invalid file format. Please upload a CSV scoping document.'}), 400
    
    try:
        content = file.read().decode('utf-8')
        
        # Parse scoping document CSV and generate test cases
        scoping_doc = ScopingParser.load_from_string(content)
        
        # Configure generator
        generator_config = GeneratorConfig(
            merchant_id=request.form.get('merchant_id', 'matrix_test'),
            environment=request.form.get('environment', 'sandbox'),
            test_suite_name=request.form.get('suite_name'),
            only_implemented=request.form.get('only_implemented', 'false').lower() == 'true'
        )
        
        generator = TestCaseGenerator(generator_config)
        hierarchical_suite = generator.generate_hierarchical_test_suite(scoping_doc)
        test_suite = hierarchical_suite.to_flat_test_suite()
        
        # Store the test suite
        suite_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        uploaded_suites[suite_id] = test_suite
        
        # Build hierarchical structure for response
        hierarchy = []
        for pm_group in hierarchical_suite.payment_methods:
            pm_data = {
                'id': pm_group.payment_method_id,
                'name': pm_group.payment_method,
                'providers': []
            }
            
            for provider_group in pm_group.providers:
                provider_data = {
                    'id': provider_group.provider_id,
                    'name': provider_group.provider,
                    'integration_id': provider_group.integration_id,
                    'test_cases': [
                        {
                            'id': tc.id,
                            'name': tc.name,
                            'description': tc.description,
                            'steps': [
                                {
                                    'step_id': s.step_id,
                                    'operation': s.operation,
                                    'provider': s.provider,
                                    'description': s.description,
                                    'input_data': s.input_data,
                                    'capture_variables': s.capture_variables,
                                    'expected_status': s.expected_status
                                }
                                for s in tc.steps
                            ]
                        }
                        for tc in provider_group.test_cases
                    ]
                }
                pm_data['providers'].append(provider_data)
            
            hierarchy.append(pm_data)
        
        # Build response
        response_data = {
            'suite_id': suite_id,
            'hierarchy': hierarchy,
            'test_suite': {
                'version': test_suite.version,
                'metadata': {
                    'test_suite_name': test_suite.metadata.test_suite_name,
                    'merchant_id': test_suite.metadata.merchant_id,
                    'environment': test_suite.metadata.environment,
                    'created_at': test_suite.metadata.created_at
                }
            }
        }
        
        return jsonify(response_data)
        
    except ScopingParseError as e:
        return jsonify({'error': f'Invalid scoping document: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@app.route('/api/update-payload', methods=['POST'])
def update_payload():
    """
    Update the input_data for all first steps in a test suite with the Builder payload.
    
    The payload is applied as-is to all test cases' first step, with only the provider
    metadata being modified to match each test case's provider.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    suite_id = data.get('suite_id')
    payload = data.get('payload')
    
    if not suite_id or suite_id not in uploaded_suites:
        return jsonify({'error': 'Test suite not found'}), 404
    
    if not payload:
        return jsonify({'error': 'No payload provided'}), 400
    
    test_suite = uploaded_suites[suite_id]
    
    # Apply payload to first step of each test case
    # Only modify the provider metadata to match the test case's provider
    import copy
    for test_case in test_suite.test_cases:
        if test_case.steps:
            # Deep copy the payload so each test case has its own copy
            step_payload = copy.deepcopy(payload)
            
            # Get the provider from the test case's first step
            provider = test_case.steps[0].provider
            
            # Generate a unique merchant_order_id for each test case
            # This prevents duplicate order ID errors across providers
            step_payload["merchant_order_id"] = str(uuid.uuid4())
            
            # Update only the provider in metadata
            if "metadata" not in step_payload:
                step_payload["metadata"] = []
            
            # Update existing provider metadata or add new one
            provider_updated = False
            for m in step_payload["metadata"]:
                if m.get("key") == "provider":
                    m["value"] = provider
                    provider_updated = True
                    break
            
            if not provider_updated:
                step_payload["metadata"].append({"key": "provider", "value": provider})
            
            # Replace the step's input_data with the user's payload
            test_case.steps[0].input_data = step_payload
    
    return jsonify({'success': True, 'message': f'Payload applied to {len(test_suite.test_cases)} test cases'})


@app.route('/api/update-provider-cards', methods=['POST'])
def update_provider_cards():
    """
    Update provider-specific test cards for a test suite.
    
    These cards will be used instead of the default card from the Builder payload
    when making payment API calls to specific providers.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    suite_id = data.get('suite_id')
    cards = data.get('cards', {})  # {provider_id: {number, expiration_month, expiration_year, security_code, holder_name}}
    
    if not suite_id or suite_id not in uploaded_suites:
        return jsonify({'error': 'Test suite not found'}), 404
    
    # Validate and store provider test cards
    validated_cards = {}
    for provider_id, card_data in cards.items():
        if card_data and card_data.get('number'):  # Only store if card number is provided
            try:
                validated_cards[provider_id.lower()] = ProviderTestCard(
                    number=card_data.get('number', ''),
                    expiration_month=int(card_data.get('expiration_month', 12)),
                    expiration_year=int(card_data.get('expiration_year', 27)),
                    security_code=card_data.get('security_code', '123'),
                    holder_name=card_data.get('holder_name', 'TEST USER')
                )
            except Exception as e:
                return jsonify({'error': f'Invalid card data for provider {provider_id}: {str(e)}'}), 400
    
    provider_test_cards_storage[suite_id] = validated_cards
    
    return jsonify({
        'success': True, 
        'message': f'Test cards configured for {len(validated_cards)} providers',
        'providers': list(validated_cards.keys())
    })


def execute_test_case_streaming(test_case: TestCase, api_client: APIClient, 
                                 context: ExecutionContext, logger: CertificationLogger) -> TestCaseResult:
    """Execute a single test case and return result."""
    logger.log_test_case_start(test_case)
    start_ms = time.time() * 1000
    
    step_results = []
    overall_status = "pass"
    error_msg = None
    
    for step in test_case.steps:
        try:
            result = execute_step(test_case, step, api_client, context, logger)
            step_results.append(result)
            if result.status in ("failure", "error"):
                overall_status = "fail" if result.status == "failure" else "error"
                error_msg = result.error_message
                break
        except Exception as e:
            overall_status = "error"
            error_msg = str(e)
            step_results.append(StepResult(
                step_id=step.step_id, operation=step.operation,
                provider=step.provider, status="error", error_message=str(e)
            ))
            break
    
    duration_ms = int((time.time() * 1000) - start_ms)
    result = TestCaseResult(
        test_case_id=test_case.id, test_case_name=test_case.name,
        status=overall_status, steps=step_results,
        duration_ms=duration_ms, error_message=error_msg
    )
    
    logger.log_test_case_end(test_case.id, result)
    return result


def execute_step(test_case: TestCase, step: Step, api_client: APIClient,
                 context: ExecutionContext, logger: CertificationLogger) -> StepResult:
    """Execute a single step."""
    from colorama import Fore, Style
    
    start_ms = time.time() * 1000
    response = None
    request_obj = None
    
    print(f"\n{Fore.CYAN}[DEBUG] Executing step {step.step_id}: {step.operation} for {step.provider}{Style.RESET_ALL}")
    
    # Log context variables for operations that depend on previous steps
    if step.operation in ('capture', 'refund', 'cancel', 'void'):
        all_vars = context.get_all_variables()
        print(f"{Fore.MAGENTA}[DEBUG] Context variables available: {json.dumps({k: str(v) for k, v in all_vars.items()}, indent=2)}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[DEBUG] Raw input data (before substitution): {json.dumps(step.input_data, indent=2, default=str)}{Style.RESET_ALL}")
    
    try:
        # Substitute variables in input data
        substituted_data = context.substitute_variables(step.input_data)
        
        print(f"{Fore.YELLOW}[DEBUG] Substituted request data: {json.dumps(substituted_data, indent=2, default=str)}{Style.RESET_ALL}")
        
        # Execute API call first to get the actual URL
        print(f"{Fore.YELLOW}[DEBUG] Making API call for operation: {step.operation}{Style.RESET_ALL}")
        response = api_client.execute_operation(step.operation, step.provider, substituted_data)
        
        # Create API request object for logging using the actual URL from the response
        actual_url = response.request_url or f"{api_client.yuno_base_url}/payments"
        request_obj = APIRequest(
            method="POST", url=actual_url,
            headers={"Content-Type": "application/json"}, body=substituted_data
        )
        
        print(f"{Fore.BLUE}[DEBUG] API Response Status Code: {response.status_code}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}[DEBUG] API Response Body: {json.dumps(response.body, indent=2) if response.body else 'None'}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}[DEBUG] API Response is_success: {response.is_success}{Style.RESET_ALL}")
        
        # Capture variables from response
        captured_vars = {}
        if step.capture_variables and response.body:
            print(f"{Fore.MAGENTA}[DEBUG] Attempting to capture variables: {list(step.capture_variables.keys())}{Style.RESET_ALL}")
            captured_vars = context.capture_variables_from_response(
                {"body": response.body}, step.capture_variables
            )
            print(f"{Fore.GREEN}[DEBUG] Successfully captured: {captured_vars}{Style.RESET_ALL}")
        
        duration_ms = int((time.time() * 1000) - start_ms)
        status = "success" if response.is_success else "failure"
        
        result = StepResult(
            step_id=step.step_id, operation=step.operation, provider=step.provider,
            status=status, request=request_obj, response=response, duration_ms=duration_ms,
            captured_variables=captured_vars if captured_vars else None
        )
        
        print(f"{Fore.GREEN}[DEBUG] Step completed with status: {status}, response attached: {result.response is not None}{Style.RESET_ALL}")
        
        logger.log_step(test_case.id, test_case.name, step, request_obj, response,
                       status, duration_ms, captured_variables=captured_vars)
        return result
        
    except ContextError as e:
        duration_ms = int((time.time() * 1000) - start_ms)
        error_msg = f"Context error: {str(e)}"
        print(f"{Fore.RED}[DEBUG] ContextError occurred: {error_msg}{Style.RESET_ALL}")
        print(f"{Fore.RED}[DEBUG] Response available: {response is not None}{Style.RESET_ALL}")
        if response:
            print(f"{Fore.RED}[DEBUG] Response body at error time: {json.dumps(response.body, indent=2) if response.body else 'None'}{Style.RESET_ALL}")
        
        # Include response if available so user can see what the API returned
        result = StepResult(
            step_id=step.step_id, operation=step.operation, provider=step.provider,
            status="error", duration_ms=duration_ms, error_message=error_msg,
            request=request_obj, response=response
        )
        
        print(f"{Fore.RED}[DEBUG] StepResult created with response attached: {result.response is not None}{Style.RESET_ALL}")
        if result.response:
            print(f"{Fore.RED}[DEBUG] StepResult.response.body: {result.response.body}{Style.RESET_ALL}")
        
        logger.log_step(test_case.id, test_case.name, step, request_obj, response,
                       "error", duration_ms, error_message=error_msg)
        return result
    except Exception as e:
        duration_ms = int((time.time() * 1000) - start_ms)
        error_msg = f"Execution error: {str(e)}"
        print(f"{Fore.RED}[DEBUG] Exception occurred: {error_msg}{Style.RESET_ALL}")
        print(f"{Fore.RED}[DEBUG] Response available: {response is not None}{Style.RESET_ALL}")
        
        # Include response if available so user can see what the API returned
        result = StepResult(
            step_id=step.step_id, operation=step.operation, provider=step.provider,
            status="error", duration_ms=duration_ms, error_message=error_msg,
            request=request_obj, response=response
        )
        logger.log_step(test_case.id, test_case.name, step, request_obj, response,
                       "error", duration_ms, error_message=error_msg)
        return result


@app.route('/execute-stream')
def execute_stream():
    """Execute test suite with SSE streaming."""
    suite_id = request.args.get('suite_id')
    test_case_ids_param = request.args.get('test_case_ids', '')
    
    if not suite_id or suite_id not in uploaded_suites:
        def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Test suite not found'})}\n\n"
        return Response(error_stream(), mimetype='text/event-stream')
    
    test_suite = uploaded_suites[suite_id]
    
    # Filter test cases if specific IDs are provided
    if test_case_ids_param:
        selected_ids = set(test_case_ids_param.split(','))
        test_cases_to_run = [tc for tc in test_suite.test_cases if tc.id in selected_ids]
    else:
        test_cases_to_run = test_suite.test_cases
    
    def generate():
        try:
            # Load config
            config = load_config()
            
            # Merge provider test cards from storage into config
            if suite_id in provider_test_cards_storage:
                config.provider_test_cards = provider_test_cards_storage[suite_id]
            
            # Generate execution ID
            execution_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Initialize components
            api_client = APIClient(config)
            logger = CertificationLogger(execution_id, "logs")
            context = ExecutionContext()
            
            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'execution_id': execution_id, 'total': len(test_cases_to_run)})}\n\n"
            
            # Execute each selected test case
            for test_case in test_cases_to_run:
                context.clear()
                
                # Send test case start event
                yield f"data: {json.dumps({'type': 'test_case_start', 'test_case_id': test_case.id, 'test_case_name': test_case.name})}\n\n"
                
                # Execute test case
                result = execute_test_case_streaming(test_case, api_client, context, logger)
                
                # Build step data with debug logging
                from colorama import Fore, Style
                steps_data = []
                for s in result.steps:
                    step_data = {
                        'step_id': s.step_id,
                        'operation': s.operation,
                        'status': s.status,
                        'duration_ms': s.duration_ms,
                        'error_message': s.error_message,
                        'captured_variables': s.captured_variables,
                        'request_method': s.request.method if s.request else None,
                        'request_url': s.request.url if s.request else None,
                        'request_body': s.request.body if s.request else None,
                        'response_status': s.response.body.get('status') if s.response and s.response.body else None,
                        'response_substatus': s.response.body.get('sub_status') if s.response and s.response.body else None,
                        'http_status_code': s.response.status_code if s.response else None,
                        'response_body': s.response.body if s.response else None,
                        'response_headers': s.response.headers if s.response else None
                    }
                    print(f"{Fore.CYAN}[SSE DEBUG] Step {s.step_id} - request: {step_data['request_method']} {step_data['request_url']}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}[SSE DEBUG] Step {s.step_id} - request_body being sent: {step_data['request_body']}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}[SSE DEBUG] Step {s.step_id} - response attached: {s.response is not None}{Style.RESET_ALL}")
                    print(f"{Fore.CYAN}[SSE DEBUG] Step {s.step_id} - response_body being sent: {step_data['response_body']}{Style.RESET_ALL}")
                    steps_data.append(step_data)
                
                # Send result event
                result_data = {
                    'type': 'test_case_result',
                    'result': {
                        'test_case_id': result.test_case_id,
                        'test_case_name': result.test_case_name,
                        'status': result.status,
                        'duration_ms': result.duration_ms,
                        'error_message': result.error_message,
                        'steps': steps_data
                    }
                }
                yield f"data: {json.dumps(result_data)}\n\n"
            
            logger.close()
            
            # Send complete event
            yield f"data: {json.dumps({'type': 'complete', 'execution_id': execution_id})}\n\n"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/download/<execution_id>')
def download_log(execution_id):
    """Download log file."""
    log_file = Path("logs") / f"execution_{execution_id}.json"
    
    if not log_file.exists():
        return jsonify({'error': 'Log file not found'}), 404
    
    return send_file(
        log_file,
        mimetype='application/json',
        as_attachment=True,
        download_name=f"execution_{execution_id}.json"
    )


# =============================================================================
# Payment Builder API Endpoints
# =============================================================================

@app.route('/api/payment-schema')
def get_payment_schema():
    """Return the Create Payment API schema for form generation."""
    try:
        schema_data = schema_to_json(CreatePaymentRequest)
        return jsonify(schema_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/validate-payment', methods=['POST'])
def validate_payment():
    """Validate a payment payload against the schema."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'valid': False, 'errors': ['No data provided']}), 400
        
        # Validate using Pydantic
        payment = CreatePaymentRequest(**data)
        return jsonify({
            'valid': True,
            'normalized': payment.model_dump(exclude_none=True)
        })
    except Exception as e:
        # Extract validation errors
        error_msg = str(e)
        return jsonify({
            'valid': False,
            'errors': [error_msg]
        }), 400


@app.route('/api/presets')
def get_payment_presets():
    """Return available payment presets/templates."""
    try:
        presets = get_presets()
        return jsonify({'presets': presets})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/datadog/query', methods=['POST'])
def query_datadog():
    """Query Datadog logs to retrieve payment request payload by trace_id."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        trace_id = data.get('trace_id')
        if not trace_id:
            return jsonify({
                'success': False,
                'error': 'trace_id is required'
            }), 400
        
        # Get optional date range
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        # Get Datadog client
        client = get_datadog_client()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Datadog API not configured. Please set DD_API_KEY and DD_APP_KEY environment variables.'
            }), 500
        
        # Query Datadog
        result = client.search_by_trace_id(
            trace_id=trace_id,
            date_from=date_from,
            date_to=date_to
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/datadog/status')
def datadog_status():
    """Check if Datadog API is configured."""
    client = get_datadog_client()
    return jsonify({
        'configured': client is not None
    })


@app.route('/e2e/start', methods=['POST'])
def e2e_start():
    """Initiate an E2E SDK Lite test flow.

    Creates a checkout session from the test case's payment data,
    stores the session for later payment processing, and returns
    the data needed to render the SDK Lite page.
    """
    import copy as _copy
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    suite_id = data.get('suite_id')
    test_case_id = data.get('test_case_id')
    provider = data.get('provider')

    if not suite_id or suite_id not in uploaded_suites:
        return jsonify({'error': 'Test suite not found'}), 404

    test_suite = uploaded_suites[suite_id]

    # Find the test case
    test_case = None
    for tc in test_suite.test_cases:
        if tc.id == test_case_id:
            test_case = tc
            break

    if not test_case:
        return jsonify({'error': f'Test case {test_case_id} not found'}), 404

    # Get payment data from the first step
    if not test_case.steps or not test_case.steps[0].input_data:
        return jsonify({'error': 'Test case has no payment data in first step'}), 400

    payment_data = _copy.deepcopy(test_case.steps[0].input_data)

    # Create checkout session
    config = load_config()
    if suite_id in provider_test_cards_storage:
        config.provider_test_cards = provider_test_cards_storage[suite_id]
    api_client = APIClient(config)

    # Auto-create a Yuno customer if customer_payer.id is missing
    customer_payer = payment_data.get("customer_payer") or {}
    if not customer_payer.get("id"):
        if not customer_payer:
            customer_payer = {"email": "matrix-e2e@y.uno", "first_name": "MATRIX", "last_name": "E2E Test"}
            payment_data["customer_payer"] = customer_payer

        customer_response = api_client.create_customer(customer_payer)
        if not customer_response.is_success:
            return jsonify({
                'error': 'Failed to create customer for E2E checkout',
                'details': customer_response.body
            }), 400

        customer_id = customer_response.body.get("id")
        if not customer_id:
            return jsonify({'error': 'No customer id returned from Yuno API'}), 500

        payment_data["customer_payer"]["id"] = customer_id

    checkout_response = api_client.create_checkout_session(payment_data)

    if not checkout_response.is_success:
        return jsonify({
            'error': 'Failed to create checkout session',
            'details': checkout_response.body
        }), 400

    checkout_session = checkout_response.body.get('checkout_session')
    if not checkout_session:
        return jsonify({'error': 'No checkout_session in API response'}), 500

    # Store session data for later payment processing
    e2e_session_id = str(uuid.uuid4())
    e2e_sessions[e2e_session_id] = {
        'payment_data': payment_data,
        'checkout_session': checkout_session,
        'provider': provider,
        'suite_id': suite_id,
        'test_case_id': test_case_id,
        'created_at': datetime.utcnow().isoformat(),
    }

    return jsonify({
        'e2e_session_id': e2e_session_id,
        'checkout_session': checkout_session,
        'country': payment_data.get('country', 'US'),
        'public_api_key': api_client.yuno_public_key,
    })


@app.route('/e2e/checkout/<e2e_session_id>')
def e2e_checkout(e2e_session_id):
    """Serve the SDK Lite checkout page for an E2E session."""
    session = e2e_sessions.get(e2e_session_id)
    if not session:
        return "E2E session not found or expired", 404

    config = load_config()
    api_client = APIClient(config)

    return render_template_string(
        E2E_CHECKOUT_TEMPLATE,
        public_api_key=api_client.yuno_public_key,
        checkout_session=session['checkout_session'],
        country_code=session['payment_data'].get('country', 'US'),
        e2e_session_id=e2e_session_id,
        provider=session['provider'],
        language='en',
    )


@app.route('/e2e/payment', methods=['POST'])
def e2e_payment():
    """Process an E2E SDK payment using the OTT from the SDK Lite callback."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    e2e_session_id = data.get('e2e_session_id')
    one_time_token = data.get('one_time_token')

    if not e2e_session_id or e2e_session_id not in e2e_sessions:
        return jsonify({'error': 'E2E session not found or expired'}), 404

    if not one_time_token:
        return jsonify({'error': 'one_time_token is required'}), 400

    session = e2e_sessions[e2e_session_id]

    config = load_config()
    suite_id = session.get('suite_id')
    if suite_id and suite_id in provider_test_cards_storage:
        config.provider_test_cards = provider_test_cards_storage[suite_id]
    api_client = APIClient(config)

    result = api_client.e2e_create_payment(
        provider=session['provider'],
        data=session['payment_data'],
        one_time_token=one_time_token,
        checkout_session=session['checkout_session'],
    )

    # Clean up the session
    del e2e_sessions[e2e_session_id]

    return jsonify({
        'status_code': result.status_code,
        'body': result.body,
        'error': result.error,
        'duration_ms': result.duration_ms,
        'request_url': result.request_url,
    })


@app.route('/builder')
def payment_builder():
    """Serve the Payment Request Builder page."""
    return render_template_string(BUILDER_TEMPLATE)


# Payment Builder HTML Template
BUILDER_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MATRIX - Payment Builder</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f7fa;
            color: #333;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        h1 {
            font-size: 2rem;
            font-weight: 600;
            color: #1a1a2e;
            margin-bottom: 8px;
        }
        
        .subtitle {
            color: #666;
            font-size: 1rem;
        }
        
        .nav-link {
            color: #4f46e5;
            text-decoration: none;
            font-size: 0.9rem;
        }
        
        .nav-link:hover {
            text-decoration: underline;
        }
        
        .builder-layout {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }
        
        @media (max-width: 900px) {
            .builder-layout {
                grid-template-columns: 1fr;
            }
        }
        
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            padding: 24px;
            margin-bottom: 24px;
        }
        
        .card h2 {
            font-size: 1.1rem;
            color: #1a1a2e;
            margin-bottom: 16px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .card h2 .badge {
            background: #4f46e5;
            color: white;
            font-size: 0.7rem;
            padding: 2px 8px;
            border-radius: 10px;
            font-weight: 500;
        }
        
        /* Field Groups */
        .field-group {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-bottom: 12px;
            overflow: hidden;
        }
        
        .field-group-header {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 16px;
            background: #f9fafb;
            cursor: pointer;
            user-select: none;
        }
        
        .field-group-header:hover {
            background: #f3f4f6;
        }
        
        .field-group-header .expand-icon {
            font-size: 0.8rem;
            color: #666;
            transition: transform 0.2s;
        }
        
        .field-group.expanded .field-group-header .expand-icon {
            transform: rotate(90deg);
        }
        
        .field-group-title {
            font-weight: 600;
            color: #1a1a2e;
            flex: 1;
        }
        
        .field-group-badge {
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 4px;
            background: #e5e7eb;
            color: #666;
        }
        
        .field-group-badge.required {
            background: #fef3c7;
            color: #92400e;
        }
        
        .field-group-content {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }
        
        .field-group.expanded .field-group-content {
            max-height: 2000px;
        }
        
        .field-group-inner {
            padding: 16px;
            border-top: 1px solid #e5e7eb;
        }
        
        /* Fields */
        .field-row {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 10px 0;
            border-bottom: 1px solid #f3f4f6;
        }
        
        .field-row:last-child {
            border-bottom: none;
        }
        
        .field-checkbox {
            flex-shrink: 0;
            padding-top: 2px;
        }
        
        .field-checkbox input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: #4f46e5;
        }
        
        .field-content {
            flex: 1;
            min-width: 0;
        }
        
        .field-label {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 6px;
        }
        
        .field-label-text {
            font-weight: 500;
            color: #1a1a2e;
            font-size: 0.9rem;
        }
        
        .field-label .required-star {
            color: #dc2626;
            font-weight: bold;
        }
        
        .field-label .field-type {
            font-size: 0.75rem;
            color: #888;
            font-family: monospace;
        }
        
        .field-description {
            font-size: 0.8rem;
            color: #666;
            margin-bottom: 8px;
        }
        
        .field-input {
            width: 100%;
        }
        
        .field-input input,
        .field-input select,
        .field-input textarea {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-size: 0.9rem;
            font-family: inherit;
        }
        
        .field-input input:focus,
        .field-input select:focus,
        .field-input textarea:focus {
            outline: none;
            border-color: #4f46e5;
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }
        
        .field-input input:disabled,
        .field-input select:disabled {
            background: #f9fafb;
            color: #9ca3af;
        }
        
        .field-input input.invalid {
            border-color: #dc2626;
        }
        
        /* Nested Fields */
        .nested-fields {
            margin-left: 24px;
            padding-left: 16px;
            border-left: 2px solid #e5e7eb;
            margin-top: 12px;
        }
        
        .nested-toggle {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 0;
            cursor: pointer;
            color: #4f46e5;
            font-size: 0.85rem;
            user-select: none;
        }
        
        .nested-toggle:hover {
            text-decoration: underline;
        }
        
        /* Preview Panel */
        .preview-panel {
            position: sticky;
            top: 20px;
        }
        
        .json-preview {
            background: #1a1a2e;
            color: #a5f3fc;
            padding: 16px;
            border-radius: 8px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.8rem;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 600px;
            overflow-y: auto;
        }
        
        /* Actions */
        .actions {
            display: flex;
            gap: 12px;
            margin-top: 20px;
        }
        
        .btn {
            display: inline-block;
            padding: 12px 24px;
            font-size: 1rem;
            font-weight: 500;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: #4f46e5;
            color: white;
        }
        
        .btn-primary:hover {
            background: #4338ca;
        }
        
        .btn-secondary {
            background: #e5e7eb;
            color: #333;
        }
        
        .btn-secondary:hover {
            background: #d1d5db;
        }
        
        .btn-success {
            background: #059669;
            color: white;
        }
        
        .btn-success:hover {
            background: #047857;
        }
        
        /* Tab Navigation */
        .tabs {
            display: flex;
            gap: 4px;
            margin-bottom: 20px;
            background: #f3f4f6;
            padding: 4px;
            border-radius: 8px;
        }
        
        .tab {
            flex: 1;
            padding: 10px 16px;
            text-align: center;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            color: #666;
            transition: all 0.2s;
        }
        
        .tab:hover {
            color: #333;
        }
        
        .tab.active {
            background: white;
            color: #4f46e5;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        /* JSON Input */
        .json-input {
            width: 100%;
            min-height: 400px;
            padding: 16px;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.85rem;
            resize: vertical;
        }
        
        .json-input:focus {
            outline: none;
            border-color: #4f46e5;
        }
        
        /* Validation Message */
        .validation-msg {
            padding: 12px 16px;
            border-radius: 8px;
            margin-top: 16px;
            display: none;
        }
        
        .validation-msg.success {
            display: block;
            background: #d1fae5;
            color: #059669;
        }
        
        .validation-msg.error {
            display: block;
            background: #fee2e2;
            color: #dc2626;
        }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .spinner {
            display: inline-block;
            width: 24px;
            height: 24px;
            border: 3px solid #e5e7eb;
            border-top-color: #4f46e5;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Payment Request Builder</h1>
            <p class="subtitle">Build and validate Create Payment API requests</p>
            <p style="margin-top: 8px;"><a href="/" class="nav-link">← Back to Test Runner</a></p>
        </header>
        
        <!-- Presets Section -->
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px; padding: 16px; background: #f9fafb; border-radius: 8px;">
            <label style="font-weight: 500; color: #1a1a2e; white-space: nowrap;">Load Preset:</label>
            <select id="preset-select" onchange="applySelectedPreset()" style="flex: 1; max-width: 300px; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; background: white;">
                <option value="">-- Select a preset --</option>
            </select>
            <span id="preset-description" style="color: #666; font-size: 0.85rem; flex: 1;"></span>
        </div>
        
        <div class="tabs">
            <div class="tab active" onclick="switchTab('interactive')">Interactive Form</div>
            <div class="tab" onclick="switchTab('json')">Paste JSON</div>
            <div class="tab" onclick="switchTab('datadog')">Query Datadog</div>
        </div>
        
        <div class="builder-layout">
            <!-- Form Panel -->
            <div class="form-panel">
                <!-- Interactive Form Tab -->
                <div id="tab-interactive" class="tab-content active">
                    <div class="card">
                        <h2>Build Payment Request</h2>
                        <div id="form-loading" class="loading">
                            <div class="spinner"></div>
                            <p style="margin-top: 12px;">Loading schema...</p>
                        </div>
                        <div id="form-container" style="display: none;"></div>
                    </div>
                </div>
                
                <!-- JSON Paste Tab -->
                <div id="tab-json" class="tab-content">
                    <div class="card">
                        <h2>Paste JSON Payload</h2>
                        <textarea id="json-input" class="json-input" placeholder="Paste your JSON payment request here..."></textarea>
                        <div class="actions">
                            <button class="btn btn-primary" onclick="parseJsonInput()">Parse & Validate</button>
                            <button class="btn btn-secondary" onclick="formatJson()">Format JSON</button>
                        </div>
                        <div id="json-validation" class="validation-msg"></div>
                    </div>
                </div>
                
                <!-- Datadog Query Tab -->
                <div id="tab-datadog" class="tab-content">
                    <div class="card">
                        <h2>Query Payment from Datadog</h2>
                        <p style="color: #666; margin-bottom: 20px;">
                            Retrieve a payment request payload from Datadog logs using the trace ID.
                        </p>
                        
                        <div id="datadog-not-configured" style="display: none; padding: 16px; background: #fef3c7; border-radius: 8px; margin-bottom: 16px;">
                            <strong style="color: #92400e;">Datadog API not configured</strong>
                            <p style="color: #92400e; margin-top: 4px; font-size: 0.9rem;">
                                Please set DD_API_KEY and DD_APP_KEY environment variables.
                            </p>
                        </div>
                        
                        <div id="datadog-form">
                            <div class="field-row" style="border-bottom: none; padding-bottom: 0;">
                                <div class="field-content">
                                    <div class="field-label">
                                        <span class="field-label-text">Trace ID</span>
                                        <span class="required-star">*</span>
                                    </div>
                                    <div class="field-description">The trace_id (UUID) from the payment request</div>
                                    <div class="field-input">
                                        <input type="text" id="datadog-trace-id" placeholder="e.g., bd22795e-f66c-477c-9e12-dce2259ceac4">
                                    </div>
                                </div>
                            </div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px;">
                                <div class="field-row" style="border-bottom: none; padding: 0;">
                                    <div class="field-content">
                                        <div class="field-label">
                                            <span class="field-label-text">Date From</span>
                                        </div>
                                        <div class="field-description">Start of date range (defaults to 7 days ago)</div>
                                        <div class="field-input">
                                            <input type="date" id="datadog-date-from">
                                        </div>
                                    </div>
                                </div>
                                <div class="field-row" style="border-bottom: none; padding: 0;">
                                    <div class="field-content">
                                        <div class="field-label">
                                            <span class="field-label-text">Date To</span>
                                        </div>
                                        <div class="field-description">End of date range (defaults to now)</div>
                                        <div class="field-input">
                                            <input type="date" id="datadog-date-to">
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="actions" style="margin-top: 20px;">
                                <button class="btn btn-primary" onclick="queryDatadog()" id="datadog-query-btn">
                                    Fetch Payload
                                </button>
                            </div>
                        </div>
                        
                        <div id="datadog-validation" class="validation-msg"></div>
                        
                        <div id="datadog-result" style="display: none; margin-top: 20px;">
                            <h3 style="font-size: 1rem; color: #1a1a2e; margin-bottom: 12px;">Retrieved Payload</h3>
                            <div id="datadog-payload-preview" class="json-preview" style="max-height: 300px;"></div>
                            <div class="actions" style="margin-top: 12px;">
                                <button class="btn btn-success" onclick="useDatadogPayload()">Use This Payload</button>
                                <button class="btn btn-secondary" onclick="copyDatadogPayload()">Copy JSON</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Preview Panel -->
            <div class="preview-panel">
                <div class="card">
                    <h2>JSON Preview <span class="badge">Live</span></h2>
                    <div id="json-preview" class="json-preview">{}</div>
                    <div class="actions">
                        <button class="btn btn-primary" onclick="copyToClipboard()">Copy JSON</button>
                        <button class="btn btn-success" onclick="usePayload()">Use This Payload</button>
                    </div>
                    <div id="preview-validation" class="validation-msg"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let schema = null;
        let presets = [];
        let fieldValues = {};
        let enabledFields = new Set();
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', () => {
            loadSchema();
            loadPresets();
            
            // Check for existing payload in sessionStorage (with delay to ensure it runs after schema loads)
            const savedPayload = sessionStorage.getItem('payment_payload');
            if (savedPayload) {
                // Use setTimeout to ensure this runs after schema load completes
                setTimeout(() => {
                    try {
                        // Format the JSON nicely and load into the JSON input
                        const parsed = JSON.parse(savedPayload);
                        document.getElementById('json-input').value = JSON.stringify(parsed, null, 2);
                        
                        // Switch to the JSON tab
                        switchTab('json');
                        
                        // Update the preview
                        document.getElementById('json-preview').textContent = JSON.stringify(parsed, null, 2);
                        
                        // Show a notice that payload was loaded
                        const validation = document.getElementById('json-validation');
                        validation.className = 'validation-msg success';
                        validation.textContent = 'Payload loaded from Test Runner. Edit as needed and click "Use This Payload" to save changes.';
                    } catch (e) {
                        console.error('Failed to load saved payload:', e);
                    }
                }, 100);
            }
        });
        
        async function loadSchema() {
            try {
                const response = await fetch('/api/payment-schema');
                schema = await response.json();
                renderForm();
            } catch (error) {
                document.getElementById('form-loading').innerHTML = 
                    '<p style="color: #dc2626;">Failed to load schema: ' + error.message + '</p>';
            }
        }
        
        async function loadPresets() {
            try {
                const response = await fetch('/api/presets');
                const data = await response.json();
                presets = data.presets || [];
                renderPresets();
            } catch (error) {
                document.getElementById('presets-loading').innerHTML = 
                    '<p style="color: #888;">Failed to load presets</p>';
            }
        }
        
        function renderPresets() {
            const select = document.getElementById('preset-select');
            
            if (presets.length === 0) {
                select.innerHTML = '<option value="">No presets available</option>';
            } else {
                const categoryIcons = {
                    'card': '💳',
                    'pix': '⚡',
                    'boleto': '📄',
                    'bank_transfer': '🏦'
                };
                
                const flags = {
                    'BR': '🇧🇷',
                    'MX': '🇲🇽',
                    'CO': '🇨🇴',
                    'CL': '🇨🇱',
                    'PE': '🇵🇪',
                    'AR': '🇦🇷',
                    'US': '🇺🇸'
                };
                
                select.innerHTML = '<option value="">-- Select a preset --</option>' + 
                    presets.map(preset => {
                        const icon = categoryIcons[preset.category] || '📦';
                        const flag = flags[preset.country] || '🌎';
                        return `<option value="${preset.id}">${flag} ${preset.name}</option>`;
                    }).join('');
            }
        }
        
        function applySelectedPreset() {
            const select = document.getElementById('preset-select');
            const descSpan = document.getElementById('preset-description');
            const presetId = select.value;
            
            if (!presetId) {
                descSpan.textContent = '';
                return;
            }
            
            const preset = presets.find(p => p.id === presetId);
            if (preset) {
                descSpan.textContent = preset.description;
                applyPreset(presetId);
            }
        }
        
        function applyPreset(presetId) {
            const preset = presets.find(p => p.id === presetId);
            if (!preset) return;
            
            // Clear current values
            fieldValues = {};
            enabledFields = new Set();
            
            // Apply preset payload
            applyPayloadToForm(preset.payload, '');
            
            // Update preview
            updatePreview();
            
            // Show confirmation
            const validation = document.getElementById('preview-validation');
            validation.className = 'validation-msg success';
            validation.textContent = `Applied preset: ${preset.name}`;
            setTimeout(() => { validation.className = 'validation-msg'; }, 3000);
        }
        
        function applyPayloadToForm(obj, prefix) {
            for (const [key, value] of Object.entries(obj)) {
                const path = prefix ? prefix + '.' + key : key;
                
                if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
                    applyPayloadToForm(value, path);
                } else if (value !== null && value !== undefined && value !== '') {
                    fieldValues[path] = value;
                    enabledFields.add(path);
                    
                    // Update input field and checkbox
                    const fieldId = path.replace(/\\./g, '-');
                    const input = document.getElementById('input-' + fieldId);
                    const checkbox = document.getElementById('cb-' + fieldId);
                    
                    if (input) {
                        if (input.type === 'checkbox') {
                            input.checked = value;
                        } else {
                            input.value = value;
                        }
                    }
                    if (checkbox) {
                        checkbox.checked = true;
                    }
                }
            }
        }
        
        function renderForm() {
            const container = document.getElementById('form-container');
            const groups = schema.groups || [];
            
            let html = '';
            
            groups.forEach(group => {
                const isExpanded = !group.collapsed;
                const requiredBadge = group.required ? 
                    '<span class="field-group-badge required">Required</span>' : 
                    '<span class="field-group-badge">' + group.fields.length + ' fields</span>';
                
                html += `
                    <div class="field-group ${isExpanded ? 'expanded' : ''}" id="group-${group.id}">
                        <div class="field-group-header" onclick="toggleGroup('${group.id}')">
                            <span class="expand-icon">▶</span>
                            <span class="field-group-title">${group.label}</span>
                            ${requiredBadge}
                        </div>
                        <div class="field-group-content">
                            <div class="field-group-inner">
                                ${renderFields(group.fields)}
                            </div>
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
            document.getElementById('form-loading').style.display = 'none';
            container.style.display = 'block';
            
            // Enable required fields by default
            schema.schema.required_fields.forEach(path => {
                enabledFields.add(path);
                const checkbox = document.getElementById('cb-' + path.replace(/\\./g, '-'));
                if (checkbox) checkbox.checked = true;
            });
            
            // Load example values
            if (schema.example) {
                loadExampleValues(schema.example, '');
            }
            
            updatePreview();
        }
        
        function renderFields(fields, parentPath = '') {
            let html = '';
            
            fields.forEach(field => {
                const fullPath = parentPath ? parentPath + '.' + field.name : field.name;
                const fieldId = fullPath.replace(/\\./g, '-');
                const isRequired = field.required;
                const hasChildren = field.children && field.children.length > 0;
                
                html += `
                    <div class="field-row" data-path="${fullPath}">
                        <div class="field-checkbox">
                            <input type="checkbox" id="cb-${fieldId}" 
                                   onchange="toggleField('${fullPath}')" 
                                   ${isRequired ? 'checked' : ''}>
                        </div>
                        <div class="field-content">
                            <div class="field-label">
                                <span class="field-label-text">${field.label}</span>
                                ${isRequired ? '<span class="required-star">*</span>' : ''}
                                <span class="field-type">${field.type}</span>
                            </div>
                            ${field.description ? '<div class="field-description">' + field.description + '</div>' : ''}
                            ${renderFieldInput(field, fullPath, fieldId)}
                            ${hasChildren ? renderNestedFields(field, fullPath) : ''}
                        </div>
                    </div>
                `;
            });
            
            return html;
        }
        
        function renderFieldInput(field, fullPath, fieldId) {
            if (field.type === 'object' || (field.children && field.children.length > 0)) {
                return ''; // Objects don't have direct inputs
            }
            
            if (field.type === 'array') {
                return '<div class="field-description" style="color: #4f46e5;">Array field - expand to add items</div>';
            }
            
            let inputHtml = '<div class="field-input">';
            
            if (field.options && field.options.length > 0) {
                // Select dropdown
                inputHtml += `<select id="input-${fieldId}" onchange="updateFieldValue('${fullPath}', this.value)">
                    <option value="">Select ${field.label}...</option>
                    ${field.options.map(opt => `<option value="${opt}">${opt}</option>`).join('')}
                </select>`;
            } else if (field.type === 'boolean') {
                // Checkbox for boolean
                inputHtml += `<label style="display: flex; align-items: center; gap: 8px;">
                    <input type="checkbox" id="input-${fieldId}" 
                           onchange="updateFieldValue('${fullPath}', this.checked)">
                    <span>Enable</span>
                </label>`;
            } else if (field.type === 'number' || field.type === 'integer') {
                // Number input
                inputHtml += `<input type="number" id="input-${fieldId}" 
                              placeholder="${field.placeholder || ''}"
                              step="${field.type === 'integer' ? '1' : '0.01'}"
                              onchange="updateFieldValue('${fullPath}', parseFloat(this.value))">`;
            } else {
                // Text input
                const inputType = field.is_sensitive ? 'password' : 'text';
                inputHtml += `<input type="${inputType}" id="input-${fieldId}" 
                              placeholder="${field.placeholder || ''}"
                              ${field.max_length ? 'maxlength="' + field.max_length + '"' : ''}
                              onchange="updateFieldValue('${fullPath}', this.value)">`;
            }
            
            inputHtml += '</div>';
            return inputHtml;
        }
        
        function renderNestedFields(field, parentPath) {
            if (!field.children || field.children.length === 0) return '';
            
            return `
                <div class="nested-fields">
                    ${renderFields(field.children, parentPath)}
                </div>
            `;
        }
        
        function toggleGroup(groupId) {
            const group = document.getElementById('group-' + groupId);
            if (group) {
                group.classList.toggle('expanded');
            }
        }
        
        function toggleField(path) {
            const fieldId = path.replace(/\\./g, '-');
            const checkbox = document.getElementById('cb-' + fieldId);
            
            if (checkbox.checked) {
                enabledFields.add(path);
            } else {
                enabledFields.delete(path);
                delete fieldValues[path];
            }
            
            updatePreview();
        }
        
        function updateFieldValue(path, value) {
            if (value === '' || value === null || value === undefined) {
                delete fieldValues[path];
            } else {
                fieldValues[path] = value;
                enabledFields.add(path);
                
                // Also check the checkbox
                const fieldId = path.replace(/\\./g, '-');
                const checkbox = document.getElementById('cb-' + fieldId);
                if (checkbox) checkbox.checked = true;
            }
            
            updatePreview();
        }
        
        function loadExampleValues(obj, prefix) {
            for (const [key, value] of Object.entries(obj)) {
                const path = prefix ? prefix + '.' + key : key;
                
                if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
                    loadExampleValues(value, path);
                } else {
                    fieldValues[path] = value;
                    
                    // Update input field
                    const fieldId = path.replace(/\\./g, '-');
                    const input = document.getElementById('input-' + fieldId);
                    if (input) {
                        if (input.type === 'checkbox') {
                            input.checked = value;
                        } else {
                            input.value = value;
                        }
                    }
                }
            }
        }
        
        function buildPayload() {
            const payload = {};
            
            for (const path of enabledFields) {
                const value = fieldValues[path];
                if (value !== undefined && value !== null && value !== '') {
                    setNestedValue(payload, path, value);
                }
            }
            
            return payload;
        }
        
        function setNestedValue(obj, path, value) {
            const parts = path.split('.');
            let current = obj;
            
            for (let i = 0; i < parts.length - 1; i++) {
                const part = parts[i];
                if (!(part in current)) {
                    current[part] = {};
                }
                current = current[part];
            }
            
            current[parts[parts.length - 1]] = value;
        }
        
        function updatePreview() {
            const payload = buildPayload();
            const preview = document.getElementById('json-preview');
            preview.textContent = JSON.stringify(payload, null, 2);
        }
        
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            const tabIndex = tab === 'interactive' ? 1 : (tab === 'json' ? 2 : 3);
            document.querySelector('.tab:nth-child(' + tabIndex + ')').classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');
            
            // Check Datadog config when switching to Datadog tab
            if (tab === 'datadog') {
                checkDatadogStatus();
            }
        }
        
        async function checkDatadogStatus() {
            try {
                const response = await fetch('/api/datadog/status');
                const data = await response.json();
                
                const notConfigured = document.getElementById('datadog-not-configured');
                const form = document.getElementById('datadog-form');
                
                if (!data.configured) {
                    notConfigured.style.display = 'block';
                    form.style.opacity = '0.5';
                    form.style.pointerEvents = 'none';
                } else {
                    notConfigured.style.display = 'none';
                    form.style.opacity = '1';
                    form.style.pointerEvents = 'auto';
                }
                
                // Pre-fill date inputs with today's date
                const today = new Date().toISOString().split('T')[0];
                const dateFrom = document.getElementById('datadog-date-from');
                const dateTo = document.getElementById('datadog-date-to');
                if (dateFrom && !dateFrom.value) dateFrom.value = today;
                if (dateTo && !dateTo.value) dateTo.value = today;
                
            } catch (error) {
                console.error('Failed to check Datadog status:', error);
            }
        }
        
        async function queryDatadog() {
            const traceId = document.getElementById('datadog-trace-id').value.trim();
            const dateFrom = document.getElementById('datadog-date-from').value;
            const dateTo = document.getElementById('datadog-date-to').value;
            const validation = document.getElementById('datadog-validation');
            const resultDiv = document.getElementById('datadog-result');
            const btn = document.getElementById('datadog-query-btn');
            
            if (!traceId) {
                validation.className = 'validation-msg error';
                validation.style.display = 'block';
                validation.textContent = 'Please enter a trace ID';
                return;
            }
            
            // UUID validation
            const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            if (!uuidPattern.test(traceId)) {
                validation.className = 'validation-msg error';
                validation.style.display = 'block';
                validation.textContent = 'Invalid trace ID format. Expected UUID format (e.g., bd22795e-f66c-477c-9e12-dce2259ceac4)';
                return;
            }
            
            // Show loading state
            btn.disabled = true;
            btn.textContent = 'Fetching...';
            validation.style.display = 'none';
            resultDiv.style.display = 'none';
            
            try {
                const body = { trace_id: traceId };
                
                // Add date range if provided
                if (dateFrom) {
                    body.date_from = dateFrom + 'T00:00:00Z';
                }
                if (dateTo) {
                    body.date_to = dateTo + 'T23:59:59Z';
                }
                
                const response = await fetch('/api/datadog/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                
                const result = await response.json();
                
                if (result.success && result.payload) {
                    // Show success
                    validation.className = 'validation-msg success';
                    validation.style.display = 'block';
                    validation.textContent = 'Found payload! (' + result.logs_count + ' logs searched)';
                    
                    // Show the payload
                    const previewDiv = document.getElementById('datadog-payload-preview');
                    previewDiv.textContent = JSON.stringify(result.payload, null, 2);
                    resultDiv.style.display = 'block';
                    
                    // Also update main preview
                    document.getElementById('json-preview').textContent = JSON.stringify(result.payload, null, 2);
                } else {
                    validation.className = 'validation-msg error';
                    validation.style.display = 'block';
                    validation.textContent = result.error || 'Failed to retrieve payload';
                    
                    // Show raw logs for debugging if available
                    if (result.raw_logs && result.raw_logs.length > 0) {
                        const previewDiv = document.getElementById('datadog-payload-preview');
                        previewDiv.textContent = '// RAW LOGS (for debugging):\\n' + JSON.stringify(result.raw_logs, null, 2);
                        resultDiv.style.display = 'block';
                        validation.textContent += ' - See raw logs below (' + result.logs_count + ' logs found)';
                    } else {
                        resultDiv.style.display = 'none';
                    }
                }
                
            } catch (error) {
                validation.className = 'validation-msg error';
                validation.style.display = 'block';
                validation.textContent = 'Request failed: ' + error.message;
                resultDiv.style.display = 'none';
            } finally {
                btn.disabled = false;
                btn.textContent = 'Fetch Payload';
            }
        }
        
        function useDatadogPayload() {
            const previewContent = document.getElementById('datadog-payload-preview').textContent;
            
            try {
                const payload = JSON.parse(previewContent);
                
                // Store in sessionStorage for use in test runner
                sessionStorage.setItem('payment_payload', JSON.stringify(payload));
                
                // Update main preview
                document.getElementById('json-preview').textContent = JSON.stringify(payload, null, 2);
                
                const validation = document.getElementById('datadog-validation');
                validation.className = 'validation-msg success';
                validation.textContent = 'Payload saved! You can now use it in the Test Runner.';
            } catch (e) {
                const validation = document.getElementById('datadog-validation');
                validation.className = 'validation-msg error';
                validation.textContent = 'Cannot save: Invalid JSON';
            }
        }
        
        function copyDatadogPayload() {
            const preview = document.getElementById('datadog-payload-preview');
            navigator.clipboard.writeText(preview.textContent).then(() => {
                alert('Copied to clipboard!');
            });
        }
        
        function parseJsonInput() {
            const input = document.getElementById('json-input');
            const validation = document.getElementById('json-validation');
            
            try {
                const parsed = JSON.parse(input.value);
                
                // Validate against API
                fetch('/api/validate-payment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(parsed)
                })
                .then(res => res.json())
                .then(result => {
                    if (result.valid) {
                        validation.className = 'validation-msg success';
                        validation.textContent = 'Valid payment request!';
                        document.getElementById('json-preview').textContent = 
                            JSON.stringify(result.normalized, null, 2);
                    } else {
                        validation.className = 'validation-msg error';
                        validation.textContent = 'Validation error: ' + result.errors.join(', ');
                    }
                });
            } catch (e) {
                validation.className = 'validation-msg error';
                validation.textContent = 'Invalid JSON: ' + e.message;
            }
        }
        
        function formatJson() {
            const input = document.getElementById('json-input');
            try {
                const parsed = JSON.parse(input.value);
                input.value = JSON.stringify(parsed, null, 2);
            } catch (e) {
                alert('Cannot format invalid JSON');
            }
        }
        
        function copyToClipboard() {
            const preview = document.getElementById('json-preview');
            navigator.clipboard.writeText(preview.textContent).then(() => {
                alert('Copied to clipboard!');
            });
        }
        
        function copyValue(value, btn) {
            navigator.clipboard.writeText(value).then(() => {
                const originalText = btn.innerHTML;
                btn.innerHTML = '✓ Copied';
                btn.classList.add('copied');
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.classList.remove('copied');
                }, 1500);
            });
        }
        
        function usePayload() {
            // Get payload from the JSON preview (works for both interactive form and pasted JSON)
            const previewContent = document.getElementById('json-preview').textContent;
            
            try {
                // Validate it's proper JSON
                const payload = JSON.parse(previewContent);
                
                // Store in sessionStorage for use in test runner
                sessionStorage.setItem('payment_payload', JSON.stringify(payload));
                
                const validation = document.getElementById('preview-validation');
                validation.className = 'validation-msg success';
                validation.textContent = 'Payload saved! You can now use it in the Test Runner.';
            } catch (e) {
                const validation = document.getElementById('preview-validation');
                validation.className = 'validation-msg error';
                validation.textContent = 'Cannot save: Invalid JSON in preview';
            }
        }
    </script>
</body>
</html>
"""

E2E_CHECKOUT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MATRIX - E2E SDK Lite Test</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f7fa;
            color: #333;
            min-height: 100vh;
        }
        .container { max-width: 720px; margin: 0 auto; padding: 40px 20px; }
        header { text-align: center; margin-bottom: 32px; }
        h1 { font-size: 2rem; font-weight: 600; color: #1a1a2e; margin-bottom: 4px; }
        .subtitle { color: #666; font-size: 0.95rem; }
        .provider-badge {
            display: inline-block;
            background: #7c3aed;
            color: white;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-top: 8px;
        }
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            padding: 24px;
            margin-bottom: 20px;
        }
        .card h2 { font-size: 1rem; color: #1a1a2e; margin-bottom: 14px; font-weight: 600; }
        .steps { display: flex; gap: 12px; margin-bottom: 8px; }
        .step-item {
            flex: 1;
            padding: 10px 12px;
            border-radius: 8px;
            background: #f0f0f5;
            text-align: center;
            font-size: 0.82rem;
            font-weight: 500;
            color: #888;
            transition: all 0.3s ease;
        }
        .step-item.active { background: #ede9fe; color: #7c3aed; font-weight: 600; }
        .step-item.done { background: #d1fae5; color: #059669; }
        .step-item.error { background: #fee2e2; color: #dc2626; }
        .step-num {
            display: inline-block;
            width: 20px; height: 20px;
            line-height: 20px;
            border-radius: 50%;
            background: #ccc;
            color: white;
            font-size: 0.7rem;
            margin-right: 4px;
            vertical-align: middle;
        }
        .step-item.active .step-num { background: #7c3aed; }
        .step-item.done .step-num { background: #059669; }
        .step-item.error .step-num { background: #dc2626; }
        #sdk-container {
            min-height: 240px;
            border: 2px dashed #e0e0e0;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #aaa;
            font-size: 0.9rem;
            position: relative;
        }
        #sdk-container.loaded { border: none; }
        #root { width: 100%; }
        #result-panel { display: none; }
        #result-panel.visible { display: block; }
        .result-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 14px;
        }
        .result-status {
            padding: 5px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .result-status.success { background: #d1fae5; color: #059669; }
        .result-status.failure { background: #fee2e2; color: #dc2626; }
        .result-status.pending { background: #fef3c7; color: #d97706; }
        .result-body {
            background: #1e1e2e;
            color: #e0e0e0;
            border-radius: 8px;
            padding: 16px;
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 0.8rem;
            line-height: 1.5;
            overflow-x: auto;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
        }
        .spinner {
            display: inline-block;
            width: 18px; height: 18px;
            border: 2px solid #ddd;
            border-top: 2px solid #7c3aed;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            vertical-align: middle;
            margin-right: 6px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .error-msg { color: #dc2626; font-size: 0.85rem; margin-top: 8px; }
        .back-link {
            display: inline-block;
            margin-top: 16px;
            color: #7c3aed;
            text-decoration: none;
            font-size: 0.9rem;
        }
        .back-link:hover { text-decoration: underline; }
        .duration { color: #999; font-size: 0.8rem; margin-left: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>MATRIX</h1>
            <p class="subtitle">E2E SDK Lite Test</p>
            <span class="provider-badge">{{ provider }}</span>
        </header>

        <div class="card">
            <h2>Flow Progress</h2>
            <div class="steps">
                <div class="step-item done" id="step-1">
                    <span class="step-num">1</span> Checkout Session
                </div>
                <div class="step-item active" id="step-2">
                    <span class="step-num">2</span> Card Input
                </div>
                <div class="step-item" id="step-3">
                    <span class="step-num">3</span> Payment
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Enter Card Details</h2>
            <div id="sdk-container">
                <div id="root"></div>
            </div>
            <p class="error-msg" id="sdk-error" style="display:none;"></p>
        </div>

        <div class="card" id="result-panel">
            <h2>Payment Result</h2>
            <div class="result-header">
                <span class="result-status" id="result-status"></span>
                <span class="duration" id="result-duration"></span>
            </div>
            <div class="result-body" id="result-body"></div>
        </div>

        <a class="back-link" href="/">&larr; Back to MATRIX</a>
    </div>

    <script src="https://sdk-web.y.uno/v1/static/js/main.min.js"></script>
    <script>
        const E2E_SESSION_ID = '{{ e2e_session_id }}';
        const CHECKOUT_SESSION = '{{ checkout_session }}';
        const PUBLIC_API_KEY = '{{ public_api_key }}';
        const COUNTRY_CODE = '{{ country_code }}';
        const LANGUAGE = '{{ language }}';

        function setStep(num, state) {
            const el = document.getElementById('step-' + num);
            el.className = 'step-item ' + state;
        }

        function displayResult(data) {
            const panel = document.getElementById('result-panel');
            const status = document.getElementById('result-status');
            const body = document.getElementById('result-body');
            const dur = document.getElementById('result-duration');

            panel.classList.add('visible');

            const paymentStatus = (data.body && data.body.status) || '';
            const isSuccess = data.status_code >= 200 && data.status_code < 300;
            const isPending = paymentStatus === 'PENDING';

            if (isPending) {
                status.textContent = paymentStatus;
                status.className = 'result-status pending';
            } else if (isSuccess) {
                status.textContent = paymentStatus || 'SUCCESS';
                status.className = 'result-status success';
            } else {
                status.textContent = data.error || 'FAILED';
                status.className = 'result-status failure';
            }

            if (data.duration_ms) {
                dur.textContent = data.duration_ms + 'ms';
            }

            body.textContent = JSON.stringify(data.body, null, 2);
        }

        function displayError(error) {
            const errEl = document.getElementById('sdk-error');
            errEl.style.display = 'block';
            errEl.textContent = typeof error === 'string' ? error : JSON.stringify(error);
            setStep(2, 'error');
        }

        (async function() {
            try {
                const yuno = await Yuno.initialize(PUBLIC_API_KEY);

                yuno.startCheckout({
                    checkoutSession: CHECKOUT_SESSION,
                    elementSelector: '#root',
                    countryCode: COUNTRY_CODE,
                    language: LANGUAGE,
                    showLoading: true,
                    showPaymentStatus: false,
                    renderMode: {
                        type: 'element',
                        elementSelector: '#root'
                    },
                    card: {
                        type: 'step'
                    },
                    async yunoCreatePayment(oneTimeToken) {
                        setStep(2, 'done');
                        setStep(3, 'active');

                        try {
                            const response = await fetch('/e2e/payment', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    e2e_session_id: E2E_SESSION_ID,
                                    one_time_token: oneTimeToken
                                })
                            });
                            const result = await response.json();
                            displayResult(result);

                            const ok = result.status_code >= 200 && result.status_code < 300;
                            setStep(3, ok ? 'done' : 'error');

                            yuno.continuePayment({ showPaymentStatus: true });
                        } catch (err) {
                            setStep(3, 'error');
                            displayError('Payment request failed: ' + err.message);
                        }
                    },
                    yunoError(error) {
                        displayError(error);
                    }
                });

                yuno.mountCheckoutLite({ paymentMethodType: 'CARD' });
                document.getElementById('sdk-container').classList.add('loaded');
            } catch (err) {
                displayError('SDK initialization failed: ' + err.message);
            }
        })();
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("\n" + "="*60)
    print("MATRIX Web Interface")
    print("="*60)
    print("Open http://localhost:5001 in your browser")
    print("="*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5001)
