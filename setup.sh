#!/bin/bash

# Setup script for Google Drive Downloader (Linux/Mac)

echo ""
echo "========================================"
echo "Google Drive Downloader - Setup"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python from https://www.python.org"
    exit 1
fi

echo "Python found: $(python3 --version)"
echo ""

echo "Installing required packages..."
echo "This may take a minute..."
echo ""

# Install packages
pip3 install google-auth-oauthlib google-auth-httplib2 google-api-python-client customtkinter

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to install packages"
    exit 1
fi

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Get your Google Drive API credentials:"
echo "   - Go to https://console.cloud.google.com/"
echo "   - Create an OAuth 2.0 Desktop Application"
echo "   - Download the JSON file and name it client_secret_file.json"
echo ""
echo "2. Run the app:"
echo "   python3 app_ui.py"
echo ""
echo "For detailed instructions, see README.md"
echo ""
