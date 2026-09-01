# DB2 → Databricks Migration Guide

## Overview

The DB2 to Databricks migration uses the **existing multi-source architecture** without introducing DB2-specific silos. This ensures consistency, maintainability, and reuse of profiling, relationship discovery, and modeling engines across all source platforms.

## Architecture: No Silos, Existing Patterns

### Migration Pipeline

```
DB2 SYSCAT Catalog
  |
  v
DB2Connector (extract: CHAR, VARCHAR, BIGINT, DECIMAL, TIMESTAMP, etc.)
  |
  v
MetadataBuilder (canonical keys: table_schema, table_name, column_name)
  |
  v
Profiler (statistics - platform-agnostic)
  |
  v
RelationshipEngine (foreign key analysis - platform-agnostic)
  |
  v
ConceptualModelEngine (business entities)
  |
  v
LogicalModelEngine (generic types: STRING, INTEGER, DECIMAL)
  |
  v
PhysicalModelEngine (physical design)
  |
  v
DatabricksTargetAdapter (map to: STRING, BIGINT, DECIMAL)
  |
  v
DatabricksDDLGenerator (CREATE TABLE)
  |
  v
Databricks Data Lake
```

**Key:** MetadataBuilder through PhysicalModelEngine are **DB2-agnostic**. DB2-specific work only at ingress (DB2Connector) and egress (DatabricksTargetAdapter).

## DB2 Type Mappings

### String/Text Types
- CHAR(n) → STRING (fixed-length treated as variable)
- VARCHAR(n) → STRING (direct)
- CLOB → STRING (unbounded)
- GRAPHIC(n) → STRING (double-byte to UTF-8)
- VARGRAPHIC(n) → STRING (variable graphic)

### Binary Types
- BLOB → BINARY (direct; no size limit)

### Integer Types
- SMALLINT → BIGINT (widened for consistency)
- INTEGER → BIGINT (widened for consistency)
- BIGINT → BIGINT (direct)

### Decimal/Numeric Types
- DECIMAL(p,s) → DECIMAL(p,s) (direct; max DECIMAL(38,18))
- DECFLOAT(16) → FLOAT (half-precision)
- DECFLOAT(34) → DOUBLE (decimal to binary encoding)

### Date/Time Types
- DATE → DATE (direct)
- TIME → STRING (deprecated; store as VARCHAR)
- TIMESTAMP → TIMESTAMP (direct; microsecond precision)

### Structured Types
- XML → STRING (serialized; native queries unavailable)

## Supported DB2 Metadata

- Tables and views (SYSCAT.TABLES)
- Columns with full type info (SYSCAT.COLUMNS)
- Primary keys (SYSCAT.TABCONST)
- Foreign keys (SYSCAT.REFERENCES)
- Constraints (unique, check)
- Indexes (SYSCAT.INDEXES)
- Statistics (row counts, page counts)

## Unsupported Features

| Feature | DB2 | Databricks | Impact |
|---------|---|---|---|
| XML queries | Yes (XPath) | No | Deserialize in application |
| GRAPHIC | Yes (double-byte) | No | UTF-8 string |
| DECFLOAT | Yes (decimal IEEE 754) | Partial (binary) | Rounding possible |
| TIME | Yes | Deprecated | STRING fallback |
| Triggers | Yes | Limited | Manual refactoring |

## Testing

Integration tests in `tests/test_db2_databricks_integration.py`:

- Simple e-commerce schema with mixed types
- Financial schema with decimal precision
- Conversion report generation
- Parametrized tests for all 15 DB2 types

**All tests verify native DB2 metadata preserved through canonical models.**

```bash
pytest tests/test_db2_databricks_integration.py -v   # 18 tests
pytest tests/test_db2_connector.py -v                # 30 tests
pytest tests/test_db2_metadata_validation.py -v      # 48 tests
```

## No Breaking Changes to PostgreSQL

DB2 integration follows same abstract patterns as PostgreSQL connector. All engines source-agnostic. PostgreSQL tests continue to pass unchanged.

## Conclusion

DB2 → Databricks leverages **existing architecture**:
- Ingress: DB2 types → Canonical metadata
- Processing: All engines work with generic types
- Egress: Generic types → Databricks types

Enables rapid support for additional sources by writing only a source connector.

