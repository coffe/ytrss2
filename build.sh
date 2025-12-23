#!/bin/bash
set -e

# Define colors
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building YTRSS 2.0...${NC}"

# Cleanup
echo "Cleaning up old builds..."
rm -rf build dist .venv ytrss.spec

# Create Virtual Environment
echo "Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Build
# Note: --add-data format is source:dest. On Linux/Mac use :, on Windows use ;
# We assume Linux build environment here as per shebang
echo "Compiling binary with PyInstaller..."
pyinstaller --onefile --name ytrss --add-data "KEYS.md:." --clean ytrss.py

# Organize output
mkdir -p bin
cp dist/ytrss bin/

echo -e "${GREEN}Build complete! Binary located at: bin/ytrss${NC}"
