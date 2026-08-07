# Module 3 — Relationship Discovery Engine

**Status:** **Implemented.** 66 tests, all passing; 96 in the suite overall.
**Approved approach:** Option A — metadata + profile only.
**Hard constraint:** `BaseConnector` is **not** modified. No new SQL. No new database round-trips.

## Deviations from this design, as built

Three, all deliberate:

1. **Cardinality rule C2 (UNIQUE constraint → `ONE_TO_ONE`) is not
   implemented.** `ConstraintMetadata` records a constraint's name and type
   but not its columns, so the canonical model cannot say *which* column is
   unique. Parsing `IndexMetadata.definition` for `CREATE UNIQUE INDEX` was
   rejected as vendor-specific logic inside an engine. Logged as **TD-13**;
   uniqueness is currently detected observationally only. Remaining rules
   renumbered accordingly.

2. **Six injected collaborator classes collapsed into one `RelationshipEngine`
   with phase methods.** Per the "avoid unnecessary abstractions" directive.
   `rules.py` and `graph.py` remain separate — they are genuinely different
   concerns (tunables, and domain-free algorithms) rather than layers.

3. **`dependency_order` is grouped by `(depth, name)`**, not raw Kahn's
   emission order. Both are valid topological orders; depth-grouping
   additionally tells a migration planner which tables can be loaded in
   parallel. Validity is preserved because a child's depth is always strictly
   greater than every parent's.

---

## 1. Responsibilities

Module 3 turns two existing artifacts into a **relationship graph**.

### In scope

| # | Responsibility |
|---|---|
| R1 | Extract the **explicit** relationship graph from declared foreign keys in the canonical metadata |
| R2 | Reconstruct **composite** foreign keys by grouping per-column FK rows under their constraint name |
| R3 | Generate **inferred** relationship candidates from naming conventions |
| R4 | Score candidates using profile statistics, and reject those contradicted by the data |
| R5 | Classify **cardinality** (1:1, 1:N, N:1, M:N) and **relationship type** (identifying / non-identifying / self-referencing) |
| R6 | Detect **junction tables** and derive the logical many-to-many relationships they represent |
| R7 | Detect **self-referencing** relationships (hierarchies) |
| R8 | Produce a **dependency order** — a safe parent-before-child table sequence for migration and load |
| R9 | Detect **cycles** that make a total dependency order impossible |
| R10 | Identify **orphan tables** with no relationships in either direction |
| R11 | Attach machine- and human-readable **evidence** to every inferred relationship |
| R12 | Serialize the result to `relationships.json` |

### Explicitly out of scope

| Excluded | Reason |
|---|---|
| Any new connector method or SQL | Option A constraint. Contract frozen. |
| Value-overlap / inclusion-dependency verification | Requires querying data. Deferred to a possible Option B. |
| Semantic alias resolution (`orders.sales_rep_id` → `employee`) | Not derivable from naming or aggregate statistics. Belongs to the LLM layer (§9). |
| Join-path enumeration between arbitrary table pairs | Consumes this graph. Belongs to the planner/query layer. |
| Business-meaning naming of relationships ("customer places order") | LLM layer. |
| Fixing any item in `TECHNICAL_DEBT.md` | Logged, deliberately deferred. |

### The invariant that governs this module

> **The engine contains no SQL and no database access. It is a pure function of
> `(DatabaseMetadata, DatabaseProfile) -> RelationshipPackage`.**

This mirrors `metadata/builder.py` ("This module should NEVER contain SQL",
`builder.py:6`) and `profiler/engine.py` ("no SQL and no vendor-specific
logic", `engine.py:11-12`). It is also what makes the module fully unit
testable without a database (§11).

---

## 2. Package Structure

Module 3 lands in `migration/relationship/` — the package already exists,
reserved and empty.

```
migration/relationship/
    __init__.py       (currently empty — stays empty, consistent with every other package)
    models.py         Pydantic models + enums. The shape of relationships.json.
    rules.py          Naming rules, type-compatibility classes, scoring weights, thresholds.
    graph.py          Pure graph algorithms: topological sort, cycle detection, orphans.
    engine.py         RelationshipEngine — orchestrates the five discovery phases.
```

Module 2 shipped as two files (`models.py` + `engine.py`). Module 3 uses four
because it has two genuinely separable concerns that Module 2 did not:

- **`rules.py`** isolates every tunable — naming patterns, type classes,
  scoring weights, the confidence threshold. These are the things most likely
  to be adjusted after seeing real-world schemas, and the things a reviewer
  most needs to read in one place. Keeping them out of `engine.py` means
  tuning inference never risks touching orchestration logic. Precedent:
  `profiler/engine.py:38-54` already hoists `_PATTERNS`, `_MIN_PATTERN_RATIO`
  and `_TEXT_TYPES` to module level for exactly this reason — `rules.py` is
  that instinct given its own file, because Module 3 has roughly five times
  as many knobs.

- **`graph.py`** contains algorithms with **zero domain knowledge** —
  topological sort, cycle detection, orphan detection. It operates on
  `(node, edges)` and knows nothing about foreign keys. It is therefore
  reusable verbatim by the migration planner (Milestone 7) and independently
  testable with trivial fixtures.

Files touched outside the package are listed in §10.

---

## 3. Classes

Composition, not inheritance — per `CLAUDE.md` ("Prefer composition over
inheritance", "Small reusable classes", "Dependency injection where
appropriate"). `RelationshipEngine` is the only public entry point; the five
collaborators are constructor-injected with working defaults so tests can
substitute any one of them in isolation.

```
RelationshipEngine
  ├── ExplicitRelationshipExtractor   R1, R2
  ├── NamingCandidateGenerator        R3
  ├── ProfileEvidenceScorer           R4
  ├── CardinalityClassifier           R5, R7
  ├── JunctionDetector                R6
  └── DependencyGraphBuilder          R8, R9, R10   (graph.py)
```

### `RelationshipEngine` — `engine.py`

The public face of the module.

```
RelationshipEngine(metadata: DatabaseMetadata, profile: DatabaseProfile | None = None)
    .discover() -> RelationshipPackage
```

`profile` is **optional**. If `artifacts.profile` is `false`, Module 3 still
runs and still produces the complete declared graph, junctions, cardinality
from structure, and dependency order — it simply skips profile-based scoring
and emits fewer inferred relationships. Degrading rather than failing matches
how the profiler treats an unavailable duplicate count
(`postgres_connector.py:295-324`) and a failed table profile
(`profiler/engine.py:91-98`).

Responsibilities: build lookup indexes once, run the five phases in order,
sort deterministically, assemble the package. It performs no analysis itself.

### `ExplicitRelationshipExtractor` — `engine.py`

Walks `TableMetadata.foreign_keys` and emits `DECLARED` relationships at
confidence `1.0`.

The non-obvious part: `ForeignKeyMetadata` is **per column**, not per
constraint — it carries singular `column` and `referenced_column` fields
(`canonical/models.py:79-88`). A composite FK therefore arrives as multiple
rows sharing one `constraint_name`. This class groups by
`(schema, table, constraint_name)`, de-duplicates `(local, referenced)` column
pairs, and orders columns to produce a single relationship with
`source_columns: [...]` / `target_columns: [...]`.

De-duplication is deliberate mitigation for **TD-07** (the composite-FK
cartesian-product risk in `extract_foreign_keys`). It cannot repair a wrong
pairing, but it prevents N x N phantom relationships from reaching the artifact.

### `NamingCandidateGenerator` — `engine.py`, rules from `rules.py`

For every column not already covered by a declared FK, proposes candidate
targets by naming convention. Emits `RelationshipCandidate` objects (internal,
not serialized) carrying a base score and the rule that fired.

Hard gates applied before a candidate is ever scored:
- target table must exist and have `table_type == 'BASE TABLE'` (**TD-10**)
- target column must be a single-column primary key
- source and target must be in the same **type-compatibility class** (§7)
- a candidate matching an existing `DECLARED` relationship is dropped — the
  declared graph always wins

### `ProfileEvidenceScorer` — `engine.py`, weights from `rules.py`

Applies profile-derived adjustments to each candidate's base score, appends a
human-readable `evidence` string for every signal considered, and can
**hard-reject** a candidate outright when the data contradicts it.

Handles the text-cast extremes trap (**TD-09**) by re-parsing `min_value` /
`max_value` numerically before any range comparison, and skipping the range
signal when parsing fails.

If `profile` is `None`, this class is a no-op pass-through that records
`"no profile available"` as evidence.

### `CardinalityClassifier` — `engine.py`

Assigns `cardinality` and `relationship_type` from structural facts first
(PK/unique membership, nullability), then from observed statistics where
structure is silent. Records which of the two decided the outcome in
`cardinality_source`. Rules table in §8.

### `JunctionDetector` — `engine.py`

Flags tables whose primary key is composed **entirely** of foreign-key columns
referencing **two or more distinct** tables, and derives one
`MANY_TO_MANY_LOGICAL` relationship per pair of referenced parents.

### `DependencyGraphBuilder` — `graph.py`

Domain-free. Kahn's algorithm for topological ordering, DFS for cycle
detection, degree counting for orphans. Ties are broken by qualified name so
output is byte-stable across runs.

---

## 4. Models

New file `migration/relationship/models.py`. A **third parallel model tree**,
alongside `canonical/models.py` and `profiler/models.py`, for the same reason
Module 2 kept its own: metadata describes *shape*, profile describes *content*,
relationships describe *structure between entities*. Joinable by name;
independently evolvable.

### Enums

```
DiscoveryMethod    DECLARED | INFERRED_NAMING | INFERRED_PROFILE
                   | DERIVED_JUNCTION | INFERRED_VERIFIED (reserved, §9)

RelationshipType   IDENTIFYING | NON_IDENTIFYING | SELF_REFERENCING
                   | MANY_TO_MANY_LOGICAL

Cardinality        ONE_TO_ONE | ONE_TO_MANY | MANY_TO_ONE | MANY_TO_MANY | UNKNOWN

CardinalitySource  STRUCTURAL | OBSERVED | UNKNOWN

ConfidenceBand     CERTAIN | HIGH | MEDIUM | LOW
```

All are `str`-valued enums, matching `models/config.py:18-58`, so they
serialize as readable strings rather than integers.

### `Relationship`

The atomic unit of the artifact.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Deterministic, stable across runs. Format: `<src_schema>.<src_table>(<cols>)-><tgt_schema>.<tgt_table>(<cols>)`. Lets downstream consumers — including an LLM — reference a relationship without restating it. |
| `constraint_name` | `str \| None` | Populated for `DECLARED`; `None` for inferred. |
| `source_schema` | `str` | |
| `source_table` | `str` | |
| `source_columns` | `list[str]` | **List**, to carry composite FKs. Single-column is a one-element list. |
| `target_schema` | `str` | |
| `target_table` | `str` | |
| `target_columns` | `list[str]` | Positionally aligned with `source_columns`. |
| `relationship_type` | `RelationshipType` | |
| `cardinality` | `Cardinality` | |
| `cardinality_source` | `CardinalitySource` | Whether structure or observation decided it. |
| `discovery_method` | `DiscoveryMethod` | |
| `confidence` | `float` | `0.0`-`1.0`. Always `1.0` for `DECLARED`. |
| `confidence_band` | `ConfidenceBand` | Derived from `confidence`. Convenience for consumers that should not hardcode thresholds. |
| `is_self_referencing` | `bool` | |
| `is_optional` | `bool` | `True` when any source column is nullable — optional participation. |
| `is_identifying` | `bool` | `True` when source columns are a subset of the source table's PK. |
| `evidence` | `list[str]` | Ordered, human-readable rationale. Empty for `DECLARED` except the constraint name. |

### `JunctionTable`

`schema_name`, `table_name`, `connected_tables: list[str]`,
`key_columns: list[str]`, `payload_columns: list[str]`, `is_pure: bool`.

`is_pure` distinguishes a pure link table (PK columns are the *only* columns)
from an associative entity carrying its own attributes — a distinction the
conceptual model generator (Milestone 4) needs, because the latter is a real
entity and the former usually is not.

### `GraphNode`

`schema_name`, `table_name`, `table_type`, `is_orphan`,
`inbound_relationship_count`, `outbound_relationship_count`,
`depth` (topological level, `0` = no dependencies).

### `RelationshipSummary`

Roll-up counters: `total_relationships`, `declared_count`, `inferred_count`,
`derived_count`, `junction_table_count`, `self_referencing_count`,
`orphan_table_count`, `cycle_count`, `max_dependency_depth`,
`tables_analyzed`, `columns_analyzed`.

Deliberately populated at build time — unlike `MetadataProfile`, which was
defined and left `null` (**TD-01**). Module 3 does not repeat that.

### `RelationshipGraph`

`database_name`, `nodes: list[GraphNode]`, `relationships: list[Relationship]`,
`junction_tables: list[JunctionTable]`, `dependency_order: list[str]`,
`cycles: list[list[str]]`, `orphan_tables: list[str]`, `summary`.

### `RelationshipPackage`

`{ relationships: RelationshipGraph }` — the serialized root, exactly
mirroring `MetadataPackage` and `ProfilePackage`.

**Naming note:** the wrapper key is `relationships` (not `relationship`) to
match the artifact filename `relationships.json` and the name already fixed in
`docs/VISION.md`.

---

## 5. Execution Flow

### Within the engine

```
DatabaseMetadata ──┐
                   ├──→  RelationshipEngine.discover()  ──→  RelationshipPackage
DatabaseProfile ───┘         (pure, in-memory, no I/O)

  Phase 0  Index          table / PK / unique / column / profile lookups, built once
  Phase 1  Explicit       declared FKs → Relationship(DECLARED, 1.0)   [composite grouping]
  Phase 2  Candidates     naming rules → RelationshipCandidate[]        [gated, deduped]
  Phase 3  Score          profile evidence → confidence, or hard-reject
                          keep only confidence >= MIN_INFERENCE_CONFIDENCE
  Phase 4  Classify       cardinality, relationship type, junctions, M:N derivation
  Phase 5  Graph          nodes, depth, dependency_order, cycles, orphans
           Sort           deterministic ordering → RelationshipPackage
```

Phases are strictly ordered: Phase 2 needs Phase 1's output to suppress
duplicates; Phase 4's junction detection needs the union of declared and
accepted-inferred edges; Phase 5 needs the final edge set.

### Within the pipeline

Module 3 becomes **step 11.5**, between profiling and the execution summary.
Both inputs are already live in `orchestrator.run()` local scope at
`orchestrator.py:106` — no re-extraction, no re-query, no re-read from disk.

```
 8. MetadataBuilder.build()            → metadata   (MetadataPackage)
 9. writer.create_run_directory()
10. writer.write_metadata()            → metadata.json
11. if artifacts.profile:
        DataProfiler.profile()         → profile    (ProfilePackage)
        writer.write_profile()         → profile.json
11.5 if artifacts.relationships:                              ← MODULE 3
        RelationshipEngine(
            metadata.metadata,
            profile.profile if profile else None
        ).discover()                   → relationships
        writer.write_relationships()   → relationships.json
12. writer.write_execution_summary()   → summary.txt
13. print banner (now including Relationships File when written)
14. finally: connector.disconnect()
```

Note the unwrapping: the profiler is handed `metadata.metadata` — the inner
`DatabaseMetadata`, not the package (`orchestrator.py:95`). Module 3 follows
the identical convention and takes `profile.profile`.

**Why here.** After profiling, because profile statistics are an *input* to
scoring. Before the planner and generators, because migration ordering,
conceptual models and DDL all consume this graph. Inside the existing
`try/finally`, so the connector is still released on any failure.

**Failure policy.** Module 3 performs no I/O and cannot raise connector errors.
A defect in inference should not destroy a successful metadata + profile run,
so the orchestrator block logs and continues on unexpected exceptions rather
than aborting — the same "degrade, don't abort" stance as
`profiler/engine.py:91-98`.

---

## 6. JSON Schema

`relationships.json`, written to the same timestamped run directory as its
siblings.

```
{
  "relationships": {
    "database_name":     string,
    "nodes":             GraphNode[],
    "relationships":     Relationship[],
    "junction_tables":   JunctionTable[],
    "dependency_order":  string[],        // "schema.table", parents first
    "cycles":            string[][],      // each inner array = one cycle
    "orphan_tables":     string[],
    "summary":           RelationshipSummary
  }
}
```

**Relationship** — see §4 for the full field table. Types:
`id`, `constraint_name`(nullable), `source_schema`, `source_table`,
`source_columns[]`, `target_schema`, `target_table`, `target_columns[]`,
`relationship_type`, `cardinality`, `cardinality_source`, `discovery_method`,
`confidence`(number), `confidence_band`, `is_self_referencing`(bool),
`is_optional`(bool), `is_identifying`(bool), `evidence[]`.

**GraphNode** — `schema_name`, `table_name`, `table_type`, `is_orphan`,
`inbound_relationship_count`, `outbound_relationship_count`, `depth`.

**JunctionTable** — `schema_name`, `table_name`, `connected_tables[]`,
`key_columns[]`, `payload_columns[]`, `is_pure`.

### Guarantees

1. **Deterministic.** Two runs over an unchanged database produce
   byte-identical files. All collections are explicitly sorted; nothing relies
   on dict iteration order. This makes the artifact diffable across runs — the
   basis for schema-drift detection later.
2. **Self-describing.** Every relationship states how it was found and how much
   to trust it. A consumer never has to guess whether an edge is a real
   constraint or a heuristic.
3. **Joinable.** `schema` / `table` / `column` names are the join keys to
   `metadata.json` and `profile.json`, matching the convention Module 2
   established (`profiler/models.py:4-10`).
4. **Additive evolution.** New fields may be added; existing fields keep their
   meaning. Consumers must ignore unknown fields.

### Direction convention — normative

> An edge always points **from the table that holds the foreign key** to the
> table that holds the referenced key. `source` is the child. `target` is the
> parent.

Therefore the default cardinality of an FK edge is `MANY_TO_ONE`, not
`ONE_TO_MANY`. Stating this explicitly is not pedantry: silently inverted edge
direction is the single most common defect in graph artifacts, and it would
reverse the load order in Milestone 7.

`dependency_order` follows the opposite arrow: **parents first**, so the list
is a safe insertion sequence.

---

## 7. Relationship Discovery Algorithm

### Phase 0 — Index construction

Built once, O(n) over the metadata:

- `tables[(schema, table)] -> TableMetadata`
- `primary_keys[(schema, table)] -> list[str]` (ordered PK columns)
- `unique_columns[(schema, table)] -> set[str]` from `ConstraintMetadata`
  where `constraint_type == 'UNIQUE'`
- `columns[(schema, table, column)] -> ColumnMetadata`
- `column_profiles[(schema, table, column)] -> ColumnProfile`
- `table_profiles[(schema, table)] -> TableProfile`
- `pk_name_index[column_name] -> list[(schema, table)]` — reverse index from a
  PK column name to the tables that use it as a single-column PK. This is what
  makes naming inference O(columns) instead of O(columns x tables).

Only `table_type == 'BASE TABLE'` entries populate `pk_name_index` (**TD-10**).

### Phase 1 — Explicit extraction

```
group TableMetadata.foreign_keys by (schema, table, constraint_name)
for each group:
    pairs = dedupe[(fk.column, fk.referenced_column) for fk in group]
    emit Relationship(
        source_columns  = [p[0] for p in pairs],
        target_columns  = [p[1] for p in pairs],
        discovery_method = DECLARED,
        confidence       = 1.0,
        evidence         = ["declared foreign key constraint '<name>'"]
    )
```

Confidence is `1.0` unconditionally. A declared constraint is enforced by the
database; profile statistics can never lower confidence in it. If observed data
appears to contradict a declared FK, that is a defect in the profile, not
evidence against the constraint.

### Phase 2 — Naming candidate generation

Applied to each column that is **not** already part of a declared FK.

| Rule | Pattern | Example | Base |
|---|---|---|---|
| **N1** | Column name **is** a single-column PK name of another base table | `warehouse.city_id` → `city.city_id` | `0.70` |
| **N2** | `<entity>_id`, `<entity>` resolves to a table after singular/plural normalization | `payment.order_id` → `orders.order_id` | `0.65` |
| **N3** | `<entity>id`, no separator | `payment.orderid` → `orders.order_id` | `0.55` |

Normalization for N2 handles the plural/singular mismatch that is present in
the reference schema itself — the table is `orders` but the column is
`order_id`. Rules: exact, `+s`, `+es`, `y`→`ies`, and the reverse of each.
Case-insensitive; underscores and camelCase both normalized.

Semantic aliases such as `orders.sales_rep_id` → `employee.employee_id` are
**not** attempted. No naming rule or aggregate statistic can recover that link;
guessing would manufacture false positives. It is correctly captured as a
declared FK here, and is the archetypal case for the LLM layer (§9).

**Hard gates** — a candidate failing any of these is discarded before scoring:

- target table exists and is `BASE TABLE`
- target column is a single-column primary key
- candidate does not duplicate a `DECLARED` relationship
- source table is not the target table **unless** the column name differs from
  the PK name (blocks the degenerate `customer.customer_id` → `customer` self-match)
- source and target share a type-compatibility class

**Type-compatibility classes.** Coarse buckets — `INTEGER`, `NUMERIC`, `TEXT`,
`UUID`, `TEMPORAL`, `BOOLEAN`, `BINARY`, `JSON`, `OTHER` — mapped from the
`data_type` string. Only same-class pairs proceed; `INTEGER`/`NUMERIC` are
treated as mutually compatible. This introduces mild vendor coupling into an
engine, which is the same trade-off Module 2 already accepted with `_TEXT_TYPES`
(`profiler/engine.py:54`). It is confined to a single constant in `rules.py`,
so adding a second vendor is a dictionary edit rather than a code change.

### Phase 3 — Profile-based scoring

Each signal adjusts the base score additively and appends an `evidence` string.
Score is clamped to `[0.0, 1.0]`.

| Signal | Condition | Adjust |
|---|---|---|
| Target is single-column PK | always true post-gate | `+0.15` |
| Exact `data_type` match | source and target identical type string | `+0.10` |
| **Inclusion holds** | source `distinct_count` <= target `distinct_count` | `+0.10` |
| **Inclusion violated** | source `distinct_count` > target `distinct_count` | **hard reject** |
| Range containment holds | source `[min,max]` within target `[min,max]` (type-aware) | `+0.10` |
| Range containment violated | source range escapes target range (type-aware) | `-0.35` |
| Pattern agreement | both `detected_pattern` set and equal | `+0.05` |
| No evidence available | source or target `row_count == 0` | `-0.10` |
| Profile absent | `profile is None` | `0.00`, evidence noted |

**Inclusion violation is a hard reject, not a penalty.** If a child column
holds more distinct values than its supposed parent's primary key, it cannot be
a foreign key into it. This is a logical impossibility, not weak evidence — the
one place where aggregate statistics alone give a *sound* negative. It is the
main reason profile data materially improves inference under Option A.

**Range containment is type-aware — see TD-09.** `min_value` / `max_value` are
`MIN(col::text)` / `MAX(col::text)` (`postgres_connector.py:255-256`), so they
compare **lexicographically**. In the reference run `audit_log.audit_id` reports
`max_value: "9"` across 10 distinct values — the true maximum is 10. Comparing
those strings directly would produce false containment violations on any table
crossing a digit boundary. The scorer therefore parses both extremes back to a
number when both columns are in a numeric class, and **skips the range signal
entirely** if parsing fails. Never compare these as strings.

**Acceptance threshold:** `MIN_INFERENCE_CONFIDENCE = 0.60`. Below it, the
candidate is dropped rather than emitted with a low score — the same stance as
`_MIN_PATTERN_RATIO = 0.8` (`profiler/engine.py:49`), where Module 2 chose to
report nothing rather than a low-confidence guess. Silence beats noise: a
downstream LLM shown a 0.3-confidence relationship will tend to rationalize it.

Accepted candidates are labelled `INFERRED_PROFILE` when at least one profile
signal contributed, `INFERRED_NAMING` when the profile was unavailable or
silent.

### Phase 4 — Classification and derivation

Cardinality and type per §8. Then junction detection:

```
table is a junction  ⟺  PK columns are non-empty
                     ∧  every PK column participates in some FK of that table
                     ∧  those FKs reference >= 2 distinct tables

is_pure          ⟺  the table has no columns outside its PK
payload_columns  =   columns not in the PK
```

For each junction, emit one `MANY_TO_MANY_LOGICAL` relationship per unordered
pair of referenced parents, `discovery_method = DERIVED_JUNCTION`,
`confidence = 1.0` when derived from declared FKs.

Validated against the reference schema: `inventory` (PK
`warehouse_id, product_id`, both FKs, plus payload columns → junction,
`is_pure = false`) and `product_promotion` (PK `product_id, promotion_id`, both
FKs, no other columns → junction, `is_pure = true`) qualify. `order_item` (PK
`order_id, line_number` — `line_number` is not a foreign key) correctly does
**not**, and is a weak/dependent entity instead. That last case is the
discriminator that proves the rule is not simply "composite PK means junction."

### Phase 5 — Graph assembly

`DependencyGraphBuilder` consumes only **physical** edges — `DECLARED`,
`INFERRED_NAMING`, `INFERRED_PROFILE`. `DERIVED_JUNCTION` edges are logical
annotations for the conceptual model and are **excluded** from traversal;
including them would create spurious ordering constraints between two parents
that have no direct dependency.

- **Depth / `dependency_order`:** Kahn's algorithm, parents first. Ties broken
  by qualified name for determinism.
- **Self-loops are excluded from `cycles`.** A self-referencing FK such as
  `employee.manager_id -> employee.employee_id` constrains *row* insertion
  order, not *table* order — the table can still be created and loaded in one
  step (nullable parent first, or deferred constraint). Reporting it as a cycle
  would falsely suggest the schema cannot be ordered. It is surfaced through
  `is_self_referencing` and `SELF_REFERENCING` instead.
- **True cycles** (A→B→A, or longer) are reported in `cycles`. Members are
  appended to `dependency_order` after all acyclic tables, in stable name
  order, so the list always contains every table. Milestone 7 will need this to
  emit deferred-constraint handling.
- **Orphans:** nodes with zero inbound and zero outbound physical edges.

### Determinism

Final sort keys: relationships by
`(source_schema, source_table, source_columns, target_schema, target_table)`;
nodes and junctions by qualified name; `dependency_order` by
`(depth, qualified_name)`. Every connector query already ends in `ORDER BY`
(`postgres_connector.py`, all `extract_*`); this extends the same discipline to
the engine.

---

## 8. Cardinality Rules

Evaluated in order; **first match wins**. Structural evidence always outranks
observed evidence — structure is a guarantee, observation is a snapshot of
today's data.

| # | Condition | Cardinality | Type | Source |
|---|---|---|---|---|
| C1 | Source columns are exactly the source table's **full PK** | `ONE_TO_ONE` | `IDENTIFYING` | `STRUCTURAL` |
| C2 | Source columns carry a **UNIQUE** constraint | `ONE_TO_ONE` | `NON_IDENTIFYING` | `STRUCTURAL` |
| C3 | Source table == target table | `MANY_TO_ONE` | `SELF_REFERENCING` | `STRUCTURAL` |
| C4 | Source columns are a **proper subset** of the source PK | `MANY_TO_ONE` | `IDENTIFYING` | `STRUCTURAL` |
| C5 | Junction-derived parent pair | `MANY_TO_MANY` | `MANY_TO_MANY_LOGICAL` | `STRUCTURAL` |
| C6 | Profile available, `distinct_count == row_count`, `null_count == 0`, `row_count > 0` | `ONE_TO_ONE` | `NON_IDENTIFYING` | `OBSERVED` |
| C7 | Default | `MANY_TO_ONE` | `NON_IDENTIFYING` | `STRUCTURAL` |
| C8 | No profile and no structural signal | `MANY_TO_ONE` | `NON_IDENTIFYING` | `UNKNOWN` |

### Notes

- **C1 vs C4.** Full PK means at most one row per parent — a genuine 1:1. A
  proper subset (the `order_item.order_id` case, PK `order_id, line_number`)
  permits many children per parent, so N:1 with identifying participation. This
  distinction is precisely what a logical model generator needs to draw an
  identifying versus non-identifying relationship.
- **C3 before C4.** A self-reference could otherwise be misclassified when the
  FK column happens to sit inside the PK.
- **C6 is observation, never a guarantee.** A column can be unique in today's
  data purely by accident — 10 rows with 10 distinct values proves nothing.
  `cardinality_source = OBSERVED` exists so a consumer can distinguish
  "the database guarantees this" from "the current data happens to look this
  way." C6 is skipped entirely when `row_count` is small (below
  `MIN_ROWS_FOR_OBSERVED_CARDINALITY`, default `100`) — the reference tables
  hold 10 rows each and must not be allowed to manufacture false 1:1 claims.
- **`is_optional`** is orthogonal to cardinality: it is `True` when any source
  column is nullable, expressing optional participation (0..1 rather than
  exactly 1). `employee.manager_id` is nullable — the hierarchy root has no
  manager.
- **Inverse direction is never emitted.** One edge per relationship, always
  child → parent. Consumers needing the 1:N view invert it themselves. Emitting
  both would double every count and corrupt the topological sort.

---

## 9. Future AI Compatibility

`docs/VISION.md` commits to "deterministic engines, AI orchestration,
explainable outputs." This artifact is designed as **LLM input**, not just
machine input.

**1. Every edge carries provenance.** `discovery_method`, `confidence`,
`confidence_band` and `evidence` mean a prompt never has to present a
relationship as an unqualified fact. The LLM can be instructed to treat
`DECLARED` as ground truth and reason only about the inferred remainder — and
`evidence` gives it the reasoning to evaluate, not just a number to trust.

**2. Stable IDs make round-tripping possible.** A deterministic `id` lets the
LLM return `{"id": "...", "verdict": "reject", "reason": "..."}` instead of
restating the relationship — cheaper, and immune to paraphrase drift when
merging AI output back into the artifact.

**3. `INFERRED_VERIFIED` is reserved now.** If Option B is approved later,
value-overlap verification adds a *value* to an existing enum and populates
existing fields. No model change, no artifact-shape change, no consumer
rewrite. Confidence bands are already the interface consumers should read,
which is why `confidence_band` is materialized rather than left to each
consumer's own thresholds.

**4. Naming is left to the LLM by design.** Business relationship names
("a customer places orders"), semantic aliases (`sales_rep_id` → employee), and
domain grouping are absent from the deterministic output. They are exactly what
the LLM adds, and keeping them out prevents the engine from inventing
unfalsifiable content.

**5. The graph fits in a prompt.** The reference schema — 19 tables, 21
relationships — serializes to roughly 25-30 KB, comparable to `profile.json`
at 26 KB. `summary` and `dependency_order` alone form a compact schema
overview for cases where the full graph would not fit.

**6. Low-confidence findings become questions, not assertions.** The 0.60
threshold keeps noise out of the artifact; the `MEDIUM` and `LOW` bands mark
what remains as candidates for human or AI adjudication rather than facts.

---

## 10. Integration Points

Five files touched. **Every change is additive** — no existing signature,
model field, artifact key, or test is modified.

| # | File | Change | Risk |
|---|---|---|---|
| 1 | `migration/relationship/models.py` | **New** | None |
| 2 | `migration/relationship/rules.py` | **New** | None |
| 3 | `migration/relationship/graph.py` | **New** | None |
| 4 | `migration/relationship/engine.py` | **New** | None |
| 5 | `migration/output/writer.py` | **Add** `write_relationships()` | None — new method, sibling of `write_profile`. Will import its model properly rather than repeating **TD-04**. |
| 6 | `migration/models/config.py` | **Add** `ArtifactsConfig.relationships: bool = True` | None — see below |
| 7 | `migration/orchestrator/orchestrator.py` | **Add** one gated block after profiling + one banner line | Low — mirrors `orchestrator.py:89-105` |
| 8 | `tests/test_relationship*.py` | **New** | None |

### Backward compatibility of the config change

`ArtifactsConfig` fields are additive-with-default. `test_config_loader.py:36-43`
uses a config that omits `profile:` entirely and validates successfully —
proving new toggles do not break existing config files. Adding `relationships`
breaks **zero** existing configs and **zero** of the 28 passing tests. The
committed `config.yaml` needs no edit; the toggle defaults to `true`.

### Orchestrator integration sketch (structure only, not final code)

```
relationships_file = None
if getattr(self.config.artifacts, "relationships", True):
    engine  = RelationshipEngine(metadata.metadata, profile.profile if profile else None)
    graph   = engine.discover()
    relationships_file = writer.write_relationships(graph, run_directory)
```

Guarded with `getattr(..., default)` exactly as the profile toggle is
(`orchestrator.py:89`), so an older `AppConfig` object cannot break the run.

### Contracts explicitly **not** touched

- `BaseConnector` — frozen, per approved Option A
- `PostgresConnector` — no new methods, no new SQL, no new queries
- `canonical/models.py` — read-only consumer
- `profiler/models.py` — read-only consumer
- `metadata/builder.py` — untouched
- `profiler/engine.py` — untouched
- `metadata.json` / `profile.json` — byte-identical output

---

## 11. Unit Test Strategy

**No database. No connector. No `FakeConnector`.** Module 3 consumes in-memory
Pydantic models, so tests construct `DatabaseMetadata` / `DatabaseProfile`
directly. This is *simpler* than Module 2's test setup, which needed a fake
connector (`test_profiler.py:20-34`) because the profiler talks to one. Module 3
does not.

### Files

| File | Covers |
|---|---|
| `tests/test_relationship_engine.py` | End-to-end discovery, explicit extraction, composite grouping, orchestration |
| `tests/test_relationship_inference.py` | Naming rules, type gates, scoring, thresholds, hard rejects |
| `tests/test_relationship_cardinality.py` | C1-C8, junction detection, self-reference |
| `tests/test_relationship_graph.py` | Topological sort, cycles, orphans, determinism — domain-free fixtures |

### Shared fixtures

A `conftest.py`-style builder producing a miniature schema
(`country → state → city → customer`, plus a junction and a self-reference)
that exercises every rule in under 10 tables. Kept independent of the `bronze`
sample so the tests do not depend on one database's contents.

### Planned cases (~28, matching the existing suite's density)

**Explicit extraction**
1. Single-column declared FK → one relationship, `DECLARED`, confidence `1.0`
2. Composite FK across two rows sharing a constraint name → **one** relationship with two ordered column pairs
3. Duplicated FK rows (the TD-07 cartesian shape) → de-duplicated, not multiplied
4. Table with no FKs → no relationships, no crash
5. Declared FK suppresses an identical naming candidate

**Naming inference**
6. N1 exact PK-name match fires
7. N2 plural/singular resolves (`order_id` → `orders`)
8. N3 no-separator variant fires at a lower base score
9. Type-class mismatch (`text` → `integer` PK) rejected before scoring
10. Target that is not a single-column PK rejected
11. Target with `table_type == 'VIEW'` rejected (**TD-10**)
12. Degenerate self-match (`customer.customer_id` → `customer`) rejected

**Profile scoring**
13. Inclusion violation (`distinct_count` child > parent) → **hard reject**
14. Inclusion holding raises confidence
15. Numeric range containment is compared **numerically, not lexicographically** — the `max_value "9"` vs `"10"` case from the reference data (**TD-09**)
16. Unparseable extremes → range signal skipped, no crash, no false rejection
17. Candidate below `0.60` dropped entirely
18. Candidate at exactly `0.60` accepted (boundary)
19. `profile=None` → engine still returns the full declared graph
20. Empty table (`row_count == 0`) does not raise or divide by zero

**Cardinality**
21. C1 full-PK FK → `ONE_TO_ONE` / `IDENTIFYING`
22. C4 partial-PK FK → `MANY_TO_ONE` / `IDENTIFYING`
23. C3 self-reference → `SELF_REFERENCING`, `is_self_referencing = True`
24. C6 suppressed below `MIN_ROWS_FOR_OBSERVED_CARDINALITY` (the 10-row trap)
25. Nullable FK column → `is_optional = True`

**Junctions**
26. All-FK composite PK → junction; pure vs payload-carrying distinguished
27. `order_item` shape (PK partly non-FK) → **not** a junction

**Graph**
28. Linear chain → correct depths and parent-first order
29. Self-loop **excluded** from `cycles`
30. True 2-table cycle detected, and every table still present in `dependency_order`
31. Orphan table detected
32. Two runs over identical input → identical serialized output (determinism)

### Non-negotiable

All 28 existing tests must still pass unchanged. Module 3 adds tests; it
modifies none.

---

## 12. Example `relationships.json`

Derived from the real reference run (`output/20260804_131232/`, schema `bronze`,
19 tables, 21 declared foreign keys). Relationship list abridged to
representative entries; counts and `dependency_order` are complete and computed
from the actual metadata.

```json
{
  "relationships": {
    "database_name": "datamodel",
    "nodes": [
      { "schema_name": "bronze", "table_name": "audit_log", "table_type": "BASE TABLE",
        "is_orphan": true,  "inbound_relationship_count": 0, "outbound_relationship_count": 0, "depth": 0 },
      { "schema_name": "bronze", "table_name": "country", "table_type": "BASE TABLE",
        "is_orphan": false, "inbound_relationship_count": 1, "outbound_relationship_count": 0, "depth": 0 },
      { "schema_name": "bronze", "table_name": "orders", "table_type": "BASE TABLE",
        "is_orphan": false, "inbound_relationship_count": 4, "outbound_relationship_count": 2, "depth": 4 }
    ],

    "relationships": [
      {
        "id": "bronze.city(state_id)->bronze.state(state_id)",
        "constraint_name": "city_state_id_fkey",
        "source_schema": "bronze", "source_table": "city",  "source_columns": ["state_id"],
        "target_schema": "bronze", "target_table": "state", "target_columns": ["state_id"],
        "relationship_type": "NON_IDENTIFYING",
        "cardinality": "MANY_TO_ONE",
        "cardinality_source": "STRUCTURAL",
        "discovery_method": "DECLARED",
        "confidence": 1.0,
        "confidence_band": "CERTAIN",
        "is_self_referencing": false,
        "is_optional": true,
        "is_identifying": false,
        "evidence": ["declared foreign key constraint 'city_state_id_fkey'"]
      },
      {
        "id": "bronze.employee(manager_id)->bronze.employee(employee_id)",
        "constraint_name": "employee_manager_id_fkey",
        "source_schema": "bronze", "source_table": "employee", "source_columns": ["manager_id"],
        "target_schema": "bronze", "target_table": "employee", "target_columns": ["employee_id"],
        "relationship_type": "SELF_REFERENCING",
        "cardinality": "MANY_TO_ONE",
        "cardinality_source": "STRUCTURAL",
        "discovery_method": "DECLARED",
        "confidence": 1.0,
        "confidence_band": "CERTAIN",
        "is_self_referencing": true,
        "is_optional": true,
        "is_identifying": false,
        "evidence": ["declared foreign key constraint 'employee_manager_id_fkey'",
                     "source and target table are identical - hierarchy"]
      },
      {
        "id": "bronze.order_item(order_id)->bronze.orders(order_id)",
        "constraint_name": "order_item_order_id_fkey",
        "source_schema": "bronze", "source_table": "order_item", "source_columns": ["order_id"],
        "target_schema": "bronze", "target_table": "orders",     "target_columns": ["order_id"],
        "relationship_type": "IDENTIFYING",
        "cardinality": "MANY_TO_ONE",
        "cardinality_source": "STRUCTURAL",
        "discovery_method": "DECLARED",
        "confidence": 1.0,
        "confidence_band": "CERTAIN",
        "is_self_referencing": false,
        "is_optional": false,
        "is_identifying": true,
        "evidence": ["declared foreign key constraint 'order_item_order_id_fkey'",
                     "source columns are a proper subset of primary key (order_id, line_number)"]
      },
      {
        "id": "bronze.product(*)<->bronze.promotion(*)",
        "constraint_name": null,
        "source_schema": "bronze", "source_table": "product",   "source_columns": ["product_id"],
        "target_schema": "bronze", "target_table": "promotion", "target_columns": ["promotion_id"],
        "relationship_type": "MANY_TO_MANY_LOGICAL",
        "cardinality": "MANY_TO_MANY",
        "cardinality_source": "STRUCTURAL",
        "discovery_method": "DERIVED_JUNCTION",
        "confidence": 1.0,
        "confidence_band": "CERTAIN",
        "is_self_referencing": false,
        "is_optional": false,
        "is_identifying": false,
        "evidence": ["derived from junction table 'bronze.product_promotion'",
                     "junction primary key (product_id, promotion_id) is composed entirely of foreign keys"]
      }
    ],

    "junction_tables": [
      { "schema_name": "bronze", "table_name": "product_promotion",
        "connected_tables": ["bronze.product", "bronze.promotion"],
        "key_columns": ["product_id", "promotion_id"],
        "payload_columns": [], "is_pure": true },
      { "schema_name": "bronze", "table_name": "inventory",
        "connected_tables": ["bronze.product", "bronze.warehouse"],
        "key_columns": ["warehouse_id", "product_id"],
        "payload_columns": ["quantity", "reorder_level"], "is_pure": false }
    ],

    "dependency_order": [
      "bronze.audit_log", "bronze.category", "bronze.country", "bronze.department",
      "bronze.promotion", "bronze.supplier",
      "bronze.employee", "bronze.product", "bronze.state",
      "bronze.city", "bronze.product_promotion",
      "bronze.customer", "bronze.warehouse",
      "bronze.inventory", "bronze.orders",
      "bronze.order_item", "bronze.payment", "bronze.return_order", "bronze.shipment"
    ],

    "cycles": [],
    "orphan_tables": ["bronze.audit_log"],

    "summary": {
      "total_relationships": 23,
      "declared_count": 21,
      "inferred_count": 0,
      "derived_count": 2,
      "junction_table_count": 2,
      "self_referencing_count": 1,
      "orphan_table_count": 1,
      "cycle_count": 0,
      "max_dependency_depth": 5,
      "tables_analyzed": 19,
      "columns_analyzed": 84
    }
  }
}
```

### Reading the numbers

- **`inferred_count: 0` is the correct result here.** Every relationship in
  `bronze` is declared, and the only table with unlinked columns is `audit_log`
  (`table_name`, `operation`, `user_name` — text, no `_id` suffix). No naming
  rule fires, so nothing is invented. An engine that produced inferred
  relationships on this schema would be producing false positives.
- **`dependency_order` is fully computed** from the real 21 FKs: six
  independent tables at depth 0, through `orders` at depth 4, to the four
  leaf tables at depth 5.
- **`orders` has 4 inbound edges** (`order_item`, `payment`, `return_order`,
  `shipment`) and 2 outbound (`customer`, `employee`) — the hub of the schema.
- **`cycles` is empty** even though `employee` self-references, per the
  self-loop exclusion rule in §7.

### Illustrative inferred entry

Not present in the reference run — shown only to fix the shape of an inferred
relationship. This is what the engine would emit if `audit_log` carried an
unconstrained `customer_id` column:

```json
{
  "id": "bronze.audit_log(customer_id)->bronze.customer(customer_id)",
  "constraint_name": null,
  "source_schema": "bronze", "source_table": "audit_log", "source_columns": ["customer_id"],
  "target_schema": "bronze", "target_table": "customer",  "target_columns": ["customer_id"],
  "relationship_type": "NON_IDENTIFYING",
  "cardinality": "MANY_TO_ONE",
  "cardinality_source": "STRUCTURAL",
  "discovery_method": "INFERRED_PROFILE",
  "confidence": 0.95,
  "confidence_band": "HIGH",
  "is_self_referencing": false,
  "is_optional": true,
  "is_identifying": false,
  "evidence": [
    "naming rule N1: column name matches single-column primary key of 'bronze.customer' (+0.70)",
    "target column is a single-column primary key (+0.15)",
    "exact data type match: integer (+0.10)",
    "distinct value inclusion holds: 8 <= 10 (+0.10)",
    "numeric range containment holds: [1, 8] within [1, 10] (+0.10)",
    "no declared foreign key constraint exists for this column"
  ]
}
```

Note the final evidence line: the artifact states plainly that this edge is
**not** enforced by the database. A reviewer or an LLM reading it is never
misled into treating an inference as a constraint.

---

## Open questions for review

1. **`MIN_INFERENCE_CONFIDENCE = 0.60`** — accept, or start stricter (`0.70`)
   for the first release and relax once real schemas are observed?
2. **`MIN_ROWS_FOR_OBSERVED_CARDINALITY = 100`** — reasonable floor for
   trusting observed 1:1?
3. **Cross-schema relationships.** `ForeignKeyMetadata` carries
   `referenced_schema`, so declared cross-schema FKs are handled. Should
   *naming inference* also be allowed to cross schema boundaries, or stay
   within a schema? Recommendation: **within-schema only** for inference — a
   `customer_id` in `bronze` matching a `customer` in `silver` is far more
   likely to be coincidence than a relationship.
4. **Should `relationships.json` be written when zero relationships are found?**
   Recommendation: **yes** — an artifact stating "no relationships" is a
   result; a missing file is ambiguous.
