# AI Data Migration Accelerator - Azure Setup Script (Windows)
# Run this once on your Azure VM to set up the accelerator
# Usage: .\setup-azure.ps1
# Note: May need to run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Write-Host "==========================================" -ForegroundColor Green
Write-Host "AI Data Migration Accelerator - Setup" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Check Python version
Write-Host "`u{2713} Checking Python version..." -ForegroundColor Cyan
$pythonVersion = python --version 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Host "`u{274C} Python not found. Please install Python 3.12+" -ForegroundColor Red
    exit 1
}
Write-Host "  Found $pythonVersion" -ForegroundColor Green

# Create virtual environment
Write-Host "`u{2713} Creating Python virtual environment..." -ForegroundColor Cyan
if (Test-Path "venv") {
    Write-Host "  venv already exists, skipping..." -ForegroundColor Yellow
} else {
    python -m venv venv
    Write-Host "  Created venv\" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "`u{2713} Activating virtual environment..." -ForegroundColor Cyan
& "venv\Scripts\Activate.ps1"
Write-Host "  Virtual environment activated" -ForegroundColor Green

# Upgrade pip
Write-Host "`u{2713} Upgrading pip, setuptools, wheel..." -ForegroundColor Cyan
python -m pip install --upgrade pip setuptools wheel | Out-Null
Write-Host "  Upgraded" -ForegroundColor Green

# Install dependencies
Write-Host "`u{2713} Installing dependencies from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt
Write-Host "  Dependencies installed" -ForegroundColor Green

# Create .env file
Write-Host "`u{2713} Setting up environment credentials..." -ForegroundColor Cyan
if (Test-Path ".env") {
    Write-Host "  .env already exists, skipping..." -ForegroundColor Yellow
} else {
    Copy-Item ".env.example" ".env"
    Write-Host "  Created .env (EDIT THIS FILE with your credentials)" -ForegroundColor Green
}

# Verify installation
Write-Host "`u{2713} Verifying installation..." -ForegroundColor Cyan
$test = @"
import pydantic, sqlalchemy, psycopg, ibm_db, yaml, rich, anthropic, openai, requests
print('All dependencies verified')
"@
python -c $test
if ($LASTEXITCODE -ne 0) {
    Write-Host "`u{274C} Verification failed" -ForegroundColor Red
    exit 1
}

# Test config loading
Write-Host "`u{2713} Testing configuration..." -ForegroundColor Cyan
$configTest = @"
import os
os.environ['SOURCE_DB_PASSWORD'] = 'test'
os.environ['DATABRICKS_HOST'] = 'https://test.databricks.com'
os.environ['DATABRICKS_TOKEN'] = 'test'
os.environ['DATABRICKS_WORKSPACE_PATH'] = '/test'
os.environ['ANTHROPIC_API_KEY'] = 'test'
from migration.utils.config_loader import load_config
config = load_config('config.yaml')
print(f'Config valid: project={config.project.name}, source={config.source.type}')
"@
python -c $configTest
if ($LASTEXITCODE -ne 0) {
    Write-Host "`u{274C} Config test failed" -ForegroundColor Red
    exit 1
}

# Summary
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "`u{2713} Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. EDIT YOUR CREDENTIALS" -ForegroundColor Cyan
Write-Host "   notepad .env" -ForegroundColor White
Write-Host "   (Add SOURCE_DB_PASSWORD, DATABRICKS_HOST, DATABRICKS_TOKEN, etc.)" -ForegroundColor Gray
Write-Host ""
Write-Host "2. EDIT MIGRATION CONFIG" -ForegroundColor Cyan
Write-Host "   notepad config.yaml" -ForegroundColor White
Write-Host "   (Set source type, database, schemas, target catalog)" -ForegroundColor Gray
Write-Host ""
Write-Host "3. ACTIVATE ENVIRONMENT" -ForegroundColor Cyan
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "4. RUN MIGRATION" -ForegroundColor Cyan
Write-Host "   python migrate.py --config config.yaml" -ForegroundColor White
Write-Host ""
Write-Host "5. VIEW OUTPUT" -ForegroundColor Cyan
Write-Host "   dir output\" -ForegroundColor White
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
