# Configuration Examples

This directory contains example configuration files for different migration scenarios.

## Quick Start

1. **Copy an example to your working directory:**
   ```bash
   cp configs/example-db2-sales.yaml config.yaml
   ```

2. **Edit for your environment:**
   ```bash
   nano config.yaml
   ```
   Change: `host`, `database`, `port`, `schema`, `catalog`, etc.

3. **Create `.env` with your credentials:**
   ```bash
   cp .env.example .env
   nano .env
   ```

4. **Run migration:**
   ```bash
   python migrate.py --config config.yaml
   ```

## Configuration Files

### `example-db2-sales.yaml`
**Source:** IBM DB2  
**Target:** Azure Databricks  
**Schemas:** SALES, PROMOTIONS  

Use this if migrating from DB2. Key differences:
- `source.type: db2`
- `source.port: 50000` (DB2 default)
- `source.database: SALESDB` (DB2 catalog name)

### `example-postgres-analytics.yaml`
**Source:** PostgreSQL  
**Target:** Azure Databricks  
**Schemas:** public, metrics, reports

Use this if migrating from PostgreSQL. Key differences:
- `source.type: postgres`
- `source.port: 5432` (PostgreSQL default)
- Multiple schemas in `public` namespace

## Supported Source Types

```yaml
source:
  type: postgres          # PostgreSQL
  type: db2              # IBM DB2
  type: mysql            # MySQL
  type: oracle           # Oracle Database
  type: sqlserver        # Microsoft SQL Server
  type: sap_hana         # SAP HANA
  type: snowflake        # Snowflake (source side only)
  type: databricks       # Databricks (source side only)
  type: bigquery         # BigQuery (source side only)
  type: redshift         # Amazon Redshift (source side only)
```

## Configuration Structure

### Project Section
```yaml
project:
  name: unique_project_name        # For logging
  output_directory: output/         # Where to save generated files
```

### Source Section
```yaml
source:
  type: postgres                   # Source database type
  host: source-db.company.com      # Hostname/IP
  port: 5432                       # Port number
  database: mydb                   # Database/catalog name
  username: user                   # Login username
  password: ""                     # Leave empty - use env var
  schema:                          # Schemas to migrate
    - schema1
    - schema2
  connection_timeout: 30           # Seconds
```

**Default ports:**
- PostgreSQL: 5432
- MySQL: 3306
- Oracle: 1521
- DB2: 50000
- SQL Server: 1433
- SAP HANA: 30013
- Snowflake: 443
- BigQuery: (no port, uses API)

### Target Section
```yaml
target:
  type: databricks                           # Always "databricks"
  host_env: DATABRICKS_HOST                  # Env var name (don't change)
  token_env: DATABRICKS_TOKEN                # Env var name (don't change)
  http_path_env: DATABRICKS_HTTP_PATH        # Env var name (don't change)
  workspace_path_env: DATABRICKS_WORKSPACE_PATH  # For --publish-ddl
  catalog: dblearn                           # Unity Catalog name
  schema: bronze                             # Target schema/database
```

### LLM Section (Optional)
```yaml
llm:
  provider: anthropic               # "anthropic" or "openai"
  model: claude-opus-5              # Model ID
  max_tokens: 32000                 # Hard limit
  effort: high                      # low | medium | high | xhigh | max
  api_key_env: ANTHROPIC_API_KEY    # Env var name
```

**Model options:**
- **Anthropic:** `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`
- **OpenAI:** `gpt-4o`, `gpt-4-turbo`, `gpt-4`

### Artifacts Section (All Optional)
```yaml
artifacts:
  profile: true                 # Generate data statistics
  relationships: true           # Discover foreign keys
  conceptual_model: true        # AI-generated business model
  logical_model: true           # Normalized design
  physical_model: true          # Databricks-optimized
  ddl: true                     # CREATE TABLE statements
  dml: true                     # Data movement scripts
  estimation: true              # Effort estimates
```

### Logging Section
```yaml
logging:
  level: INFO                   # DEBUG | INFO | WARNING | ERROR
```

## Scenario: Multiple Databases

Create separate config files for each:

**config-db2.yaml:**
```yaml
project:
  name: db2_migration
  output_directory: output/db2/

source:
  type: db2
  host: db2-server.com
  database: DB2DB
  schema: [SCHEMA1, SCHEMA2]

target:
  catalog: db2_catalog
  schema: db2_bronze
```

**config-postgres.yaml:**
```yaml
project:
  name: postgres_migration
  output_directory: output/postgres/

source:
  type: postgres
  host: postgres-server.com
  database: postgres_db
  schema: [public]

target:
  catalog: postgres_catalog
  schema: postgres_bronze
```

**Run both:**
```bash
python migrate.py --config config-db2.yaml
python migrate.py --config config-postgres.yaml
```

## Scenario: Multiple Schemas from Same Database

Use **one** config with multiple schemas:

```yaml
source:
  type: db2
  host: db2-server.com
  database: SOURCEDB
  schema:
    - SALES
    - MARKETING
    - FINANCE
```

**Run all schemas:**
```bash
python migrate.py --config config.yaml
# Outputs:
# - output/SALES/<timestamp>/
# - output/MARKETING/<timestamp>/
# - output/FINANCE/<timestamp>/
```

**Run specific schema:**
```bash
python migrate.py --config config.yaml --schema SALES
```

## Environment Variables Reference

All credentials come from these env vars (never hardcode passwords):

```bash
# Source database password
SOURCE_DB_PASSWORD=your_password

# Databricks workspace
DATABRICKS_HOST=https://your-workspace.databricks.com
DATABRICKS_TOKEN=dapi123...
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/abc123

# Workspace publishing (for --publish-ddl)
DATABRICKS_WORKSPACE_PATH=/Workspace/Users/you@company.com/migration

# LLM API key (optional)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional: Custom CA certificate for corporate SSL proxy
DATABRICKS_CA_BUNDLE=/path/to/ca-bundle.crt
```

Load these from **`.env` file:**
```bash
cp .env.example .env
# Edit .env with your values
```

The CLI automatically loads `.env` on startup.

## Tips & Tricks

### Use Environment Variables in Config
```yaml
source:
  password: ${SOURCE_DB_PASSWORD}       # Resolved from env
  password: ${SOURCE_DB_PASSWORD:-pwd}  # Default: "pwd"
```

### Run Schema in Different Target Schema
```bash
# Rerun same source schema to different target
python migrate.py --config config.yaml --schema SALES --force
# Change target.schema in config.yaml first
```

### Skip AI Step (Faster)
```yaml
artifacts:
  conceptual_model: false    # Skip AI, 20% faster
```

### Debug Mode
```yaml
logging:
  level: DEBUG               # Very verbose, for troubleshooting
```

## Validation

The configuration is automatically validated on startup. Common errors:

| Error | Fix |
|-------|-----|
| `Config validation failed` | Check YAML syntax (indentation, colons) |
| `source.schema must contain at least one schema` | Add at least one schema |
| `source.port must be between 1 and 65535` | Valid port number |
| `target.catalog required for live execution` | Add catalog field to target |

## Next Steps

1. Copy an example: `cp configs/example-*.yaml config.yaml`
2. Edit for your environment
3. Create `.env` with credentials
4. Run: `python migrate.py --config config.yaml`
5. Check outputs in `output/`

See `AZURE_DEPLOYMENT_GUIDE.md` for complete setup instructions.
