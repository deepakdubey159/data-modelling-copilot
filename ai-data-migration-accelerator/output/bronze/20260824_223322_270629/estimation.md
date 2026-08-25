# Migration Effort Estimation

## Executive Summary

**Complexity Level:** VERY_HIGH
**Total Effort:** 45.2 person-days (9.0 weeks, 2.1 months)
**Confidence:** MEDIUM

**Source:** postgres
**Target:** databricks

## Effort Breakdown

| Component | Effort (Days) |
|-----------|---------------|
| Analysis & Discovery | 11.0 |
| Modeling & Design | 9.7 |
| Development & Conversion | 13.5 |
| Testing & Validation | 9.3 |
| Deployment & Cutover | 5.0 |

| **Total** | **45.2** |

## Complexity Factors

| Factor | Value |
|--------|-------|
| Tables | 20 |
| Columns | 76 |
| Primary Keys | 20 |
| Foreign Keys | 23 |
| Complex Relationships | 1 |
| Unique Constraints | 3 |
| Check Constraints | 2 |
| Large Tables | 7 |
| Datatype Conversions | 0 |

## Effort Component Details

### Analysis & Discovery

Schema profiling, relationship discovery. 8.8 person-days, ~11.0 calendar days.

**Estimated Effort:** 11.0 person-days

### Modeling & Design

Logical & physical model design. 7.8 person-days, ~9.7 calendar days.

**Estimated Effort:** 9.7 person-days

### Development & Conversion

DDL generation, transformation logic, type mapping. 10.8 person-days, ~13.5 calendar days.

**Estimated Effort:** 13.5 person-days

### Testing & Validation

Functional, data, integration testing. 7.4 person-days, ~9.3 calendar days.

**Estimated Effort:** 9.3 person-days

### Deployment & Cutover

Migration execution, cutover, validation. 4.0 person-days, ~5.0 calendar days.

**Estimated Effort:** 5.0 person-days

## Assumptions

- Schema contains 20 tables with 76 total columns.
- Found 23 foreign key relationships.
- 7 tables classified as large (>1M rows).
- Team size: 1 person(s) at 8.0 hours/day.
- Productivity factor: 80% (overhead accounted for).
- Assumes standard complexity migration with historical project data.

## Identified Risks

- Large tables (7) may require partitioning strategy.
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