"""Classify a raw source database type name into a generic PhysicalDataType.

This is the target-agnostic half of type preservation: it decides *what kind
of data* a source column holds (a generic storage class, plus its exact
length/precision/scale) from the source's own declared type - never from the
column's name, and never from any target platform's syntax. Turning that
generic class into a specific vendor type string (`STRING`, `VARCHAR2(255)`,
...) is each target adapter's job, not this module's.

Deliberately conservative: an unrecognized source type does not raise and
does not guess a narrow type - it falls back to STRING (the type that can
hold everything without loss) and reports that fallback explicitly, so the
caller can warn rather than silently misrepresent the data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from migration.physical.models import PhysicalDataType

# Source type names this classifier resolves explicitly, keyed by the base
# type name (no length/precision - those come from the column's own
# character_length/numeric_precision/numeric_scale fields, never parsed out
# of a combined string). Covers DB2 (LUW and mainframe/z-OS via SYSCAT,
# COLTYPE values) and PostgreSQL (information_schema.columns.data_type
# values) without regressing either.
_EXPLICIT_TYPES: dict[str, PhysicalDataType] = {
    # -- DB2: character ---------------------------------------------------
    "CHARACTER": PhysicalDataType.STRING,
    "CHAR": PhysicalDataType.STRING,
    "VARCHAR": PhysicalDataType.STRING,
    "LONG VARCHAR": PhysicalDataType.STRING,
    "GRAPHIC": PhysicalDataType.STRING,
    "VARGRAPHIC": PhysicalDataType.STRING,
    "LONG VARGRAPHIC": PhysicalDataType.STRING,
    "CLOB": PhysicalDataType.STRING,
    "DBCLOB": PhysicalDataType.STRING,
    # -- DB2: binary -------------------------------------------------------
    "BLOB": PhysicalDataType.BINARY,
    "BINARY": PhysicalDataType.BINARY,
    "VARBINARY": PhysicalDataType.BINARY,
    # -- DB2: numeric ------------------------------------------------------
    "SMALLINT": PhysicalDataType.INTEGER,
    "INTEGER": PhysicalDataType.INTEGER,
    "INT": PhysicalDataType.INTEGER,
    "BIGINT": PhysicalDataType.INTEGER,
    "DECIMAL": PhysicalDataType.DECIMAL,
    "DEC": PhysicalDataType.DECIMAL,
    "NUMERIC": PhysicalDataType.DECIMAL,
    "REAL": PhysicalDataType.DECIMAL,
    "DOUBLE": PhysicalDataType.DECIMAL,
    "FLOAT": PhysicalDataType.DECIMAL,
    "DECFLOAT": PhysicalDataType.DECIMAL,
    # -- DB2: temporal ------------------------------------------------------
    "DATE": PhysicalDataType.DATE,
    "TIME": PhysicalDataType.STRING,
    # Databricks has no native TIME type; documented, explicit fallback.
    "TIMESTAMP": PhysicalDataType.TIMESTAMP,
    # -- DB2: other ----------------------------------------------------------
    "BOOLEAN": PhysicalDataType.BOOLEAN,
    "XML": PhysicalDataType.STRING,
    "ROWID": PhysicalDataType.STRING,
    # -- PostgreSQL: information_schema.columns.data_type values -----------
    "CHARACTER VARYING": PhysicalDataType.STRING,
    "TEXT": PhysicalDataType.STRING,
    "UUID": PhysicalDataType.STRING,
    "CITEXT": PhysicalDataType.STRING,
    "SMALLSERIAL": PhysicalDataType.INTEGER,
    "SERIAL": PhysicalDataType.INTEGER,
    "BIGSERIAL": PhysicalDataType.INTEGER,
    "DOUBLE PRECISION": PhysicalDataType.DECIMAL,
    "MONEY": PhysicalDataType.DECIMAL,
    "TIMESTAMP WITHOUT TIME ZONE": PhysicalDataType.TIMESTAMP,
    "TIMESTAMP WITH TIME ZONE": PhysicalDataType.TIMESTAMP,
    "TIME WITHOUT TIME ZONE": PhysicalDataType.STRING,
    "TIME WITH TIME ZONE": PhysicalDataType.STRING,
    "BYTEA": PhysicalDataType.BINARY,
    "JSON": PhysicalDataType.JSON,
    "JSONB": PhysicalDataType.JSON,
}

# Precision/scale defaults for types the source declares without them
# (DB2 REAL/DOUBLE/FLOAT carry no user-declared precision/scale; Databricks
# DOUBLE is a fixed-width binary float, not a DECIMAL, but the generic
# PhysicalDataType has no separate float class - DECIMAL is the closest
# generic class and each target adapter decides the concrete float type).
_FLOATING_POINT_TYPES = frozenset({"REAL", "DOUBLE", "FLOAT", "DOUBLE PRECISION"})

# Databricks (and every SQL target this accelerator generates for) has no
# native TIME type. Recorded once so callers can build a consistent warning.
UNSUPPORTED_TEMPORAL_TYPES = frozenset({"TIME", "TIME WITHOUT TIME ZONE", "TIME WITH TIME ZONE"})

_NUMERIC_SUFFIX = re.compile(r"\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\)\s*$")


@dataclass(frozen=True)
class SourceTypeClassification:
    data_type: PhysicalDataType
    length: int | None
    precision: int | None
    scale: int | None
    is_explicit: bool
    """False when the type name was not recognized and STRING was used as
    the documented, lossless fallback."""

    warning: str | None = None
    """Set when the caller should record a note - an unrecognized type, or
    a recognized type with no target-native equivalent (e.g. TIME)."""


def classify_source_type(
    source_type: str | None,
    *,
    length: int | None = None,
    precision: int | None = None,
    scale: int | None = None,
) -> SourceTypeClassification:
    """Classify a source column's declared type into a generic storage class.

    `length`/`precision`/`scale` must come from the source's own structured
    metadata fields (e.g. DB2 SYSCAT.COLUMNS.LENGTH/PRECISION/SCALE,
    PostgreSQL information_schema.columns.character_maximum_length /
    numeric_precision / numeric_scale) - never parsed out of a combined
    string like "DECIMAL(18,2)", which the source rarely provides as one
    token and which regressed silently when it was assumed.
    """
    if not source_type:
        return SourceTypeClassification(
            data_type=PhysicalDataType.STRING,
            length=length,
            precision=None,
            scale=None,
            is_explicit=False,
            warning="No source type name was available; used STRING as a lossless fallback.",
        )

    # Defensive: tolerate a combined "TYPE(n)" or "TYPE(p,s)" form even
    # though the structured fields above are the intended source, so a
    # caller that only has a combined string still gets the base type right.
    base = _NUMERIC_SUFFIX.sub("", source_type).strip().upper()
    base = re.sub(r"\s+", " ", base)

    data_type = _EXPLICIT_TYPES.get(base)
    warning = None

    if data_type is None:
        return SourceTypeClassification(
            data_type=PhysicalDataType.STRING,
            length=length,
            precision=None,
            scale=None,
            is_explicit=False,
            warning=(
                f"Source type '{source_type}' is not in the explicit DB2/PostgreSQL "
                f"mapping table; used STRING as a documented, lossless fallback."
            ),
        )

    if base in UNSUPPORTED_TEMPORAL_TYPES:
        warning = (
            f"Source type '{source_type}' has no native target equivalent for TIME-of-day "
            f"values; mapped to STRING to preserve the value without loss."
        )

    if data_type == PhysicalDataType.DECIMAL:
        if base in _FLOATING_POINT_TYPES:
            # Floating-point types carry no user-declared precision/scale.
            return SourceTypeClassification(
                data_type=data_type,
                length=None,
                precision=None,
                scale=None,
                is_explicit=True,
                warning=warning,
            )
        return SourceTypeClassification(
            data_type=data_type,
            length=None,
            precision=precision,
            scale=scale if scale is not None else (0 if precision is not None else None),
            is_explicit=True,
            warning=warning,
        )

    if data_type == PhysicalDataType.STRING and base not in UNSUPPORTED_TEMPORAL_TYPES:
        return SourceTypeClassification(
            data_type=data_type,
            length=length,
            precision=None,
            scale=None,
            is_explicit=True,
            warning=warning,
        )

    return SourceTypeClassification(
        data_type=data_type,
        length=None,
        precision=None,
        scale=None,
        is_explicit=True,
        warning=warning,
    )
