# Technical Debt Register

Findings logged during the Module 3 (Relationship Discovery) architecture
review. **None of these are in scope for Module 3.** They are recorded here
so they are not rediscovered, and so a future milestone can pick them up
deliberately rather than incidentally.

Status legend: `OPEN` — logged, not started.

| ID | Severity | Area | Target |
|----|----------|------|--------|
| TD-01 | Medium | Canonical metadata | Milestone 4 |
| TD-02 | High | Metadata builder | Milestone 4 |
| TD-03 | Low | Orchestrator | Milestone 4 |
| TD-04 | Low | Output writer | Any |
| TD-05 | Low | CLI | Any |
| TD-06 | **High** | Security / config | **Immediate** |
| TD-07 | Medium | Postgres connector | Milestone 4 |
| TD-08 | Low | Documentation | Any |
| TD-09 | Medium | Profiler / consumers | Milestone 4 |
| TD-10 | Medium | Metadata builder | Milestone 4 |
| TD-11 | Low | Config | Milestones 4-10 |
| TD-12 | Low | Output writer | Milestone 9 |
| TD-13 | Medium | Canonical metadata | Milestone 4 |

---

## TD-01 — `MetadataPackage.profile` is always `null`

**Status:** OPEN · **Severity:** Medium · **File:** `migration/canonical/models.py:248-269`, `migration/metadata/builder.py:240-242`

`MetadataProfile` defines eleven roll-up counters (`total_schemas`,
`total_tables`, `total_columns`, `total_views`, `total_functions`,
`total_procedures`, `total_triggers`, `total_primary_keys`,
`total_foreign_keys`, `total_indexes`, `total_constraints`). `MetadataBuilder.build`
constructs `MetadataPackage(metadata=database)` and never populates the
`profile` field, so every `metadata.json` written to date carries
`"profile": null`.

**Impact:** Any consumer wanting headline counts must re-walk the whole tree.
Estimation (Milestone 10) and reporting (Milestone 9) both want these.

**Fix sketch:** Populate in `MetadataBuilder.build` after the tree is assembled.
Purely additive — no model change, no artifact-shape change (the key already exists).

---

## TD-02 — Views, functions, procedures and triggers are never built

**Status:** OPEN · **Severity:** High · **File:** `migration/metadata/builder.py:45-51`

`PostgresConnector` fully implements `extract_views`, `extract_procedures`,
`extract_functions` and `extract_triggers` (`postgres_connector.py:174-209`),
and `SchemaMetadata` has typed fields for all four
(`canonical/models.py:217-223`). But `MetadataBuilder.build` calls only 7 of
the 11 `extract_*` methods, so these four arrays are **permanently empty** in
`metadata.json`.

**Impact:** The capability is paid for but not delivered. A DDL generator
(Milestone 8) that must recreate views, or a lineage/documentation pass that
must read view definitions, has nothing to work from. Confirmed empirically:
the `bronze` run reports `views: 0, functions: 0, procedures: 0, triggers: 0`.

**Fix sketch:** Four additional loops in `build`, mapping to the existing
`ViewMetadata` / `FunctionMetadata` / `ProcedureMetadata` / `TriggerMetadata`
models. Note the connector returns `routine_schema`/`routine_name` and
`trigger_schema`/`event_object_table` — key names differ from the
`table_schema`/`table_name` convention used elsewhere, so the mapping is not
copy-paste.

---

## TD-03 — `validate_connection()` is implemented, tested, and never called

**Status:** OPEN · **Severity:** Low · **File:** `migration/orchestrator/orchestrator.py:53-55`

`BaseConnector.validate_connection` is part of the abstract contract
(`base.py:53-58`), implemented by `PostgresConnector` (`postgres_connector.py:71-80`)
and covered by a test (`test_postgres_connector.py:28-29`). The orchestrator
calls `connect()` and proceeds directly to metadata extraction without ever
issuing the round-trip check.

**Impact:** Low in practice — `connect()` already forces a real connection
eagerly (`postgres_connector.py:52`), so a dead connection fails fast anyway.
This is dead-but-correct code, not a bug.

---

## TD-04 — `ProfilePackage` annotated but not imported in the writer

**Status:** OPEN · **Severity:** Low · **File:** `migration/output/writer.py:85`

`write_profile(self, profile: ProfilePackage, ...)` references a name that is
never imported in that module. It survives only because
`from __future__ import annotations` (`writer.py:21`) makes all annotations
lazy strings.

**Impact:** No runtime failure today. It **will** raise `NameError` the moment
anything calls `typing.get_type_hints()` on `OutputWriter` — which is exactly
what FastAPI, Pydantic `validate_call`, and most schema-generation tooling do.
Given the stated goal of exposing this logic as REST APIs later
(`README.md:14-15`), this is a landmine on the declared roadmap.

**Fix sketch:** One import line. Module 3's `write_relationships` will import
its own model properly and must not copy this pattern.

---

## TD-05 — Dead code: `_print_discovered_tables`

**Status:** OPEN · **Severity:** Low · **File:** `migrate.py:87-103`

Superseded when `MigrationOrchestrator` took over the run. No caller remains.
The `rich.table.Table` import at `migrate.py:22` exists only for this function.

---

## TD-06 — Plaintext password committed in `config.yaml`

**Status:** OPEN · **Severity:** **High** · **File:** `config.yaml:11`

`source.password: '12345'` is hardcoded, and `config.yaml` is not listed in
`.gitignore` (only `.env` is). The config loader already fully supports
`${SOURCE_DB_PASSWORD}` and `${VAR:-default}` resolution
(`utils/config_loader.py:22`, `29-54`), with passing tests
(`test_config_loader.py:102-128`). The mechanism exists and is simply unused.

**Impact:** Any push to a shared remote leaks a credential. Flagged in
`README.md:130-134` and still present.

**Fix sketch:** Change to `password: ${SOURCE_DB_PASSWORD}`, add `config.yaml`
to `.gitignore`, ship a `config.example.yaml`. If the file was ever committed,
rotate the credential — removing it from HEAD does not remove it from history.

---

## TD-07 — Composite foreign keys may produce a cartesian product

**Status:** OPEN · **Severity:** Medium · **File:** `migration/connectors/postgres_connector.py:134-153`

`extract_foreign_keys` joins `key_column_usage` to `constraint_column_usage` on
`constraint_name` alone. For a **single-column** FK this is correct. For a
**composite** FK of N columns, `information_schema.constraint_column_usage`
returns N rows and `key_column_usage` returns N rows, and the unordered join
yields **N x N** rows — pairing each local column with each referenced column,
including wrong pairings.

**Impact:** Not yet observed. The `bronze` schema has no composite FKs (its two
composite-PK tables, `inventory` and `product_promotion`, each declare two
*separate* single-column FKs). The defect is latent and will surface on the
first source database that uses one.

**Fix sketch:** Join on ordinal position via `pg_constraint.conkey`/`confkey`,
or `referential_constraints` + `key_column_usage` on both sides with matching
`ordinal_position`. **Module 3 mitigates but does not fix this**: it groups FK
rows by `constraint_name` and de-duplicates column pairs, which limits the
blast radius to a possibly-wrong pairing rather than N x N phantom relationships.

---

## TD-08 — `ARCHITECTURE.md` is empty

**Status:** OPEN · **Severity:** Low · **File:** `ARCHITECTURE.md`

Zero bytes. The real architecture narrative currently lives in `README.md:56-128`
and in module docstrings.

---

## TD-09 — `min_value` / `max_value` are text-cast, so comparison is lexicographic

**Status:** OPEN · **Severity:** Medium · **File:** `migration/connectors/postgres_connector.py:255-256`

The profiling aggregate computes `MIN(col::text)` and `MAX(col::text)` for
*every* column regardless of type, and `ColumnProfile.min_value`/`max_value`
are typed `Optional[str]` (`profiler/models.py:40-42`).

**Impact:** For numeric columns the reported extremes are **lexicographic, not
numeric**. Confirmed in the `bronze` run: `audit_log.audit_id` reports
`min_value: "1"`, `max_value: "9"` over 10 rows with `distinct_count: 10` — the
true maximum is 10, but `"9" > "10"` as text. Any consumer that compares these
values numerically without re-parsing will draw wrong conclusions. Likewise
`min_length`/`max_length` are lengths of the *text rendering*, not of the value.

**Fix sketch (later):** emit typed `min_value`/`max_value` alongside the text
form, or record the cast explicitly in the artifact.

**Module 3 workaround (in scope, by design):** the range-containment check
parses text extremes back to a numeric type before comparing whenever both
columns are in a numeric type class, and skips the range signal entirely when
parsing fails. See §7 of `MODULE_3_DESIGN.md`.

---

## TD-10 — Views are materialized as `TableMetadata` entries

**Status:** OPEN · **Severity:** Medium · **File:** `migration/connectors/postgres_connector.py:100-107`, `migration/metadata/builder.py:61-79`

`extract_tables` selects from `information_schema.tables` without filtering
`table_type`, so views arrive alongside base tables. The builder then appends
every row to `SchemaMetadata.tables` as a `TableMetadata`, preserving the
distinction only in the `table_type` string field. `SchemaMetadata.views`
stays empty (see TD-02).

**Impact:** `DataProfiler` will run full aggregate scans against views as
though they were tables (`profiler/engine.py:67-73` iterates `schema.tables`
unconditionally). On an expensive view this is a silent performance cliff.
Not yet observed — the `bronze` schema has no views.

**Module 3 handling (in scope, by design):** the relationship engine filters
inference candidates to `table_type == 'BASE TABLE'`. Declared FKs are honored
regardless of type.

---

## TD-11 — Most `artifacts.*` toggles are inert

**Status:** OPEN · **Severity:** Low · **File:** `migration/models/config.py:110-119`

`ArtifactsConfig` exposes eight booleans. Only `profile` is honored
(`orchestrator.py:89`). `conceptual_model`, `logical_model`, `physical_model`,
`ddl`, `dml`, `report` and `estimation` all default to `true` and do nothing.

**Impact:** Config that appears to request work silently produces none. Each is
resolved by the milestone that implements the corresponding generator.

**Note:** The field is additive-with-default, which is what makes it safe for
Module 3 to add `relationships: bool = True` without breaking any existing
config file or test.

---

## TD-12 — `summary.txt` is an acknowledged placeholder

**Status:** OPEN · **Severity:** Low · **File:** `migration/output/writer.py:104-125`

Four lines of text, documented in-code as temporary and destined to become
`migration_report.md` (Milestone 9). `write_execution_summary` also takes
`database_name` only — it has no visibility into which artifacts were actually
produced, so it cannot report them.

---

## TD-13 — `ConstraintMetadata` records no columns

**Status:** OPEN · **Severity:** Medium · **Found during:** Module 3 implementation
**File:** `migration/canonical/models.py:107-110`

`ConstraintMetadata` carries only `constraint_name` and `constraint_type`. It
does **not** record which columns a constraint covers. The connector's
`extract_constraints` query has the same shape
(`postgres_connector.py:155-162`) — it selects from
`information_schema.table_constraints` without joining `key_column_usage`.

**Impact:** A `UNIQUE` constraint is visible by name but not by column, so
nothing downstream can tell *which* column is unique.

Concretely, this removed a planned cardinality rule from Module 3. The design
called for "source column carries a UNIQUE constraint → `ONE_TO_ONE`
(`STRUCTURAL`)". That rule is **not implemented**, because the information
does not exist in the canonical model. Uniqueness is therefore only detected
*observationally*, via profile statistics and gated behind
`MIN_ROWS_FOR_OBSERVED_CARDINALITY` — which correctly reports
`cardinality_source = OBSERVED` rather than `STRUCTURAL`, but means a genuinely
guaranteed one-to-one relationship is currently reported as many-to-one
whenever the child table is small.

The alternative — parsing `IndexMetadata.definition` for `CREATE UNIQUE INDEX`
— was rejected: that string is vendor-specific SQL, and parsing it inside an
engine would violate the "no source-specific logic" rule.

**Fix sketch:** Add `columns: List[str]` to `ConstraintMetadata` (additive,
defaults to empty, breaks nothing) and join `key_column_usage` in
`extract_constraints`. Module 3's cardinality classifier can then gain the
structural UNIQUE rule as a small, isolated addition.
