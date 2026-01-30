#!/usr/bin/env python3
"""MATRIX Web Interface - Simple web UI for test case execution."""

import json
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file, Response

from src.parser import TestCaseParser, TestCaseParseError
from src.api_client import APIClient
from src.logger import CertificationLogger
from src.context import ExecutionContext, ContextError
from src.models import Config, TestSuite, TestCase, Step, StepResult, TestCaseResult, APIRequest

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
            <h2>Upload Test Case File</h2>
            <div class="upload-area" id="upload-area">
                <input type="file" id="file-input" accept=".json">
                <div class="upload-icon">📄</div>
                <p class="upload-text">
                    <strong>Click to upload</strong> or drag and drop<br>
                    <small>JSON test case file</small>
                </p>
            </div>
            <div id="upload-error" class="error-message hidden"></div>
        </div>
        
        <!-- Test Cases Section -->
        <div class="card hidden" id="testcases-section">
            <h2>Test Suite</h2>
            <div class="metadata" id="metadata"></div>
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
        let currentExecutionId = null;
        let testResults = {};
        let summary = { total: 0, passed: 0, failed: 0, errors: 0, approved: 0, declined: 0 };
        let selectedTestCases = new Set();
        
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
        
        async function handleFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            
            uploadError.classList.add('hidden');
            
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
                // Select all test cases by default
                selectedTestCases = new Set(data.test_suite.test_cases.map(tc => tc.id));
                displayTestSuite(data.test_suite);
                updateSelectionCount();
                
            } catch (error) {
                uploadError.textContent = 'Failed to upload file: ' + error.message;
                uploadError.classList.remove('hidden');
            }
        }
        
        function displayTestSuite(suite, showResults = false) {
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
        
        function toggleTestCaseSelection(tcId) {
            if (selectedTestCases.has(tcId)) {
                selectedTestCases.delete(tcId);
            } else {
                selectedTestCases.add(tcId);
            }
            updateSelectionCount();
            updateSelectAllCheckbox();
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
            let durationEl = header.querySelector('.test-case-duration');
            if (!durationEl) {
                const idEl = header.querySelector('.test-case-id');
                idEl.insertAdjacentHTML('beforebegin', `<span class="test-case-duration">${tc.duration_ms}ms</span>`);
            } else {
                durationEl.textContent = `${tc.duration_ms}ms`;
            }
            
            // Update step details with results
            if (tc.steps && tc.steps.length > 0) {
                const stepDetails = element.querySelectorAll('.step-detail');
                tc.steps.forEach(stepResult => {
                    const stepEl = stepDetails[stepResult.step_id - 1];
                    if (stepEl) {
                        stepEl.classList.remove('success', 'failure', 'error');
                        stepEl.classList.add(stepResult.status);
                        
                        // Add result badge to header
                        const headerEl = stepEl.querySelector('.step-detail-header');
                        let badge = headerEl.querySelector('.step-result-badge');
                        if (!badge) {
                            headerEl.insertAdjacentHTML('beforeend', `
                                <span class="step-result-badge ${stepResult.status}">${stepResult.status.toUpperCase()}</span>
                                ${stepResult.duration_ms ? `<span style="color:#888;font-size:0.8rem;margin-left:8px">${stepResult.duration_ms}ms</span>` : ''}
                            `);
                        }
                        
                        // Add response status and body sections
                        if (stepResult.response_status || stepResult.response_body) {
                            const bodyEl = stepEl.querySelector('.step-detail-body');
                            
                            // Add response status row if not present
                            if (stepResult.response_status && !bodyEl.querySelector('.response-status-row')) {
                                const statusHtml = `
                                    <div class="step-section response-status-section">
                                        <div class="step-section-label">API Response</div>
                                        <div class="response-status-row">
                                            <span class="response-status-badge">${stepResult.response_status}</span>
                                            ${stepResult.response_substatus ? `<span class="response-substatus-badge">${stepResult.response_substatus}</span>` : ''}
                                            ${stepResult.http_status_code ? `<span class="http-status-code">HTTP ${stepResult.http_status_code}</span>` : ''}
                                        </div>
                                    </div>
                                `;
                                const requestSection = bodyEl.querySelector('.collapsible-section');
                                if (requestSection) {
                                    requestSection.closest('.step-section').insertAdjacentHTML('afterend', statusHtml);
                                } else {
                                    bodyEl.insertAdjacentHTML('afterbegin', statusHtml);
                                }
                            }
                            
                            // Add collapsible response body if not present
                            if (stepResult.response_body && !bodyEl.querySelector('.response-body-section')) {
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
                                if (statusSection) {
                                    statusSection.insertAdjacentHTML('afterend', responseBodyHtml);
                                } else {
                                    const requestSection = bodyEl.querySelector('.collapsible-section');
                                    if (requestSection) {
                                        requestSection.closest('.step-section').insertAdjacentHTML('afterend', responseBodyHtml);
                                    } else {
                                        bodyEl.insertAdjacentHTML('afterbegin', responseBodyHtml);
                                    }
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
                            const bodyEl = stepEl.querySelector('.step-detail-body');
                            if (!bodyEl.querySelector('.step-error-msg')) {
                                bodyEl.insertAdjacentHTML('beforeend', `
                                    <div class="step-error-msg">${stepResult.error_message}</div>
                                `);
                            }
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
            
            // Start SSE connection with selected test case IDs
            const idsParam = encodeURIComponent(selectedIds.join(','));
            const eventSource = new EventSource(`/execute-stream?suite_id=${currentSuiteId}&test_case_ids=${idsParam}`);
            
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
        });
        
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
    """Handle file upload and parse test suite."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        content = file.read().decode('utf-8')
        json_data = json.loads(content)
        test_suite = TestCaseParser.parse_test_suite(json_data)
        
        # Store the test suite
        suite_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        uploaded_suites[suite_id] = test_suite
        
        # Return parsed data
        return jsonify({
            'suite_id': suite_id,
            'test_suite': {
                'version': test_suite.version,
                'metadata': {
                    'test_suite_name': test_suite.metadata.test_suite_name,
                    'merchant_id': test_suite.metadata.merchant_id,
                    'environment': test_suite.metadata.environment,
                    'created_at': test_suite.metadata.created_at
                },
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
                    for tc in test_suite.test_cases
                ]
            }
        })
        
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON: {str(e)}'}), 400
    except TestCaseParseError as e:
        return jsonify({'error': f'Invalid test case format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


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
    start_ms = time.time() * 1000
    
    try:
        # Substitute variables in input data
        substituted_data = context.substitute_variables(step.input_data)
        
        # Create API request
        base_url = api_client.config.api.base_urls.get(step.provider, "https://api.example.com")
        request_obj = APIRequest(
            method="POST", url=f"{base_url}/{step.operation}",
            headers={"Content-Type": "application/json"}, body=substituted_data
        )
        
        # Execute API call
        response = api_client.execute_operation(step.operation, step.provider, substituted_data)
        
        # Capture variables from response
        captured_vars = {}
        if step.capture_variables and response.body:
            captured_vars = context.capture_variables_from_response(
                {"body": response.body}, step.capture_variables
            )
        
        duration_ms = int((time.time() * 1000) - start_ms)
        status = "success" if response.is_success else "failure"
        
        result = StepResult(
            step_id=step.step_id, operation=step.operation, provider=step.provider,
            status=status, request=request_obj, response=response, duration_ms=duration_ms,
            captured_variables=captured_vars if captured_vars else None
        )
        
        logger.log_step(test_case.id, test_case.name, step, request_obj, response,
                       status, duration_ms, captured_variables=captured_vars)
        return result
        
    except ContextError as e:
        duration_ms = int((time.time() * 1000) - start_ms)
        error_msg = f"Context error: {str(e)}"
        result = StepResult(
            step_id=step.step_id, operation=step.operation, provider=step.provider,
            status="error", duration_ms=duration_ms, error_message=error_msg
        )
        logger.log_step(test_case.id, test_case.name, step, None, None,
                       "error", duration_ms, error_message=error_msg)
        return result
    except Exception as e:
        duration_ms = int((time.time() * 1000) - start_ms)
        error_msg = f"Execution error: {str(e)}"
        result = StepResult(
            step_id=step.step_id, operation=step.operation, provider=step.provider,
            status="error", duration_ms=duration_ms, error_message=error_msg
        )
        logger.log_step(test_case.id, test_case.name, step, None, None,
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
                
                # Send result event
                result_data = {
                    'type': 'test_case_result',
                    'result': {
                        'test_case_id': result.test_case_id,
                        'test_case_name': result.test_case_name,
                        'status': result.status,
                        'duration_ms': result.duration_ms,
                        'error_message': result.error_message,
                        'steps': [
                            {
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
                            for s in result.steps
                        ]
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

if __name__ == '__main__':
    print("\n" + "="*60)
    print("MATRIX Web Interface")
    print("="*60)
    print("Open http://localhost:5001 in your browser")
    print("="*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5001)
