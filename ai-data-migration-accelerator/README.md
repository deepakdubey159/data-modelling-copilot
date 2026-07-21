# AI Data Migration Accelerator

An AI-powered, config-driven CLI tool that connects to source databases,
extracts and normalizes metadata into a canonical model, uses an LLM to
understand schemas, and generates migration artifacts (DDL, DML, docs,
effort estimation) for a target platform.

This is a **CLI application**, not a chatbot or web app:

```bash
python migrate.py --config config.yaml
```

The core business logic is kept independent of the CLI so it can later be
exposed as REST APIs or microservices without rewrites.

## Status: Milestone 1

Scope delivered in this milestone:

- Repository structure and packaging (`pyproject.toml`, `requirements.txt`)
- Logging framework (Rich console output + timestamped file logs under `logs/`)
- YAML configuration loader with environment-variable resolution (`${VAR}` / `${VAR:-default}`)
- Fully validated configuration model (Pydantic) — bad config fails fast with a clear message
- Abstract `BaseConnector` interface defining the full contract every source
  connector must implement (tables, columns, PKs, FKs, constraints, indexes,
  views, procedures, functions, triggers, statistics)
- Working `PostgresConnector` implementation (SQLAlchemy + psycopg)
- Connector factory (`create_connector`) decoupling the CLI from concrete connector classes
- CLI (`migrate.py`) that: loads config → connects → validates connection → extracts tables → prints a discovered-schema report
- Unit tests for the config loader, connector factory, and connector state handling (16 tests, all passing)

## Architecture

```
migrate.py                     CLI entrypoint (argument parsing, orchestration, error surfacing)
migration/
  models/config.py             Pydantic models — canonical, validated config.yaml shape
  utils/config_loader.py       YAML → dict → env-var resolution → validated AppConfig
  utils/logging_setup.py       Rich console + file logging setup
  connectors/base.py           BaseConnector — abstract contract for all source DBs
  connectors/postgres_connector.py   PostgreSQL implementation
  connectors/factory.py        Maps SourceType -> concrete connector class
```

### Design decisions

- **Config-first, fail-fast validation.** Nothing downstream ever sees raw
  YAML or a dict — everything is a validated `AppConfig` Pydantic model.
  Invalid config (bad port, empty schema list, unresolved env var) is
  rejected at startup with a specific error, not a stack trace three layers
  deep in a connector.

- **Connector abstraction.** `BaseConnector` defines the *entire* eventual
  contract (all 11 `extract_*` methods) even though Milestone 1 only wires
  up `extract_tables`/`extract_columns` end-to-end through the CLI. This
  means adding Oracle, SQL Server, MySQL, etc. later is "implement this
  interface," not "redesign the interface."

- **Factory over direct instantiation.** `migrate.py` never imports
  `PostgresConnector` directly — it asks `create_connector(source_config)`
  for whatever connector matches `source.type`. Adding a new source type is
  a one-line addition to the factory, with zero changes to the CLI or
  orchestrator.

- **Native metadata stays native (for now).** Connectors return metadata in
  their own vendor-native shape (e.g. PostgreSQL's `information_schema`
  columns). Translating that into the canonical cross-vendor metadata model
  is explicitly deferred to Milestone 2 (`migration/canonical/`), keeping
  this milestone's connector responsible only for "talk to Postgres,"
  not "know about the canonical model too."

- **`information_schema` + `pg_catalog` over ORM introspection.** These are
  stable, documented, cross-version-compatible sources of truth for
  PostgreSQL metadata, rather than relying on SQLAlchemy's reflection API,
  which is convenient but abstracts away details (like exact constraint
  types) the AI layer will need later.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real credentials, never commit this file
```

## Configuration

Edit `config.yaml` (see the file in this repo for the full schema). Secrets
can be pulled from the environment instead of hardcoded:

```yaml
source:
  password: ${SOURCE_DB_PASSWORD}
```

## Running

```bash
python migrate.py --config config.yaml
```

Expected output on success: a connection confirmation, then a table listing
discovered schemas/tables/types, e.g.:

```
Connected successfully to 'sales' at localhost:5432

Schemas requested: public

        Discovered Tables
┏━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┓
┃ Schema ┃ Table     ┃ Type  ┃
┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━┩
│ public │ customers │ BASE TABLE │
│ public │ orders    │ BASE TABLE │
└────────┴───────────┴───────┘

Total tables discovered: 2
```

## Tests

```bash
pytest -q
```

16 tests covering config validation/error paths, environment variable
resolution, the connector factory, and connector connection-state handling.

## Suggested Git commit message

```
feat(milestone-1): project scaffold, config validation, base connector interface, PostgreSQL connector, CLI

- Add pyproject.toml / requirements.txt / repo structure
- Add Rich-backed logging framework with per-run log files
- Add Pydantic config models + YAML loader with env-var resolution
- Add BaseConnector abstract interface (full extract_* contract)
- Implement PostgresConnector (SQLAlchemy + psycopg, information_schema/pg_catalog)
- Add connector factory to decouple CLI from concrete connector classes
- Add migrate.py CLI: load config -> connect -> validate -> extract tables -> report
- Add 16 unit tests covering config loader and connector behavior
```

## Next milestone (not started — awaiting approval)

Milestone 2: canonical metadata model (`migration/canonical/`) — normalize
PostgreSQL's native metadata shape into the vendor-agnostic
Database → Schema → Table → Column → PK/FK/Index/Constraint → Statistics
hierarchy, plus extending the connector call sites in the orchestrator to
pull the remaining `extract_*` methods (PKs, FKs, indexes, etc.), not just
tables/columns.
