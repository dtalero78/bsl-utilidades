#!/bin/bash
set -e

echo "🔧 Installing Python dependencies..."
pip install -r requirements.txt

echo "📦 Installing Node.js dependencies..."
npm install

echo "🎭 Installing Puppeteer Chromium..."
# Puppeteer will download Chromium automatically during npm install
# but we need to ensure the environment is set up correctly
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false

echo "📦 Installing system dependencies for Puppeteer..."
# Digital Ocean should have these, but just in case
if command -v apt-get &> /dev/null; then
    echo "Installing Chromium dependencies via apt-get..."
    apt-get update || true
    apt-get install -y \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
        libatspi2.0-0 \
        ca-certificates \
        fonts-liberation \
        || echo "⚠️ Could not install system dependencies (may need sudo)"
fi

echo "✅ Build completed successfully"
