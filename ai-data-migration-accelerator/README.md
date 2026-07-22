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

## Status: Milestone 2

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

Milestone 2 adds on top of that, unchanged:

- Canonical metadata model, metadata builder, output writer, and orchestrator
  (already in place before this milestone) — `python migrate.py --config
  config.yaml` still produces `metadata.json` exactly as before.
- **Data Profiler** (`migration/profiler/`): generates `profile.json`
  alongside `metadata.json` for every run (toggle: `artifacts.profile` in
  `config.yaml`, defaults to `true`). For every table discovered in the
  canonical metadata, it reports:
  - row count, duplicate row count (best-effort — `None` when it can't be
    computed for a given table, e.g. json/array columns)
  - per column: null count/percentage, distinct count/percentage, min/max
    value, min/max length
  - per free-form text column: a lightweight detected pattern (email,
    UUID, ISO date, phone-like, numeric string, upper-case code) based on
    a 200-row sample, reported only above an 80% match-confidence threshold
- Two new methods on `BaseConnector`/`PostgresConnector`: `profile_table`
  and `sample_column_values`. These query row data (not catalog metadata),
  so they're deliberately kept separate from the `extract_*` family.
- 12 new unit tests (profiler orchestration logic with a fake connector,
  identifier-quoting safety on the Postgres side) — 28 tests total, all
  passing, still no live database required.

## Architecture

```
migrate.py                     CLI entrypoint (argument parsing, orchestration, error surfacing)
migration/
  models/config.py             Pydantic models — canonical, validated config.yaml shape
  utils/config_loader.py       YAML → dict → env-var resolution → validated AppConfig
  utils/logging_setup.py       Rich console + file logging setup
  connectors/base.py           BaseConnector — abstract contract for all source DBs
  connectors/postgres_connector.py   PostgreSQL implementation (metadata + profiling)
  connectors/factory.py        Maps SourceType -> concrete connector class
  canonical/models.py          Canonical, vendor-agnostic metadata model
  metadata/builder.py          Native connector output -> canonical metadata
  profiler/models.py           Canonical, vendor-agnostic data-profile model
  profiler/engine.py           Canonical metadata + connector -> DatabaseProfile
  output/writer.py             Writes metadata.json, profile.json, summary.txt
  orchestrator/orchestrator.py Coordinates the full run end-to-end
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

- **Profiling stays separate from metadata extraction.** `extract_*`
  methods read catalog metadata (`information_schema`/`pg_catalog`) and
  never touch row data. Profiling queries actual table contents, so it's a
  distinct connector contract (`profile_table`, `sample_column_values`)
  and a distinct model tree (`migration/profiler/models.py` vs
  `migration/canonical/models.py`) — keeping "what shape is the data"
  and "what does the data actually contain" as separate concerns that can
  evolve independently (e.g. profiling could later support sampling-only
  mode for huge tables without touching the metadata side at all).

- **One table scan per table, not one query per column.** `profile_table`
  builds a single aggregate `SELECT` with one set of `COUNT`/`MIN`/`MAX`
  expressions per column, so profiling a 40-column table costs one pass
  over the data, not 40.

- **Duplicate-row detection degrades gracefully.** Full-row duplicate
  counting uses `ROW_NUMBER() OVER (PARTITION BY <all columns>)`, which
  fails for column types that can't be compared that way (e.g. `json`).
  Rather than aborting the whole table's profile, `duplicate_row_count`
  is set to `None` ("unknown") and profiling continues — callers must not
  treat `None` as zero.

⚠️ **Note on `config.yaml`:** the committed copy currently has a real
password hardcoded in `source.password`, and `config.yaml` itself isn't
git-ignored (only `.env` is). The config loader already supports
`${SOURCE_DB_PASSWORD}`-style env-var resolution — worth switching to that
before this is pushed anywhere shared.

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

28 tests: config validation/error paths, environment variable resolution,
the connector factory, connector connection-state handling, and (new in
Milestone 2) profiler orchestration logic plus Postgres identifier-quoting
safety.

## Suggested Git commit message

```
feat(milestone-2): data profiler generating profile.json

- Add profile_table / sample_column_values to BaseConnector + PostgresConnector
- Add migration/profiler/models.py — DatabaseProfile/TableProfile/ColumnProfile
- Add migration/profiler/engine.py — DataProfiler (row counts, null/distinct
  stats, min/max, duplicate detection, sample-based pattern detection)
- Wire OutputWriter.write_profile + orchestrator to emit profile.json
  alongside metadata.json, gated by artifacts.profile (default: true)
- Add artifacts.profile toggle to AppConfig (additive, default true —
  existing config.yaml files keep working unchanged)
- Add 12 unit tests (profiler engine with a fake connector, Postgres
  identifier-quoting safety)
```

## Next milestone (not started — awaiting approval)

Milestone 3: Relationship Discovery (`migration/relationship/`) — generate
`relationships.json` from the canonical metadata's existing PK/FK data
(explicit graph) plus inferred relationships from naming conventions and
profiled value overlap (e.g. `profile.json` min/max + distinct stats can
suggest likely FK candidates the source database never declared), building
toward join paths and a dependency graph for the conceptual model generator
in Milestone 4.
