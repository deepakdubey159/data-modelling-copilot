# DB2 Live Connectivity Smoke Tests

## Overview

Optional smoke tests verify that DB2Connector can establish and validate connections to real DB2 databases. These tests are **skipped by default** and only run when DB2 credentials are provided via environment variables.

## Normal Test Suite (Always Runs)

All standard tests in `tests/test_db2_connector.py` mock `ibm_db` and **do not require a real DB2 instance**:

- 30 connector tests covering connection lifecycle, metadata extraction, profiling
- 15 metadata validation tests ensuring canonical metadata correctness
- 18 integration tests verifying end-to-end DB2 → Databricks pipeline

**Run with:** `pytest tests/test_db2_connector.py tests/test_db2_metadata_validation.py tests/test_db2_databricks_integration.py`

## Optional Live Connectivity Tests

Three smoke tests verify real DB2 connectivity. Located in `tests/test_db2_connector.py::TestDB2LiveConnectivity`:

1. **test_connect_to_live_db2** — Establish and close a connection
2. **test_validate_live_connection** — Validate an active connection
3. **test_extract_tables_from_live_db2** — Extract table metadata from real SYSCAT

### When Tests Are Skipped

Skipped when **any** required environment variable is missing:
```
DB2_TEST_HOST=<missing>
  → Test skipped (no DB2 server to connect to)
```

### When Tests Run

Tests execute when ALL required variables are set:
```bash
export DB2_TEST_HOST=prod-db2.example.com
export DB2_TEST_PORT=50000
export DB2_TEST_DATABASE=production
export DB2_TEST_USERNAME=db2admin
export DB2_TEST_PASSWORD=secret123

pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|---|---|
| `DB2_TEST_HOST` | Hostname or IP of DB2 server | `db2.example.com` or `192.168.1.100` |
| `DB2_TEST_DATABASE` | Database name | `production` or `testdb` |
| `DB2_TEST_USERNAME` | User with connection privileges | `db2admin` or `migration_user` |
| `DB2_TEST_PASSWORD` | Password for user | `secret123` |

### Optional

| Variable | Description | Default | Example |
|----------|---|---|---|
| `DB2_TEST_PORT` | TCP port for DB2 | `50000` | `50000` or `60000` |
| `DB2_TEST_SCHEMA` | Comma-separated schemas to query | `DB2INST1` | `PROD,STAGING` or `SYSADM` |

## Running the Smoke Tests

### Environment Setup (Bash/Linux/macOS)

```bash
export DB2_TEST_HOST=prod-db2
export DB2_TEST_PORT=50000
export DB2_TEST_DATABASE=production
export DB2_TEST_USERNAME=db2_migration
export DB2_TEST_PASSWORD=MySecurePassword123
export DB2_TEST_SCHEMA=PROD,STAGING

pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v
```

### Environment Setup (PowerShell/Windows)

```powershell
$env:DB2_TEST_HOST = "prod-db2"
$env:DB2_TEST_PORT = "50000"
$env:DB2_TEST_DATABASE = "production"
$env:DB2_TEST_USERNAME = "db2_migration"
$env:DB2_TEST_PASSWORD = "MySecurePassword123"
$env:DB2_TEST_SCHEMA = "PROD,STAGING"

pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v
```

### One-Liner (Bash)

```bash
DB2_TEST_HOST=prod-db2 DB2_TEST_PORT=50000 DB2_TEST_DATABASE=production \
DB2_TEST_USERNAME=db2admin DB2_TEST_PASSWORD=secret \
pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v
```

### Using Configuration File

Create `.env.db2_test`:
```
DB2_TEST_HOST=prod-db2
DB2_TEST_PORT=50000
DB2_TEST_DATABASE=production
DB2_TEST_USERNAME=db2admin
DB2_TEST_PASSWORD=secret123
DB2_TEST_SCHEMA=PROD,STAGING
```

Load and run:
```bash
export $(cat .env.db2_test | xargs)
pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v
```

## Security Considerations

### Credential Handling

1. **Never hardcode credentials** in test files, code, or repositories
2. **Use environment variables only** — they are read at test runtime
3. **Use `.env` files in `.gitignore`** if storing locally for development
4. **Use secret management** for CI/CD (GitHub Secrets, GitLab CI Variables, etc.)

### Connection Requirements

DB2Connector requires:
- **Network access** to the DB2 server on the specified port
- **User privileges** to:
  - Connect to the database (CONNECT privilege)
  - Query SYSCAT tables (SYSADM or similar role)
  - Call system functions like `SELECT 1 FROM SYSIBM.SYSDUMMY1`

### Recommended User Setup (DB2 Admin)

```sql
-- Create a dedicated migration user with minimal privileges
CREATE USER DB2_MIGRATION PASSWORD '<secure_password>';
GRANT CONNECT ON DATABASE TO USER DB2_MIGRATION;
GRANT IMPLICIT_SCHEMA ON DATABASE TO USER DB2_MIGRATION;

-- Grant read access to SYSCAT tables
GRANT SELECT ON TABLE SYSCAT.TABLES TO USER DB2_MIGRATION;
GRANT SELECT ON TABLE SYSCAT.COLUMNS TO USER DB2_MIGRATION;
GRANT SELECT ON TABLE SYSCAT.REFERENCES TO USER DB2_MIGRATION;
GRANT SELECT ON TABLE SYSCAT.TABCONST TO USER DB2_MIGRATION;
GRANT SELECT ON TABLE SYSCAT.KEYCOLUSE TO USER DB2_MIGRATION;
GRANT SELECT ON TABLE SYSCAT.INDEXES TO USER DB2_MIGRATION;
GRANT SELECT ON TABLE SYSCAT.VIEWS TO USER DB2_MIGRATION;
GRANT SELECT ON TABLE SYSCAT.ROUTINES TO USER DB2_MIGRATION;
GRANT SELECT ON TABLE SYSCAT.TRIGGERS TO USER DB2_MIGRATION;
```

## Test Results

### Skipped (No Environment Variables)

```
$ pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v

test_db2_connector.py::TestDB2LiveConnectivity::test_connect_to_live_db2 SKIPPED
test_db2_connector.py::TestDB2LiveConnectivity::test_validate_live_connection SKIPPED
test_db2_connector.py::TestDB2LiveConnectivity::test_extract_tables_from_live_db2 SKIPPED

===== 3 skipped in 0.06s =====
```

### Passed (Valid Credentials)

```
$ DB2_TEST_HOST=prod-db2 DB2_TEST_DATABASE=prod DB2_TEST_USERNAME=admin \
  DB2_TEST_PASSWORD=secret pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v

test_db2_connector.py::TestDB2LiveConnectivity::test_connect_to_live_db2 PASSED
test_db2_connector.py::TestDB2LiveConnectivity::test_validate_live_connection PASSED
test_db2_connector.py::TestDB2LiveConnectivity::test_extract_tables_from_live_db2 PASSED

===== 3 passed in 1.23s =====
```

### Failed (Invalid Credentials)

```
$ DB2_TEST_HOST=prod-db2 DB2_TEST_DATABASE=prod DB2_TEST_USERNAME=wrong \
  DB2_TEST_PASSWORD=badpass pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v

test_db2_connector.py::TestDB2LiveConnectivity::test_connect_to_live_db2 FAILED
...
migration.connectors.base.ConnectorError: Failed to connect to DB2 at prod-db2:50000/prod: ...
```

## CI/CD Integration

### GitHub Actions

```yaml
name: DB2 Live Connectivity Tests

on: [workflow_dispatch]  # Manual trigger only

jobs:
  db2-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v
        env:
          DB2_TEST_HOST: ${{ secrets.DB2_TEST_HOST }}
          DB2_TEST_PORT: ${{ secrets.DB2_TEST_PORT }}
          DB2_TEST_DATABASE: ${{ secrets.DB2_TEST_DATABASE }}
          DB2_TEST_USERNAME: ${{ secrets.DB2_TEST_USERNAME }}
          DB2_TEST_PASSWORD: ${{ secrets.DB2_TEST_PASSWORD }}
          DB2_TEST_SCHEMA: ${{ secrets.DB2_TEST_SCHEMA }}
```

### GitLab CI

```yaml
db2-smoke-tests:
  script:
    - pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v
  only:
    - schedules  # Run on schedule, manual trigger
  variables:
    DB2_TEST_HOST: $DB2_TEST_HOST
    DB2_TEST_PORT: $DB2_TEST_PORT
    DB2_TEST_DATABASE: $DB2_TEST_DATABASE
    DB2_TEST_USERNAME: $DB2_TEST_USERNAME
    DB2_TEST_PASSWORD: $DB2_TEST_PASSWORD
    DB2_TEST_SCHEMA: $DB2_TEST_SCHEMA
```

## Troubleshooting

### Connection Timeout

```
ConnectorError: Failed to connect to DB2 at prod-db2:50000/testdb: timeout
```

**Check:**
1. Is DB2 running? `telnet prod-db2 50000`
2. Is port correct? Check with DBA
3. Are firewall rules allowing connection?

### Authentication Failed

```
ConnectorError: Failed to connect to DB2 at prod-db2:50000/testdb: [IBM][IDS Shared Memory Protocol Driver] User identification and authentication setup failed
```

**Check:**
1. Username and password correct?
2. User has CONNECT privilege?
3. Account not locked or expired?

### Schema Not Found

```
No tables returned from DB2_TEST_SCHEMA
```

**Check:**
1. Schema name correct? (case-sensitive in SYSCAT)
2. User has privileges on schema?
3. Schema contains tables?

## FAQ

**Q: Do I need a real DB2 instance to run tests?**
A: No. The default test suite (30 tests) mocks DB2 and runs on any machine. The 3 smoke tests are optional and only run when DB2 credentials are provided.

**Q: Can I run the normal tests and smoke tests together?**
A: Yes. `pytest tests/test_db2_connector.py -v` runs all 33 tests (30 mocked + 3 skipped/run).

**Q: What if I provide invalid credentials?**
A: The smoke tests fail with `ConnectorError` showing the DB2 error message.

**Q: Are credentials logged?**
A: No. The connector only logs the connection attempt, not the credentials. Passwords are never printed.

**Q: Can I use SSL/TLS for the connection?**
A: Not yet. DB2Connector currently uses plain TCP. SSL support can be added via `ibm_db` connection string options if needed.

## Summary

- **33 tests total:** 30 mocked (always run) + 3 smoke tests (optional)
- **No real DB2 required** for normal development/CI
- **Smoke tests opt-in** via 4 required environment variables
- **Credentials safe:** Environment variables, never hardcoded
- **Production-ready:** Test validates real connectivity before migration
