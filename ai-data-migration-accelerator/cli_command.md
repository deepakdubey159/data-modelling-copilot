CLI Commands  -  python migrate.py --help

The accelerator supports the following execution modes.

1. Generate Migration Artifacts

Generates the migration artifacts and databricks.sql locally.

python migrate.py --config config.yaml

Does not:

Publish to Databricks
Execute SQL

2. Generate and Publish SQL

Runs the complete migration pipeline and automatically publishes the generated databricks.sql to Databricks Workspace.

python migrate.py --config config.yaml --publish --force

Does not execute SQL.

Required environment variables:

DATABRICKS_HOST
DATABRICKS_TOKEN
DATABRICKS_WORKSPACE_PATH

The generated databricks.sql is retained locally and the same file is published to the configured Databricks Workspace path.

Recommended command for the end-to-end migration and publishing workflow:

python migrate.py --config config.yaml --publish
3. Publish an Existing SQL File

Publishes an already-generated SQL file without running the migration pipeline again.

python migrate.py --config config.yaml --publish-ddl "<path-to-databricks.sql>"

Example:

python migrate.py --config config.yaml --publish-ddl "output/bronze/20260825_121213_156502/databricks.sql"

Use this option when the SQL has already been generated and manually reviewed or modified.

4. Preview DDL Execution

Performs a dry run of a previously generated ddl.json.

python migrate.py --config config.yaml --execute-ddl "<path-to-ddl.json>"

No Databricks execution occurs unless --live is specified.

5. Execute DDL in Databricks

Executes the previously generated DDL against the configured Databricks target.

python migrate.py --config config.yaml --execute-ddl "<path-to-ddl.json>" --live

Use only after the generated DDL has been reviewed and approved.

Recommended End-to-End Workflow
DB2 Source
    ↓
Migration / AI Modeling
    ↓
Generate databricks.sql
    ↓
Publish to Databricks Workspace
    ↓
Manual Review
    ↓
Execute DDL after Approval
One-command generation + publishing
python migrate.py --config config.yaml --publish
Separate generation and publishing
python migrate.py --config config.yaml

Then:

python migrate.py --config config.yaml --publish-ddl "<path-to-databricks.sql>"
Execute after approval
python migrate.py --config config.yaml --execute-ddl "<path-to-ddl.json>" --live

Important: --publish publishes the generated SQL but does not execute it. This allows the generated SQL to be reviewed in Databricks Workspace before execution.