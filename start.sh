#!/bin/bash

# MATRIX Web Interface Startup Script
# This script activates the virtual environment and starts the Flask server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo "  MATRIX - Web Interface Launcher"
echo "======================================"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "Checking dependencies..."
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "Warning: .env file not found."
    echo "Copy .env.example to .env and configure your API keys."
    echo ""
fi

echo ""
echo "Starting MATRIX Web Interface..."
echo "======================================"
echo ""

# Start the Flask server
python3 web.py
