"""DB2 → Databricks type conversion and migration support.

This module provides comprehensive type mapping and conversion analysis
for migrating DB2 schemas to Databricks using the existing architecture.

The conversion flow:
  DB2 catalog → DB2Connector → canonical metadata
    ↓
  MetadataBuilder / Profiler / Relationship/Logical/Physical Engines
    ↓
  PhysicalModel (with generic types)
    ↓
  DatabricksTargetAdapter (maps generic → Databricks)
    ↓
  TargetModel + DatabricksDDLGenerator → Databricks SQL

This module generates a conversion report documenting the mapping at each stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SupportLevel(str, Enum):
    """Indicates how well a DB2 type is supported in Databricks."""

    DIRECT = "DIRECT"  # Direct 1:1 mapping, no data loss
    COMPATIBLE = "COMPATIBLE"  # Maps to compatible type, possible precision loss
    UNSUPPORTED = "UNSUPPORTED"  # Not supported; migration path differs


@dataclass
class DB2Type:
    """Represents a DB2 SYSCAT type with metadata."""

    name: str
    """DB2 type name (e.g., 'VARCHAR', 'DECIMAL')."""

    description: str
    """What this type represents."""

    supports_length: bool = False
    supports_precision: bool = False
    supports_scale: bool = False
    example: str = ""


@dataclass
class TypeConversionRule:
    """Maps a DB2 type through to Databricks."""

    db2_type: str
    """Native DB2 type (e.g., 'DECIMAL(10,2)')."""

    canonical_type: str
    """Canonical metadata type (e.g., 'NUMERIC')."""

    physical_type: str
    """Generic physical model type (e.g., 'DECIMAL')."""

    databricks_type: str
    """Target Databricks type (e.g., 'DECIMAL(10,2)')."""

    support_level: SupportLevel
    """How well supported this conversion is."""

    conversion_rule: str
    """How to convert: preserve, truncate, cast, etc."""

    warning: Optional[str] = None
    """Any caveats or data loss warnings."""

    notes: Optional[str] = None


# Native DB2 type categories, derived from the same DB2_TYPES/CONVERSION_RULES
# registry used for conversion reporting. Reused by effort estimation so that
# both consumers classify DB2 types identically instead of maintaining a
# second definition of what counts as "legacy" or "LOB".
DB2_LEGACY_TYPES = frozenset({"GRAPHIC", "VARGRAPHIC", "DECFLOAT"})
DB2_LOB_TYPES = frozenset({"CLOB", "BLOB"})
DB2_GRAPHIC_TYPES = frozenset({"GRAPHIC", "VARGRAPHIC"})
DB2_NUMERIC_PRECISION_TYPES = frozenset({"DECIMAL", "DECFLOAT"})
DB2_XML_TYPES = frozenset({"XML"})


def classify_db2_native_type(native_type: str) -> dict:
    """Classify a DB2 native type string (e.g. from canonical ColumnMetadata.data_type).

    Returns flags describing which DB2-specific complexity categories the
    type belongs to. Takes the *native* DB2 type name directly — never a
    generic canonical/physical type — so classification is exact rather than
    inferred.
    """
    base_type = native_type.split("(")[0].strip().upper()
    return {
        "is_legacy": base_type in DB2_LEGACY_TYPES,
        "is_lob": base_type in DB2_LOB_TYPES,
        "is_graphic": base_type in DB2_GRAPHIC_TYPES,
        "is_numeric_precision": base_type in DB2_NUMERIC_PRECISION_TYPES,
        "is_xml": base_type in DB2_XML_TYPES,
    }


# DB2 types comprehensive mapping
DB2_TYPES = {
    # Character/String types
    "CHAR": DB2Type(
        name="CHAR",
        description="Fixed-length character string",
        supports_length=True,
        example="CHAR(10)",
    ),
    "VARCHAR": DB2Type(
        name="VARCHAR",
        description="Variable-length character string",
        supports_length=True,
        example="VARCHAR(255)",
    ),
    "CLOB": DB2Type(
        name="CLOB",
        description="Character large object (up to 2GB)",
        supports_length=False,
        example="CLOB",
    ),
    # Graphic/Unicode types
    "GRAPHIC": DB2Type(
        name="GRAPHIC",
        description="Fixed-length graphic string (double-byte)",
        supports_length=True,
        example="GRAPHIC(50)",
    ),
    "VARGRAPHIC": DB2Type(
        name="VARGRAPHIC",
        description="Variable-length graphic string",
        supports_length=True,
        example="VARGRAPHIC(100)",
    ),
    # Binary types
    "BLOB": DB2Type(
        name="BLOB",
        description="Binary large object (up to 2GB)",
        supports_length=False,
        example="BLOB",
    ),
    # Integer types
    "SMALLINT": DB2Type(
        name="SMALLINT",
        description="Small integer (16-bit)",
        example="SMALLINT",
    ),
    "INTEGER": DB2Type(
        name="INTEGER",
        description="Regular integer (32-bit)",
        example="INTEGER",
    ),
    "BIGINT": DB2Type(
        name="BIGINT",
        description="Large integer (64-bit)",
        example="BIGINT",
    ),
    # Decimal/Numeric types
    "DECIMAL": DB2Type(
        name="DECIMAL",
        description="Fixed-point decimal number",
        supports_precision=True,
        supports_scale=True,
        example="DECIMAL(10,2)",
    ),
    "DECFLOAT": DB2Type(
        name="DECFLOAT",
        description="IEEE 754 decimal floating point",
        supports_precision=True,
        example="DECFLOAT(34)",
    ),
    # Date/Time types
    "DATE": DB2Type(
        name="DATE",
        description="Date (YYYY-MM-DD)",
        example="DATE",
    ),
    "TIME": DB2Type(
        name="TIME",
        description="Time of day (HH:MM:SS)",
        example="TIME",
    ),
    "TIMESTAMP": DB2Type(
        name="TIMESTAMP",
        description="Date and time with microsecond precision",
        example="TIMESTAMP",
    ),
    # XML type
    "XML": DB2Type(
        name="XML",
        description="XML document",
        example="XML",
    ),
}

# Conversion rules: how each DB2 type maps to Databricks
CONVERSION_RULES = [
    # String types
    TypeConversionRule(
        db2_type="CHAR(n)",
        canonical_type="TEXT",
        physical_type="STRING",
        databricks_type="STRING",
        support_level=SupportLevel.DIRECT,
        conversion_rule="Map fixed-length CHAR to STRING; trailing spaces preserved in Databricks",
        notes="Databricks doesn't distinguish CHAR vs VARCHAR; migration preserves data but not type semantics",
    ),
    TypeConversionRule(
        db2_type="VARCHAR(n)",
        canonical_type="TEXT",
        physical_type="STRING",
        databricks_type="STRING",
        support_level=SupportLevel.DIRECT,
        conversion_rule="Direct mapping; length constraint is documentation only in Databricks",
    ),
    TypeConversionRule(
        db2_type="CLOB",
        canonical_type="TEXT",
        physical_type="STRING",
        databricks_type="STRING",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map CLOB to STRING; no size limit in Databricks",
        notes="Unbounded CLOBs will load into STRING; performance implications for very large objects",
    ),
    # Graphic types (double-byte character encoding)
    TypeConversionRule(
        db2_type="GRAPHIC(n)",
        canonical_type="TEXT",
        physical_type="STRING",
        databricks_type="STRING",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map to STRING; character encoding preserved by UTF-8",
        warning="Graphic strings use double-byte encoding in DB2; verify UTF-8 compatibility",
    ),
    TypeConversionRule(
        db2_type="VARGRAPHIC(n)",
        canonical_type="TEXT",
        physical_type="STRING",
        databricks_type="STRING",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map to STRING; character encoding preserved by UTF-8",
        warning="Variable graphic strings; double-byte encoding compatibility required",
    ),
    # Binary types
    TypeConversionRule(
        db2_type="BLOB",
        canonical_type="BINARY",
        physical_type="BINARY",
        databricks_type="BINARY",
        support_level=SupportLevel.DIRECT,
        conversion_rule="Direct mapping; Databricks BINARY can hold arbitrarily large objects",
    ),
    # Integer types
    TypeConversionRule(
        db2_type="SMALLINT",
        canonical_type="SMALL_INTEGER",
        physical_type="INTEGER",
        databricks_type="BIGINT",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map SMALLINT to BIGINT; all DB2 integer types use 64-bit in Databricks for consistency",
        warning="SMALLINT values fit in BIGINT; this is a widen operation but safe",
    ),
    TypeConversionRule(
        db2_type="INTEGER",
        canonical_type="INTEGER",
        physical_type="INTEGER",
        databricks_type="BIGINT",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map to BIGINT; Databricks standardizes on 64-bit integers",
    ),
    TypeConversionRule(
        db2_type="BIGINT",
        canonical_type="LONG_INTEGER",
        physical_type="INTEGER",
        databricks_type="BIGINT",
        support_level=SupportLevel.DIRECT,
        conversion_rule="Direct 64-bit mapping",
    ),
    # Decimal/Numeric types
    TypeConversionRule(
        db2_type="DECIMAL(p,s)",
        canonical_type="NUMERIC",
        physical_type="DECIMAL",
        databricks_type="DECIMAL(p,s)",
        support_level=SupportLevel.DIRECT,
        conversion_rule="Direct mapping; Databricks DECIMAL(p,s) identical to DB2",
        notes="Maximum precision in Databricks: DECIMAL(38,18)",
    ),
    TypeConversionRule(
        db2_type="DECFLOAT(16)",
        canonical_type="FLOATING_POINT",
        physical_type="FLOAT",
        databricks_type="FLOAT",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map DECFLOAT(16) to FLOAT (32-bit IEEE 754)",
        warning="DECFLOAT(16) is half-precision; maps to FLOAT; possible precision loss",
    ),
    TypeConversionRule(
        db2_type="DECFLOAT(34)",
        canonical_type="FLOATING_POINT",
        physical_type="DOUBLE",
        databricks_type="DOUBLE",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map DECFLOAT(34) to DOUBLE (64-bit IEEE 754)",
        warning="DECFLOAT(34) uses decimal encoding; DOUBLE uses binary encoding; rounding may occur",
    ),
    # Date/Time types
    TypeConversionRule(
        db2_type="DATE",
        canonical_type="DATE",
        physical_type="DATE",
        databricks_type="DATE",
        support_level=SupportLevel.DIRECT,
        conversion_rule="Direct mapping",
    ),
    TypeConversionRule(
        db2_type="TIME",
        canonical_type="TIME",
        physical_type="TIME",
        databricks_type="STRING",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map to STRING; Databricks TIME is deprecated; store as VARCHAR",
        warning="DB2 TIME type maps to STRING; runtime must parse TIME format",
    ),
    TypeConversionRule(
        db2_type="TIMESTAMP",
        canonical_type="TIMESTAMP",
        physical_type="TIMESTAMP",
        databricks_type="TIMESTAMP",
        support_level=SupportLevel.DIRECT,
        conversion_rule="Direct mapping; microsecond precision compatible",
    ),
    # XML type
    TypeConversionRule(
        db2_type="XML",
        canonical_type="XML",
        physical_type="STRING",
        databricks_type="STRING",
        support_level=SupportLevel.COMPATIBLE,
        conversion_rule="Map XML to STRING; store serialized XML documents",
        warning="DB2 native XML querying not available in Databricks; must deserialize in application",
    ),
]


def generate_conversion_report(source_schema: dict[str, list[tuple[str, str]]]) -> dict:
    """Generate a comprehensive conversion report for a DB2 schema.

    Args:
        source_schema: Dict[table_name] → [(column_name, db2_type), ...]

    Returns:
        A report dictionary with:
        - summary: Overview of what converts well vs. issues
        - type_mappings: List of TypeConversionRule applied
        - unsupported_types: Types that cannot convert
        - recommendations: Migration-specific guidance
        - warnings: Data loss or compatibility issues
    """
    mappings_used = set()
    unsupported = set()
    warnings = []

    for table_name, columns in source_schema.items():
        for col_name, db2_type in columns:
            # Extract base type (e.g., "VARCHAR(255)" → "VARCHAR")
            base_type = db2_type.split("(")[0].upper()

            # Find matching conversion rule
            matching_rules = [r for r in CONVERSION_RULES if r.db2_type.split("(")[0].upper() == base_type]
            if matching_rules:
                for rule in matching_rules:
                    mappings_used.add((rule.db2_type, rule.databricks_type))
                    if rule.warning:
                        warnings.append(f"{table_name}.{col_name}: {rule.warning}")
            else:
                unsupported.add(base_type)

    direct_mappings = [r for r in CONVERSION_RULES if r.support_level == SupportLevel.DIRECT]
    compatible_mappings = [r for r in CONVERSION_RULES if r.support_level == SupportLevel.COMPATIBLE]

    return {
        "summary": f"Converting {len(mappings_used)} type mappings. "
                   f"{len(direct_mappings)} direct, {len(compatible_mappings)} compatible. "
                   f"{len(unsupported)} unsupported types.",
        "type_mappings": CONVERSION_RULES,
        "unsupported_types": list(unsupported),
        "recommendations": [
            "Use DatabricksTargetAdapter to map PhysicalModel generic types to Databricks",
            "Review warnings for GRAPHIC, DECFLOAT, TIME, and XML types",
            "All integer types standardize on BIGINT for consistency",
            "String types normalize to STRING (CHAR/VARCHAR distinctions lost)",
            "Consider ETL logic for XML deserialization in application layer",
            "Test decimal precision (max DECIMAL(38,18) in Databricks)",
        ],
        "warnings": warnings,
    }


def report_as_markdown() -> str:
    """Generate a markdown report of all DB2 → Databricks type conversions."""

    lines = [
        "# DB2 → Databricks Type Conversion Matrix\n",
        "This document defines how each DB2 data type maps through the migration pipeline to Databricks.\n",
        "## Type Conversion Flow\n",
        "```",
        "DB2 Type → Canonical Type → Physical Type → Databricks Type",
        "```\n",
        "## Conversion Rules by Support Level\n",
    ]

    for support_level in [SupportLevel.DIRECT, SupportLevel.COMPATIBLE, SupportLevel.UNSUPPORTED]:
        rules = [r for r in CONVERSION_RULES if r.support_level == support_level]
        if rules:
            lines.append(f"### {support_level.value}\n")
            for rule in rules:
                lines.append(f"- **{rule.db2_type}** → {rule.databricks_type}")
                lines.append(f"  - Canonical: {rule.canonical_type}")
                lines.append(f"  - Physical: {rule.physical_type}")
                lines.append(f"  - Rule: {rule.conversion_rule}")
                if rule.warning:
                    lines.append(f"  - ⚠️ Warning: {rule.warning}")
                if rule.notes:
                    lines.append(f"  - Note: {rule.notes}")
                lines.append("")

    lines.extend([
        "## Unsupported Types\n",
        "No native DB2 types are entirely unsupported; all map to STRING or BINARY as fallback.\n",
        "## Architecture Integration\n",
        "The DB2 → Databricks pipeline uses the existing architecture:\n",
        "1. **DB2Connector**: Extract native metadata (CHAR, VARCHAR, DECIMAL, TIMESTAMP, etc.)\n",
        "2. **MetadataBuilder**: Normalize to canonical schema\n",
        "3. **Profiler**: Gather statistics and data characteristics\n",
        "4. **Engines**: Discover relationships and logical/physical models using generic types\n",
        "5. **DatabricksTargetAdapter**: Map generic types to Databricks\n",
        "6. **DatabricksDDLGenerator**: Generate CREATE TABLE statements\n",
    ])

    return "\n".join(lines)
