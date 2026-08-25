# Production Deployment Checklist

**Use this checklist to verify your deployment is ready for production.**

---

## ✅ Pre-Deployment Setup (Week 1)

### Environment Preparation

- [ ] **Python Version**
  - Run: `python3.12 --version`
  - Should output: `Python 3.12.x` or higher
  - ℹ️ If not installed: [Download Python 3.12+](https://www.python.org/downloads/)

- [ ] **Virtual Environment Created**
  - Run: `python3.12 -m venv venv`
  - Verify: `ls -la venv/` (Linux/Mac) or `dir venv` (Windows)
  - ℹ️ Contains isolated Python + dependencies

- [ ] **Virtual Environment Activated**
  - Linux/Mac: `source venv/bin/activate`
  - Windows: `venv\Scripts\activate`
  - Verify: `(venv)` appears in shell prompt

- [ ] **Dependencies Installed**
  - Run: `pip install -r requirements.txt`
  - Verify: `pip list | grep pydantic`
  - Should show: `pydantic 2.7.0` or higher

- [ ] **All 11 Required Libraries Present**
  ```bash
  python -c "
  import pydantic
  import sqlalchemy
  import psycopg
  import ibm_db
  import yaml
  import rich
  import python_dotenv
  import anthropic
  import openai
  import requests
  print('✅ All 11 libraries installed')
  "
  ```

### Credentials & Secrets

- [ ] **`.env` File Created**
  - Run: `cp .env.example .env`
  - Verify: `ls -la .env` (hidden file exists)
  - ℹ️ Never commit to git

- [ ] **`.gitignore` Includes `.env`**
  - Verify: `.env` is in `.gitignore`
  - Never accidentally commit: `git diff --cached .env` (should be empty)

- [ ] **All Required Environment Variables Set**
  - `SOURCE_DB_PASSWORD` ✅
  - `DATABRICKS_HOST` ✅
  - `DATABRICKS_TOKEN` ✅
  - `DATABRICKS_HTTP_PATH` ✅
  - `DATABRICKS_WORKSPACE_PATH` ✅
  - `ANTHROPIC_API_KEY` ✅ (optional, for AI features)
  - `DATABRICKS_CA_BUNDLE` ✅ (if corporate proxy)

- [ ] **Verify Credentials are Valid**
  - Test source DB connection separately
  - Test Databricks token with curl/API call
  - Test Anthropic API key if using LLM

---

## ✅ Configuration & Code (Week 1-2)

### Configuration Validation

- [ ] **`config.yaml` Syntax Valid**
  - Run: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
  - Should succeed silently (no errors)

- [ ] **`config.yaml` Fully Configured**
  - `project.name` is set ✅
  - `source.type` is valid (postgres, db2, mysql, etc.) ✅
  - `source.host` is set ✅
  - `source.port` is correct ✅
  - `source.database` is set ✅
  - `source.username` is set ✅
  - `source.schema` has at least one schema ✅
  - `target.type` is "databricks" ✅
  - `target.catalog` is set ✅
  - `target.schema` is set ✅

- [ ] **Config Loads Successfully**
  ```bash
  python -c "
  import os
  from migration.utils.config_loader import load_config
  config = load_config('config.yaml')
  print(f'✅ Config loaded: {config.project.name}')
  "
  ```

### Source Database Connectivity

- [ ] **Source Database is Accessible**
  - Ping: `ping source-db.hostname`
  - Port: `telnet source-db.hostname 5432` (or your port)
  - ℹ️ Network firewall allows outbound access

- [ ] **Source Database Credentials Work**
  - Run: `python migrate.py --config config.yaml --plan`
  - Should connect and show migration plan
  - ℹ️ If fails: check password, firewall, network

- [ ] **Source Database Has Required Schemas**
  - Verify all schemas in `config.yaml` exist on source DB
  - Verify schemas have tables to migrate
  - Check for read permissions on required objects

### Target Databricks Setup

- [ ] **Azure Databricks Workspace is Accessible**
  - Visit: `https://your-workspace.databricks.com`
  - Should load Databricks interface

- [ ] **Databricks Token is Valid**
  - Run:
    ```bash
    curl -H "Authorization: Bearer $DATABRICKS_TOKEN" \
      https://your-workspace.databricks.com/api/2.0/clusters/list
    ```
  - Should return JSON (not 401 Unauthorized)

- [ ] **Target Catalog Exists or Can Be Created**
  - In Databricks: Go to Data > Catalogs
  - Verify catalog name from `target.catalog` exists or is creatable
  - ℹ️ Some workspaces auto-create; others need admin approval

- [ ] **SQL Warehouse/Cluster is Running**
  - In Databricks: Go to SQL > Warehouses (or Compute > Clusters)
  - Verify the warehouse/cluster for `DATABRICKS_HTTP_PATH` is running
  - ℹ️ It will start automatically when needed, but startup adds ~2 min delay

- [ ] **SSL Certificate Chain Valid (if corporate proxy)**
  - If using custom CA: `DATABRICKS_CA_BUNDLE=/path/to/ca-bundle.crt`
  - Verify file exists and is readable: `ls -la /path/to/ca-bundle.crt`
  - Verify certificate is valid: `openssl x509 -text -noout -in /path/to/ca-bundle.crt`

### Code & Dependencies

- [ ] **All Tests Pass Locally**
  ```bash
  pip install -e ".[dev]"
  pytest tests/ -v
  # All tests should PASS
  ```

- [ ] **Code Quality Checks Pass**
  ```bash
  # Lint check
  ruff check .
  
  # Format check
  black --check .
  ```

---

## ✅ Test Run (Week 2-3)

### Dry Run (Read-Only)

- [ ] **Test Migration with `--plan` (Read-Only)**
  ```bash
  python migrate.py --config config.yaml --plan
  ```
  - Expected: Schema migration order, dependencies shown
  - No changes made to source or target
  - Should complete in < 2 minutes

- [ ] **Test Single Schema**
  ```bash
  python migrate.py --config config.yaml --schema <schema_name>
  ```
  - Should generate: metadata, profile, DDL, etc.
  - Check output directory: `output/<schema>/<timestamp>/`

### Review Generated Artifacts

- [ ] **Metadata JSON is Valid**
  - File: `output/<schema>/<timestamp>/metadata.json`
  - Check: Valid JSON, contains tables, columns, types
  - Verify: All source tables are present

- [ ] **Profile JSON Shows Data Statistics**
  - File: `output/<schema>/<timestamp>/profile.json`
  - Check: Row counts, null percentages, column statistics
  - Verify: No errors in profiling data

- [ ] **Generated DDL is Correct**
  - File: `output/<schema>/<timestamp>/databricks.sql`
  - Check: CREATE TABLE statements
  - Verify: Catalog and schema names are correct
  - Example: `CREATE TABLE \`catalog\`.\`schema\`.\`table_name\``

- [ ] **Column Types are Correct**
  - Verify: No `STRING(255)` (should be just `STRING`)
  - Verify: `DECIMAL(18,2)` preserved correctly
  - Verify: DB2 `BIGINT` → Databricks `BIGINT` mapping

- [ ] **Relationships Discovered**
  - File: `output/<schema>/<timestamp>/relationships.json`
  - Check: Foreign keys are identified
  - Verify: Cardinality is correct (1:1, 1:N, etc.)

- [ ] **Conceptual Model Generated (if AI enabled)**
  - File: `output/<schema>/<timestamp>/conceptual_model.json`
  - Check: Entity types are meaningful
  - Verify: Relationships match source FK definitions

### Dry Run DDL Execution

- [ ] **Preview DDL Execution (No Changes)**
  ```bash
  python migrate.py --config config.yaml \
    --execute-ddl output/<schema>/<timestamp>/ddl.json
  ```
  - Expected: "Dry run: N statement(s) would be executed"
  - No tables created
  - Review each statement carefully

- [ ] **Verify Generated SQL in Dry Run**
  - Check table names: `\`catalog\`.\`schema\`.\`table\``
  - Check column names and types
  - Check constraints, indexes are present
  - Look for any suspicious statements

---

## ✅ Performance & Scale Testing (Week 3-4)

### Benchmark with Sample Data

- [ ] **Small Test Run**
  - Migrate 1-2 small schemas (< 10 tables, < 1M rows)
  - Measure time taken
  - Verify output quality

- [ ] **Medium Test Run**
  - Migrate 10-50 tables
  - Total data: 10-100M rows
  - Measure time, memory usage
  - Check for timeouts or slowdowns

- [ ] **Large Test Run (if applicable)**
  - Migrate 100+ tables
  - Total data: 1B+ rows
  - Monitor:
    - CPU usage
    - Memory usage
    - Network I/O
    - Execution time

### Performance Tuning

- [ ] **If too slow: Reduce AI Effort**
  ```yaml
  llm:
    effort: low    # Instead of "high"
  ```
  - 10x faster, less intelligent

- [ ] **If too slow: Skip AI**
  ```yaml
  artifacts:
    conceptual_model: false
    logical_model: false
  ```
  - Only generates deterministic artifacts

- [ ] **If profiling too slow: Skip It**
  ```yaml
  artifacts:
    profile: false
  ```
  - Skips data statistics generation

---

## ✅ Security Verification (Week 4)

### Access Control

- [ ] **Source DB Credentials Use Service Account**
  - User: Service account (not personal credentials)
  - Permissions: Read-only on required schemas/tables
  - Not: Database superuser

- [ ] **Databricks Service Principal or PAT is Minimal**
  - Token: Service principal (not personal account)
  - Permissions: Only create tables in target catalog+schema
  - Not: Workspace admin, cluster create/delete

- [ ] **API Keys are Rotated**
  - Schedule: Rotate every 90 days
  - Process: Update .env, restart migrations
  - Track: When each key was created

### Secret Storage

- [ ] **`.env` is Never Committed**
  - Verify: `git log --all -S 'SOURCE_DB_PASSWORD' | wc -l` returns 0
  - Verify: `.env` is in `.gitignore`
  - If accidentally committed: Rotate all passwords

- [ ] **`.env` Permissions are Restricted**
  - Linux/Mac: `chmod 600 .env` (owner read/write only)
  - Windows: File properties, remove "Everyone" permission
  - Verify: `ls -la .env` shows `-rw-------`

- [ ] **Databricks CA Bundle Stored Securely**
  - File: Not in git repository
  - Permissions: 600 (owner read only)
  - Storage: System certificate store or secure vault

- [ ] **Logs Don't Contain Secrets**
  - Check: `logs/migration.log` has no passwords
  - Verify: No PII/credentials in output
  - Redact if found before sharing logs

---

## ✅ Deployment & Execution (Week 4-5)

### Pre-Production Run

- [ ] **Full Test Run on Similar Compute**
  - Use production-like VM/container (same OS, CPU, RAM)
  - Run on small subset of production data
  - Verify: Same results as development

- [ ] **Monitoring is Set Up**
  - Logs: Redirect to `logs/migration.log`
  - Alerts: Set up for job failures
  - Metrics: Track execution time, success rate

### Live Execution (When Ready)

- [ ] **First Live Execution**
  ```bash
  # Start with smallest schema
  python migrate.py --config config.yaml --schema <smallest_schema>
  ```
  - Verify: All 12 artifacts generated successfully
  - Check: No errors in logs

- [ ] **Live DDL Execution (First Table)**
  ```bash
  # Execute DDL for one schema
  python migrate.py --config config.yaml \
    --execute-ddl output/<schema>/<timestamp>/ddl.json \
    --live
  ```
  - Verify: Tables created in Databricks
  - Check: Databricks UI shows new tables
  - Verify: Schemas and catalogs are correct

- [ ] **Run Additional Schemas**
  ```bash
  # Run remaining schemas one by one
  for schema in SCHEMA2 SCHEMA3 SCHEMA4; do
    python migrate.py --config config.yaml --schema $schema
  done
  ```
  - Monitor for failures
  - Stop and investigate if errors occur

- [ ] **Verify All Artifacts in Target**
  - Databricks: Navigate to Data > Catalogs > catalog > schema
  - Count tables: Should match source schema count
  - Spot-check: Open 5-10 tables, verify columns match

---

## ✅ Operational Readiness (Week 5+)

### Runbooks & Documentation

- [ ] **Deployment Runbook Written**
  - Step-by-step instructions
  - Commands to run
  - Expected outputs
  - Troubleshooting section

- [ ] **Configuration Management**
  - Config files stored in version control
  - Changes tracked and audited
  - Rollback plan documented

- [ ] **Backup & Recovery Plan**
  - Output artifacts backed up
  - Rollback procedure documented
  - Recovery time objective (RTO) defined

### Monitoring & Alerting

- [ ] **Logging Configured**
  ```yaml
  logging:
    level: INFO
  ```
  - Logs written to: `logs/migration.log`
  - Rotation: Set up log rotation (daily/size-based)

- [ ] **Alerts Set Up**
  - Email alert on failure
  - Slack notification on success/failure
  - PagerDuty escalation for critical failures

- [ ] **Metrics Tracked**
  - Execution time
  - Success/failure rate
  - Number of tables migrated
  - Data volume migrated

### Support & Escalation

- [ ] **Support Team Trained**
  - Runbook reviewed with team
  - Troubleshooting scenarios practiced
  - Access and credentials shared securely

- [ ] **Escalation Path Defined**
  - Tier 1: DevOps/Migration team
  - Tier 2: Database team
  - Tier 3: Databricks support
  - Contact info and hours documented

---

## ✅ Post-Deployment Verification (First Week)

### Day 1: Smoke Tests

- [ ] **Run one full migration**
  - All steps complete without error
  - All artifacts generated
  - Tables visible in Databricks

### Days 2-3: Functional Tests

- [ ] **Verify Data Integrity**
  - Compare source row counts to Databricks
  - Check sample rows match
  - Verify primary keys are enforced

- [ ] **Verify DDL Quality**
  - Check all constraints are created
  - Check indexes are present
  - Check column types are correct

### Days 4-7: Production Load Tests

- [ ] **Run on Production Data**
  - Measure actual execution time
  - Monitor resource usage
  - Verify quality remains high

- [ ] **Test Batch Runs**
  - Multiple schemas in sequence
  - Verify no conflicts/race conditions
  - Check output isolation

- [ ] **Test Error Recovery**
  - Intentionally cause a failure (wrong password)
  - Verify error message is clear
  - Restart migration, should recover

---

## 📋 Sign-Off (Production Approval)

**Before promoting to production, get approval from:**

- [ ] **DevOps/Infrastructure Team** — Servers, networking, access OK?
- [ ] **Database Team** — Source DB access, performance impact OK?
- [ ] **Security Team** — Credentials handling, compliance OK?
- [ ] **Data Governance** — Data lineage, metadata OK?
- [ ] **Business Owner** — Timeline, scope, expectations OK?

**Sign-off form:**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| DevOps | | | |
| Database | | | |
| Security | | | |
| Governance | | | |
| Business | | | |

---

## ✅ Final Checklist

**Before going live, verify:**

- [ ] All tests pass ✅
- [ ] Security checklist complete ✅
- [ ] Runbooks written ✅
- [ ] Team trained ✅
- [ ] Sign-offs obtained ✅
- [ ] Rollback plan ready ✅
- [ ] Monitoring active ✅

---

## 🚀 Go Live!

You're ready to deploy to production. Document:

1. **Start date/time:** `_______________`
2. **Expected completion:** `_______________`
3. **Owner/contact:** `_______________`
4. **Rollback contact:** `_______________`

Good luck! 🎉

---

**Questions?** See:
- AZURE_DEPLOYMENT_GUIDE.md — Complete setup guide
- README.md — User documentation
- ARCHITECTURE.md — System design
- configs/README.md — Configuration reference
