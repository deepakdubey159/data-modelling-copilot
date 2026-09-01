#!/bin/bash
# AI Data Migration Accelerator - Azure Setup Script
# Run this once on your Azure VM to set up the accelerator
# Usage: bash setup-azure.sh

set -e  # Exit on error

echo "=========================================="
echo "AI Data Migration Accelerator - Setup"
echo "=========================================="
echo ""

# Check Python version
echo "✓ Checking Python version..."
if ! python3.12 --version 2>/dev/null; then
    echo "❌ Python 3.12 not found. Please install Python 3.12+"
    exit 1
fi
PYTHON_VERSION=$(python3.12 --version | cut -d' ' -f2)
echo "  Found Python $PYTHON_VERSION"
echo ""

# Create virtual environment
echo "✓ Creating Python virtual environment..."
if [ -d "venv" ]; then
    echo "  venv already exists, skipping..."
else
    python3.12 -m venv venv
    echo "  Created venv/"
fi
echo ""

# Activate virtual environment
echo "✓ Activating virtual environment..."
source venv/bin/activate
echo "  Virtual environment activated"
echo ""

# Upgrade pip
echo "✓ Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel >/dev/null 2>&1
echo "  Upgraded"
echo ""

# Install dependencies
echo "✓ Installing dependencies from requirements.txt..."
pip install -r requirements.txt
echo "  Dependencies installed"
echo ""

# Create .env file
echo "✓ Setting up environment credentials..."
if [ -f ".env" ]; then
    echo "  .env already exists, skipping..."
else
    cp .env.example .env
    echo "  Created .env (EDIT THIS FILE with your credentials)"
fi
echo ""

# Verify installation
echo "✓ Verifying installation..."
python -c "
import pydantic, sqlalchemy, psycopg, ibm_db, yaml, rich, anthropic, openai, requests
print('  All dependencies verified')
" || {
    echo "❌ Verification failed. Try: pip install -r requirements.txt"
    exit 1
}
echo ""

# Test config loading
echo "✓ Testing configuration..."
python -c "
import os
os.environ['SOURCE_DB_PASSWORD'] = 'test'
os.environ['DATABRICKS_HOST'] = 'https://test.databricks.com'
os.environ['DATABRICKS_TOKEN'] = 'test'
os.environ['DATABRICKS_WORKSPACE_PATH'] = '/test'
os.environ['ANTHROPIC_API_KEY'] = 'test'
from migration.utils.config_loader import load_config
config = load_config('config.yaml')
print(f'  Config valid: project={config.project.name}, source={config.source.type}')
" || {
    echo "❌ Config test failed. Check config.yaml syntax"
    exit 1
}
echo ""

# Summary
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. EDIT YOUR CREDENTIALS"
echo "   nano .env"
echo "   (Add SOURCE_DB_PASSWORD, DATABRICKS_HOST, DATABRICKS_TOKEN, etc.)"
echo ""
echo "2. EDIT MIGRATION CONFIG"
echo "   nano config.yaml"
echo "   (Set source type, database, schemas, target catalog)"
echo ""
echo "3. ACTIVATE ENVIRONMENT"
echo "   source venv/bin/activate"
echo ""
echo "4. RUN MIGRATION"
echo "   python migrate.py --config config.yaml"
echo ""
echo "5. VIEW OUTPUT"
echo "   ls -la output/"
echo ""
echo "=========================================="
