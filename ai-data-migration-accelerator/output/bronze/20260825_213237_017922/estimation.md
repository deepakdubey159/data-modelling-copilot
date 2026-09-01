# Migration Effort Estimation

## Executive Summary

**Complexity Level:** VERY_HIGH
**Total Effort:** 42.7 person-days (8.5 weeks, 1.9 months)
**Confidence:** MEDIUM

**Source:** postgres
**Target:** databricks

## Effort Breakdown

| Component | Effort (Days) |
|-----------|---------------|
| Analysis & Discovery | 8.8 |
| Modeling & Design | 7.7 |
| Development & Conversion | 12.8 |
| Testing & Validation | 8.4 |
| Deployment & Cutover | 5.0 |

| **Total** | **42.7** |

## Complexity Factors

| Factor | Value |
|--------|-------|
| Tables | 20 |
| Columns | 78 |
| Primary Keys | 20 |
| Foreign Keys | 23 |
| Complex Relationships | 1 |
| Unique Constraints | 2 |
| Check Constraints | 3 |
| Large Tables | 9 |
| Datatype Conversions | 0 |

## Effort Component Details

### Analysis & Discovery

Schema profiling, relationship discovery: 8.8 person-days; calendar duration: ~11.0 days with 1 person(s).

**Estimated Effort:** 8.8 person-days

### Modeling & Design

Logical & physical model design: 7.7 person-days; calendar duration: ~9.6 days with 1 person(s).

**Estimated Effort:** 7.7 person-days

### Development & Conversion

DDL generation, transformation logic, type mapping: 12.8 person-days; calendar duration: ~16.0 days with 1 person(s).

**Estimated Effort:** 12.8 person-days

### Testing & Validation

Functional, data, integration testing: 8.4 person-days; calendar duration: ~10.5 days with 1 person(s).

**Estimated Effort:** 8.4 person-days

### Deployment & Cutover

Migration execution, cutover, validation: 5.0 person-days; calendar duration: ~6.2 days with 1 person(s).

**Estimated Effort:** 5.0 person-days

## Assumptions

- Schema contains 20 tables with 78 total columns.
- Found 23 foreign key relationships.
- 9 tables classified as large (>1M rows).
- Team size: 1 person(s) at 8.0 hours/day.
- Productivity factor: 80% (overhead accounted for).
- Assumes standard complexity migration with historical project data.

## Identified Risks

- Large tables (9) may require partitioning strategy.
- Complex relationships (1) may need custom logic.
- High complexity may increase discovery and testing effort.
- Single-person team may have coordination bottlenecks.

## Recommendations

- Use partitioning/parallelization for large tables.
- Consider referential integrity validation automation.
- Consider adding 1-2 team members to reduce calendar duration from 1 → 3.

---

**Note:** This estimation is based on schema complexity analysis. Actual effort
may vary based on data quality, business logic complexity, and team experience.