#!/usr/bin/env python3
"""MATRIX Web Interface - Simple web UI for test case execution."""

import json
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file, Response

from src.scoping_parser import ScopingParser, ScopingParseError
from src.test_generator import TestCaseGenerator, GeneratorConfig
from src.api_client import APIClient
from src.logger import CertificationLogger
from src.context import ExecutionContext, ContextError
from src.models import Config, TestSuite, TestCase, Step, StepResult, TestCaseResult, APIRequest
from src.schemas import CreatePaymentRequest, get_presets
from src.schemas.schema_utils import schema_to_json

app = Flask(__name__)

# Store uploaded test suites in memory (for simplicity)
uploaded_suites = {}

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
                <button onclick="clearBuilderPayload()" style="background: none; border: 1px solid #10b981; color: #059669; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">Clear</button>
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
        
        // Check for saved payload from builder on page load
        document.addEventListener('DOMContentLoaded', () => {
            const savedPayload = sessionStorage.getItem('payment_payload');
            if (savedPayload) {
                document.getElementById('saved-payload-notice').classList.remove('hidden');
            }
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
                        // Apply to first step of all test cases
                        currentSuite.test_cases.forEach(tc => {
                            if (tc.steps.length > 0) {
                                tc.steps[0].input_data = payload;
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
                            </div>
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
                
                let captureVarsHtml = '';
                if (stepResult?.captured_variables && Object.keys(stepResult.captured_variables).length > 0) {
                    captureVarsHtml = `<div class="step-section">
                        <div class="step-section-label">Captured Values</div>
                        <div class="capture-vars">
                            ${Object.entries(stepResult.captured_variables).map(([name, value]) => 
                                `<span class="capture-var captured">${name} = ${JSON.stringify(value)}</span>`
                            ).join('')}
                        </div>
                    </div>`;
                } else if (step.capture_variables && Object.keys(step.capture_variables).length > 0) {
                    captureVarsHtml = `<div class="step-section">
                        <div class="step-section-label">Variables to Capture</div>
                        <div class="capture-vars">
                            ${Object.entries(step.capture_variables).map(([name, path]) => 
                                `<span class="capture-var">${name} ← ${path}</span>`
                            ).join('')}
                        </div>
                    </div>`;
                }
                
                const errorHtml = stepResult?.error_message 
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
                            ${responseHtml}
                            ${captureVarsHtml}
                            ${step.expected_status ? `<div class="step-section">
                                <div class="step-section-label">Expected Status</div>
                                <span style="color:#059669;font-weight:500">${step.expected_status}</span>
                            </div>` : ''}
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
                    
                    // Show captured values if we have results, otherwise show the JSONPath specs
                    let captureVarsHtml = '';
                    if (stepResult?.captured_variables && Object.keys(stepResult.captured_variables).length > 0) {
                        // Show actual captured values after execution
                        captureVarsHtml = `<div class="step-section">
                            <div class="step-section-label">Captured Values</div>
                            <div class="capture-vars">
                                ${Object.entries(stepResult.captured_variables).map(([name, value]) => 
                                    `<span class="capture-var captured">${name} = ${JSON.stringify(value)}</span>`
                                ).join('')}
                            </div>
                        </div>`;
                    } else if (step.capture_variables && Object.keys(step.capture_variables).length > 0) {
                        // Show JSONPath specs before execution
                        captureVarsHtml = `<div class="step-section">
                            <div class="step-section-label">Variables to Capture</div>
                            <div class="capture-vars">
                                ${Object.entries(step.capture_variables).map(([name, path]) => 
                                    `<span class="capture-var">${name} ← ${path}</span>`
                                ).join('')}
                            </div>
                        </div>`;
                    }
                    
                    const errorHtml = stepResult?.error_message 
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
                                ${responseHtml}
                                ${captureVarsHtml}
                                ${step.expected_status ? `<div class="step-section">
                                    <div class="step-section-label">Expected Status</div>
                                    <span style="color:#059669;font-weight:500">${step.expected_status}</span>
                                </div>` : ''}
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
                        
                        // Update captured variables section with actual values
                        if (stepResult.captured_variables && Object.keys(stepResult.captured_variables).length > 0) {
                            const bodyEl = stepEl.querySelector('.step-detail-body');
                            // Find existing capture vars section or create new one
                            let captureSection = bodyEl.querySelector('.step-section:has(.capture-vars)');
                            if (!captureSection) {
                                // Find the section by label text as fallback
                                const sections = bodyEl.querySelectorAll('.step-section');
                                sections.forEach(s => {
                                    const label = s.querySelector('.step-section-label');
                                    if (label && (label.textContent.includes('Capture') || label.textContent.includes('Variables'))) {
                                        captureSection = s;
                                    }
                                });
                            }
                            
                            const capturedHtml = `
                                <div class="step-section">
                                    <div class="step-section-label">Captured Values</div>
                                    <div class="capture-vars">
                                        ${Object.entries(stepResult.captured_variables).map(([name, value]) => 
                                            `<span class="capture-var captured">${name} = ${JSON.stringify(value)}</span>`
                                        ).join('')}
                                    </div>
                                </div>
                            `;
                            
                            if (captureSection) {
                                captureSection.outerHTML = capturedHtml;
                            } else {
                                // Insert before expected status or at end
                                const expectedSection = bodyEl.querySelector('.step-section:last-child');
                                if (expectedSection) {
                                    expectedSection.insertAdjacentHTML('beforebegin', capturedHtml);
                                } else {
                                    bodyEl.insertAdjacentHTML('beforeend', capturedHtml);
                                }
                            }
                        }
                        
                        // Add error message if present
                        if (stepResult.error_message) {
                            const errBodyEl = stepEl.querySelector('.step-detail-body');
                            if (errBodyEl && !errBodyEl.querySelector('.step-error-msg')) {
                                errBodyEl.insertAdjacentHTML('beforeend', `
                                    <div class="step-error-msg">${stepResult.error_message}</div>
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
            
            // Reset test case displays
            displayTestSuite(currentSuite);
            
            // Check if we have a saved payload from the Builder
            const savedPayload = sessionStorage.getItem('payment_payload');
            
            // Function to start the actual execution
            const startExecution = () => {
                const idsParam = encodeURIComponent(selectedIds.join(','));
                const eventSource = new EventSource(`/execute-stream?suite_id=${currentSuiteId}&test_case_ids=${idsParam}`);
                setupEventSource(eventSource);
            };
            
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
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serve the main page."""
    return render_template_string(HTML_TEMPLATE)

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
    
    try:
        # Substitute variables in input data
        substituted_data = context.substitute_variables(step.input_data)
        
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
                        'response_status': s.response.body.get('status') if s.response and s.response.body else None,
                        'response_substatus': s.response.body.get('sub_status') if s.response and s.response.body else None,
                        'http_status_code': s.response.status_code if s.response else None,
                        'response_body': s.response.body if s.response else None
                    }
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
            
            document.querySelector(`.tab:nth-child(${tab === 'interactive' ? 1 : 2})`).classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');
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

if __name__ == '__main__':
    print("\n" + "="*60)
    print("MATRIX Web Interface")
    print("="*60)
    print("Open http://localhost:5001 in your browser")
    print("="*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5001)
