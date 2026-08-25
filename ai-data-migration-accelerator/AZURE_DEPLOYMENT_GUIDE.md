# AI Data Migration Accelerator - Azure Deployment Guide

**Version:** 0.1.0 (Production-Ready)  
**Last Updated:** 2026-08-25

---

## 🎯 Quick Start: Deploy to Azure in 5 Steps

If you want to quickly deploy to Azure VM/Container and run migrations independently:

```bash
# 1. CLONE AND SETUP (run once)
git clone <repo-url> accelerator
cd accelerator/ai-data-migration-accelerator

# 2. CREATE PYTHON VIRTUAL ENVIRONMENT
python3.12 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# 3. INSTALL DEPENDENCIES
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. CREATE ENVIRONMENT FILE (with YOUR credentials)
cp .env.example .env
# Edit .env with your actual credentials (see below)

# 5. RUN MIGRATION
python migrate.py --config config.yaml
# Output: output/<schema>/20260825_123456/
```

✅ **Done!** All artifacts (metadata, DDL, profiles, relationships) are in the output folder.

---

## 📋 Complete Setup Instructions for Azure

### Prerequisites

- **Python:** 3.12+ (check: `python3 --version`)
- **OS:** Windows, Linux, or macOS
- **Network:** Outbound access to:
  - Source database (DB2, PostgreSQL, etc.)
  - Azure Databricks workspace
  - Anthropic API (if using Claude)
- **Storage:** ~1GB for venv + outputs

### Step 1: Prepare Python Environment

#### On Windows (Azure VM)
```powershell
# Check Python version
python --version

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip setuptools wheel
```

#### On Linux/macOS (Azure VM, Container)
```bash
# Check Python version
python3.12 --version

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### Step 2: Install Dependencies

```bash
# Install all required libraries
pip install -r requirements.txt

# Verify installation (should succeed silently)
python -c "import pydantic, sqlalchemy, psycopg, ibm_db, yaml, rich, anthropic, openai, requests; print('✅ All dependencies installed')"
```

**Dependencies installed:**
- ✅ `pydantic>=2.7` — Type validation & config models
- ✅ `SQLAlchemy>=2.0` — Database abstraction layer
- ✅ `psycopg[binary]>=3.1` — PostgreSQL driver
- ✅ `ibm-db>=3.2` — IBM DB2 driver
- ✅ `PyYAML>=6.0` — YAML config parser
- ✅ `rich>=13.7` — Rich terminal output
- ✅ `python-dotenv>=1.0` — .env file support
- ✅ `anthropic>=0.40` — Claude API client
- ✅ `openai>=1.50` — OpenAI API client
- ✅ `requests>=2.31` — HTTP client (Databricks Workspace API)

### Step 3: Create Credentials File

Create `.env` file in your working directory:

```env
# Source Database Credentials
SOURCE_DB_PASSWORD=your_source_db_password

# Anthropic LLM (Optional - for conceptual modeling)
ANTHROPIC_API_KEY=sk-ant-...

# Azure Databricks Target
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=dapi123456789...
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/your-warehouse-id
DATABRICKS_WORKSPACE_PATH=/Workspace/Users/your@email.com/migration

# Optional: Custom CA certificate bundle (for corporate proxy/SSL)
# DATABRICKS_CA_BUNDLE=/path/to/ca-bundle.crt
```

**How to get these values:**

- **SOURCE_DB_PASSWORD** — Your DB2/PostgreSQL password
- **ANTHROPIC_API_KEY** — From [console.anthropic.com](https://console.anthropic.com)
- **DATABRICKS_HOST** — From Azure Databricks workspace URL (Settings → Workspace URL)
- **DATABRICKS_TOKEN** — From Azure Databricks (Settings → Personal Access Tokens)
- **DATABRICKS_HTTP_PATH** — From SQL warehouse/cluster details
- **DATABRICKS_WORKSPACE_PATH** — Where to publish DDL files (auto-created)

### Step 4: Configure Migration Schema

Edit `config.yaml` for your migration:

```yaml
project:
  name: customer_migration
  output_directory: output/

source:
  type: db2                    # postgres, db2, oracle, sqlserver, mysql, etc.
  host: your-source-db.com
  port: 50000                  # DB2: 50000, PostgreSQL: 5432, Oracle: 1521
  database: SOURCEDB
  username: db2user            # Your source database username
  password: ""                 # Leave empty - loaded from SOURCE_DB_PASSWORD env var
  schema:
    - SALES                    # Source schema(s) to migrate
    - INVENTORY
  connection_timeout: 30

target:
  type: databricks
  host_env: DATABRICKS_HOST           # Don't change - reads from env var
  token_env: DATABRICKS_TOKEN         # Don't change - reads from env var
  http_path_env: DATABRICKS_HTTP_PATH # Don't change - reads from env var
  workspace_path_env: DATABRICKS_WORKSPACE_PATH  # For --publish-ddl
  catalog: dblearn            # Unity Catalog name (required for new tables)
  schema: bronze              # Target schema - separates different migration runs

llm:
  provider: anthropic
  model: claude-opus-5        # Claude 5 Opus (best), or claude-haiku-4-5-20251001 (fast)
  max_tokens: 32000
  effort: high                # low=cheap, high=thorough, max=exhaustive
  api_key_env: ANTHROPIC_API_KEY

artifacts:
  profile: true               # Generate data profiles
  relationships: true         # Discover foreign key relationships
  conceptual_model: true      # AI-generated business understanding
  logical_model: true         # Data model normalization
  physical_model: true        # Databricks physical design
  ddl: true                   # CREATE TABLE / ALTER / INDEX statements
  dml: true                   # Data movement scripts
  estimation: true            # Effort/duration estimates

logging:
  level: INFO                 # DEBUG (verbose), INFO (normal), WARNING, ERROR
```

### Step 5: Run the Migration

```bash
# Activate your virtual environment first
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# RUN THE FULL MIGRATION
python migrate.py --config config.yaml

# Expected output:
# ========================================================================
# Metadata extraction completed successfully.
# Output Folder : output/bronze/20260825_120000
# Metadata File : output/bronze/20260825_120000/metadata.json
# Profile File  : output/bronze/20260825_120000/profile.json
# DDL           : output/bronze/20260825_120000/databricks.sql
#                 output/bronze/20260825_120000/ddl.json
# ========================================================================
```

✅ **All artifacts are now in `output/bronze/20260825_120000/`**

---

## 🔄 Running Multiple Migrations (Different Schemas/Databases)

### Scenario 1: Migrate Multiple Source Schemas (Same Database)

Use **one config file** with multiple schemas:

**config.yaml:**
```yaml
source:
  type: db2
  host: source-db.com
  database: SOURCEDB
  schema:
    - SALES      # First schema
    - INVENTORY  # Second schema
    - FINANCE    # Third schema
```

**Run all schemas at once:**
```bash
python migrate.py --config config.yaml
# Output:
# - output/SALES/20260825_120000/
# - output/INVENTORY/20260825_120000/
# - output/FINANCE/20260825_120000/
```

**Run specific schema only:**
```bash
python migrate.py --config config.yaml --schema SALES
# Output: output/SALES/20260825_120000/
```

**Run multiple specific schemas:**
```bash
python migrate.py --config config.yaml --schema SALES --schema INVENTORY
# Output:
# - output/SALES/20260825_120000/
# - output/INVENTORY/20260825_120000/
```

### Scenario 2: Migrate Different Databases (Different Configs)

Create separate config files for each database:

**config-db2.yaml:**
```yaml
project:
  name: db2_migration
  output_directory: output/db2/

source:
  type: db2
  host: db2-server.com
  port: 50000
  database: DB2DATABASE
  schema: [SCHEMA1, SCHEMA2]

target:
  catalog: db2_catalog
  schema: bronze
```

**config-postgres.yaml:**
```yaml
project:
  name: postgres_migration
  output_directory: output/postgres/

source:
  type: postgres
  host: postgres-server.com
  port: 5432
  database: postgres_db
  schema: [public]

target:
  catalog: postgres_catalog
  schema: silver
```

**Run migrations independently:**
```bash
# Migrate DB2
python migrate.py --config config-db2.yaml
# Output: output/db2/SCHEMA1/20260825_120000/

# Migrate PostgreSQL
python migrate.py --config config-postgres.yaml
# Output: output/postgres/public/20260825_120000/
```

### Scenario 3: Batch Migration (Script Multiple Runs)

Create a **batch script** to migrate all databases:

**migrate_all.sh** (Linux/macOS):
```bash
#!/bin/bash
set -e  # Exit on any error

echo "Starting batch migration..."

# Activate venv
source venv/bin/activate

# Migrate each database
echo "=== Migrating DB2 ==="
python migrate.py --config configs/db2-sales.yaml

echo "=== Migrating PostgreSQL ==="
python migrate.py --config configs/postgres-marketing.yaml

echo "=== Migrating MySQL ==="
python migrate.py --config configs/mysql-analytics.yaml

echo "✅ All migrations completed!"
echo "Outputs are in:"
echo "  - output/db2/"
echo "  - output/postgres/"
echo "  - output/mysql/"
```

**migrate_all.ps1** (Windows):
```powershell
Write-Host "Starting batch migration..."

# Activate venv
& "venv\Scripts\Activate.ps1"

# Migrate each database
Write-Host "=== Migrating DB2 ==="
python migrate.py --config configs/db2-sales.yaml

Write-Host "=== Migrating PostgreSQL ==="
python migrate.py --config configs/postgres-marketing.yaml

Write-Host "=== Migrating MySQL ==="
python migrate.py --config configs/mysql-analytics.yaml

Write-Host "✅ All migrations completed!"
```

**Run batch migration:**
```bash
# Linux/macOS
chmod +x migrate_all.sh
./migrate_all.sh

# Windows
.\migrate_all.ps1
```

---

## 📦 Deployment Options

### Option 1: Source Code (Recommended for Azure VMs)

Best for: Development, debugging, custom modifications

```bash
# Install from source
cd ai-data-migration-accelerator
pip install -e .

# Run migration
python migrate.py --config config.yaml

# Update code? Just restart - no reinstall needed
```

**Pros:** Easy to modify, debug with IDE, track changes with git  
**Cons:** Requires Python + dependencies everywhere  
**Space:** ~500MB (venv)

### Option 2: Python Wheel (Recommended for CI/CD, Docker)

Best for: Production, distribution, automation

```bash
# Build wheel (one-time)
cd ai-data-migration-accelerator
pip install build
python -m build --wheel
# Creates: dist/ai_data_migration_accelerator-0.1.0-py3-none-any.whl

# Install wheel on any machine
pip install dist/ai_data_migration_accelerator-0.1.0-py3-none-any.whl

# Run migration
migration-accelerator --config config.yaml
```

**Pros:** Single file, no git needed, immutable binary  
**Cons:** Harder to debug/modify  
**Space:** ~200MB (venv + wheel)

### Option 3: Docker Container (Recommended for Azure Container Instances)

Best for: Cloud deployment, multi-region, scalability

**Dockerfile:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy wheel
COPY dist/ai_data_migration_accelerator-0.1.0-py3-none-any.whl .

# Install wheel
RUN pip install --no-cache-dir ai_data_migration_accelerator-0.1.0-py3-none-any.whl

# Copy config and .env
COPY config.yaml .
COPY .env .

# Create output directory
RUN mkdir -p output

# Entry point
ENTRYPOINT ["migration-accelerator"]
CMD ["--config", "config.yaml"]
```

**Build and push to Azure Container Registry:**
```bash
# Build
docker build -t accelerator:0.1.0 .

# Tag for Azure
docker tag accelerator:0.1.0 myregistry.azurecr.io/accelerator:0.1.0

# Push to Azure Container Registry
docker push myregistry.azurecr.io/accelerator:0.1.0

# Run on Azure Container Instances
az container create \
  --resource-group mygroup \
  --name accelerator-migration \
  --image myregistry.azurecr.io/accelerator:0.1.0 \
  --environment-variables \
    SOURCE_DB_PASSWORD=xxx \
    DATABRICKS_HOST=https://xxx.databricks.com \
  --azure-file-volume-mount-path /app/output
```

**Pros:** Cloud-native, scalable, reproducible across regions  
**Cons:** Learning curve for Docker  
**Space:** ~800MB (image)

---

## 🎯 Next Steps After Migration

### 1. Review Generated Artifacts

```bash
cd output/<schema>/<timestamp>/

# View files generated
ls -la
# - metadata.json         (canonical database schema)
# - profile.json          (data statistics)
# - relationships.json    (FK dependencies)
# - conceptual_model.json (AI-generated business model)
# - logical_model.json    (normalized design)
# - physical_model.json   (Databricks-optimized schema)
# - databricks.sql        (DDL statements, human-readable)
# - ddl.json              (machine-readable DDL package)
# - estimation.json       (effort/duration estimates)
```

### 2. Preview Generated DDL

```bash
# Show the SQL that will be executed
cat output/<schema>/<timestamp>/databricks.sql

# Expected output (example):
# CREATE TABLE `dblearn`.`bronze`.`customers` (
#   `customer_id` BIGINT NOT NULL,
#   `customer_name` STRING NOT NULL,
#   `email` STRING,
#   ...
# );
```

### 3. Execute DDL Against Databricks (Dry Run)

```bash
# Preview without actually executing
python migrate.py --config config.yaml \
  --execute-ddl output/bronze/20260825_120000/ddl.json

# Expected output:
# Dry run: 12 statement(s) would be executed
#   CREATE   CREATE TABLE `dblearn`.`bronze`.`customers` (...)
#   ALTER    ALTER TABLE `dblearn`.`bronze`.`customers` ADD CONSTRAINT fk_...
#   CREATE   CREATE INDEX idx_email ON `dblearn`.`bronze`.`customers`(email)
```

### 4. Execute DDL Live Against Databricks

```bash
# ACTUALLY EXECUTE against live Databricks workspace
python migrate.py --config config.yaml \
  --execute-ddl output/bronze/20260825_120000/ddl.json \
  --live

# Expected output:
# Executed 12 statement(s), 0 failed.
```

### 5. Publish SQL Files to Databricks Workspace

```bash
# Upload the DDL SQL file to Databricks Workspace
python migrate.py --config config.yaml \
  --publish-ddl output/bronze/20260825_120000/databricks.sql

# File is now accessible in Databricks:
# /Workspace/Users/your@email.com/migration/databricks.sql
```

---

## 🔒 Security Best Practices

### ✅ DO:
- Store credentials in **.env** (never commit to git)
- Use IAM roles for Databricks authentication when possible
- Rotate personal access tokens regularly
- Use environment variables: `${VAR}` in config.yaml
- Keep `.env` in `.gitignore`

### ❌ DON'T:
- Commit passwords to git
- Hardcode credentials in config.yaml
- Share `.env` file via email/Slack
- Use shared credentials across teams
- Leave SSH keys in container images

### Example .env in .gitignore:

```bash
# .gitignore
.env                        # ✅ Never commit secrets
.env.local
.env.*.local
.DS_Store
venv/
build/
dist/
*.egg-info/
```

---

## 🧪 Testing Deployment

### Verify Installation

```bash
# Test Python environment
python --version
# Python 3.12.0+

# Test imports
python -c "
from migration.connectors.factory import create_connector
from migration.models.config import AppConfig, SourceType, TargetType
print('✅ All imports successful')
"

# Test config loading
python -c "
import os
os.environ['SOURCE_DB_PASSWORD'] = 'test'
os.environ['DATABRICKS_HOST'] = 'https://test.databricks.com'
os.environ['DATABRICKS_TOKEN'] = 'test'
os.environ['DATABRICKS_WORKSPACE_PATH'] = '/test'
os.environ['ANTHROPIC_API_KEY'] = 'test'
from migration.utils.config_loader import load_config
config = load_config('config.yaml')
print(f'✅ Config loaded: project={config.project.name}, source={config.source.type}, target={config.target.type}')
"

# Test CLI
python migrate.py --help
# Usage: migrate.py [-h] --config CONFIG [--schema SCHEMA] [--plan] ...
```

### Run Test Suite

```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_source_database_type_mapping.py -v

# With coverage
pytest tests/ --cov=migration --cov-report=html
# Output: htmlcov/index.html
```

---

## 📊 Performance Tips

| Setting | Recommendation | Impact |
|---------|---|---|
| `llm.effort` | `low` for quick preview | 10x faster, less intelligent |
| `llm.effort` | `high` for production | 3x slower, very thorough |
| `artifacts.conceptual_model` | `false` if not needed | Skip 20% of time |
| `artifacts.profile` | `false` for large tables | Skip 30% of time |
| `source.connection_timeout` | 60-120 seconds | Lower = timeout errors, Higher = slow feedback |

---

## 🐛 Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError: pydantic` | Dependencies not installed | `pip install -r requirements.txt` |
| `Config validation failed` | Missing env var | Check `.env` has SOURCE_DB_PASSWORD, etc. |
| `Connection refused` | Wrong host/port | Verify source.host and source.port in config.yaml |
| `DATABRICKS_HOST not set` | Env var missing | Export: `export DATABRICKS_HOST=https://...` |
| `Permission denied (.env)` | File permissions | `chmod 600 .env` (Linux/Mac) |
| `Timeout connecting to DB` | Network/firewall issue | Check source DB is accessible from your network |
| `SSL certificate verify failed` | Corporate proxy/custom CA | Set `DATABRICKS_CA_BUNDLE=/path/to/ca-bundle.crt` |
| `Wheel not found` | Not built yet | `python -m build --wheel` |

---

## 📞 Support & Diagnostics

### Enable Debug Logging

```yaml
# In config.yaml
logging:
  level: DEBUG
```

**Output:** Detailed logs in `logs/migration.log`

### Generate Diagnostic Report

```bash
# Collect system info for support
python -c "
import platform
import sys
import pkg_resources

print('=== Environment ===')
print(f'OS: {platform.system()} {platform.release()}')
print(f'Python: {sys.version}')
print()
print('=== Installed Packages ===')
for dist in pkg_resources.working_set:
    if any(x in dist.project_name.lower() for x in ['pydantic', 'sqlalchemy', 'psycopg', 'ibm', 'yaml', 'rich', 'anthropic', 'openai', 'requests']):
        print(f'{dist.project_name} {dist.version}')
"
```

---

## ✅ Checklist: Ready for Production

- [ ] Python 3.12+ installed
- [ ] Virtual environment created (`venv/`)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with all credentials
- [ ] `config.yaml` configured for your source/target
- [ ] Source database connection verified
- [ ] Databricks workspace accessible
- [ ] Test migration run completed successfully
- [ ] Output files reviewed (`output/<schema>/<timestamp>/`)
- [ ] DDL verified before live execution
- [ ] Security checklist completed (credentials, .gitignore, etc.)

---

## 🚀 Next Phase: Automation

**CI/CD Integration:** Set up automated migrations on schedule
- GitHub Actions / GitLab CI workflow
- Azure DevOps pipeline
- Jenkins / Airflow dag
- CloudScheduler / Lambda

**Contact:** See README.md for support and detailed documentation

**Version:** 0.1.0 | **Status:** ✅ Production-Ready
