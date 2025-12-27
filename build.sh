#!/bin/bash
set -e

# Define paths
VENV_DIR=".venv"
DIST_DIR="dist"
BUILD_DIR="build"
BIN_DIR="bin"

# Ensure we are in the project directory
cd "$(dirname "$0")"

echo "🚀 Starting build process for YTRSS 2.0..."

# Fresh Start: Clean up everything
echo "🧹 Cleaning up old builds and environment..."
rm -rf "$DIST_DIR" "$BUILD_DIR" "$VENV_DIR" "$BIN_DIR"
# Also clean spec file to ensure fresh config if arguments change
rm -f ytrss.spec

# Create Virtual Environment
echo "🌱 Creating fresh virtual environment..."
python3 -m venv "$VENV_DIR"

# Activate venv
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "📦 Installing dependencies..."
# Upgrade pip quietly
pip install --upgrade pip --quiet
# Install requirements quietly
pip install -r requirements.txt --quiet
# Ensure PyInstaller is installed
pip install pyinstaller --quiet

# Build
echo "🔨 Compiling binary with PyInstaller..."
# --log-level=WARN keeps the output clean
# --onefile bundles everything
# --add-data includes KEYS.md
pyinstaller --onefile --name ytrss --add-data "KEYS.md:." --clean --log-level=WARN ytrss.py

# Organize output
echo "📂 Organizing output..."
mkdir -p "$BIN_DIR"
cp "$DIST_DIR/ytrss" "$BIN_DIR/"

# Final verification and report
if [ -f "$BIN_DIR/ytrss" ]; then
    echo "✅ Build complete!"
    echo "📍 Binary located at: $BIN_DIR/ytrss"
    # Show size in human readable format
    du -h "$BIN_DIR/ytrss" | cut -f1 | awk '{print "   Size: " $1}'

    # Installation Prompt
    echo ""
    read -p "🚀 Do you want to install 'ytrss' to /usr/local/bin? (Requires sudo) [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔑 Installing to /usr/local/bin..."
        if sudo cp "$BIN_DIR/ytrss" /usr/local/bin/ytrss; then
            echo "✅ Successfully installed! You can now run 'ytrss' from anywhere."
        else
            echo "❌ Installation failed. Please check permissions."
        fi
    else
        echo "👋 Skipping installation. You can run it manually from: $BIN_DIR/ytrss"
    fi
else
    echo "❌ Error: Binary creation failed."
    exit 1
fi