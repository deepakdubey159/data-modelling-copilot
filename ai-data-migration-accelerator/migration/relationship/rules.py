"""
Relationship Discovery Rules

Every tunable used by the relationship engine lives here: naming rules, type
compatibility classes, scoring weights and thresholds. They are separated
from `engine.py` because they are the parts most likely to be adjusted after
seeing real-world schemas, and a reviewer should be able to read all of them
in one place without reading orchestration logic.

Precedent: `migration/profiler/engine.py` already hoists `_PATTERNS`,
`_MIN_PATTERN_RATIO` and `_TEXT_TYPES` to module level for the same reason.
This module is that instinct given its own file, because relationship
discovery has considerably more knobs.

Nothing here is source-specific. Type classification is keyword-based over
common SQL type names so it works for any connector without the engine ever
knowing which system produced the metadata.
"""

from __future__ import annotations

import re

from migration.relationship.models import ConfidenceBand

# ---------------------------------------------------------
# Thresholds
# ---------------------------------------------------------

BASE_TABLE_TYPE = "BASE TABLE"
"""Only tables of this type participate in inference. Views are excluded:
they carry no keys of their own and inferring into them produces noise."""

MIN_INFERENCE_CONFIDENCE = 0.60
"""Candidates scoring below this are dropped entirely rather than reported
weakly. Same stance as the profiler's `_MIN_PATTERN_RATIO` — silence beats
noise, because a low-confidence relationship shown to a human (or an AI) tends
to get rationalized into a real one."""

MIN_ROWS_FOR_OBSERVED_CARDINALITY = 100
"""Below this row count, observed uniqueness is not treated as evidence of a
one-to-one relationship. Ten rows with ten distinct values proves nothing."""


# ---------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------

BASE_SCORE_EXACT_PK_NAME = 0.70
BASE_SCORE_ENTITY_ID_SUFFIX = 0.65
BASE_SCORE_ENTITY_ID_NO_SEPARATOR = 0.55

BONUS_TARGET_IS_SINGLE_COLUMN_PK = 0.15
BONUS_EXACT_TYPE_MATCH = 0.10
BONUS_DISTINCT_INCLUSION = 0.10
BONUS_RANGE_CONTAINMENT = 0.10
BONUS_PATTERN_AGREEMENT = 0.05

PENALTY_RANGE_VIOLATION = -0.35
PENALTY_NO_DATA = -0.10


# ---------------------------------------------------------
# Confidence bands
# ---------------------------------------------------------


def confidence_band(score: float) -> ConfidenceBand:
    """Bucket a raw confidence score. Consumers should branch on the band
    rather than reimplementing these thresholds."""
    if score >= 1.0:
        return ConfidenceBand.CERTAIN
    if score >= 0.85:
        return ConfidenceBand.HIGH
    if score >= 0.70:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


# ---------------------------------------------------------
# Type compatibility
# ---------------------------------------------------------

# Ordered: the first class whose keyword appears in the type name wins.
# Order matters — "interval" contains "int", so TEMPORAL must be tested
# before INTEGER.
_TYPE_CLASS_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("UUID", ("uuid", "uniqueidentifier", "guid")),
    ("BOOLEAN", ("bool",)),
    ("JSON", ("json", "xml", "variant", "struct", "map", "array", "jsonb")),
    ("TEMPORAL", ("timestamp", "datetime", "date", "time", "interval", "year")),
    ("NUMERIC", ("numeric", "decimal", "number", "float", "double", "real", "money")),
    ("INTEGER", ("int", "serial", "byteint")),
    ("TEXT", ("char", "text", "string", "clob", "nchar", "nvarchar")),
    ("BINARY", ("binary", "blob", "bytea", "raw", "image")),
)

UNKNOWN_TYPE_CLASS = "OTHER"

NUMERIC_CLASSES = frozenset({"INTEGER", "NUMERIC"})
"""Classes whose values can be parsed as numbers. Used to decide whether a
min/max range comparison is meaningful."""

# Pairs of distinct classes that may still legitimately reference each other.
_CROSS_CLASS_COMPATIBLE = frozenset({frozenset({"INTEGER", "NUMERIC"})})


def type_class(data_type: str) -> str:
    """Map a vendor type name onto a coarse compatibility class.

    Deliberately coarse. The goal is only to reject nonsense pairings (a text
    column cannot reference an integer key), not to model any vendor's type
    system faithfully.
    """
    if not data_type:
        return UNKNOWN_TYPE_CLASS

    lowered = data_type.strip().lower()
    for class_name, keywords in _TYPE_CLASS_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return class_name
    return UNKNOWN_TYPE_CLASS


def types_compatible(source_type: str, target_type: str) -> bool:
    """True when two columns could plausibly hold the same values."""
    source_class = type_class(source_type)
    target_class = type_class(target_type)

    if source_class == UNKNOWN_TYPE_CLASS or target_class == UNKNOWN_TYPE_CLASS:
        # Unrecognized types are not evidence against a relationship, so they
        # are allowed through rather than silently discarded.
        return True
    if source_class == target_class:
        return True
    return frozenset({source_class, target_class}) in _CROSS_CLASS_COMPATIBLE


def is_numeric_type(data_type: str) -> bool:
    return type_class(data_type) in NUMERIC_CLASSES


# ---------------------------------------------------------
# Identifier normalization
# ---------------------------------------------------------

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def normalize_identifier(name: str) -> str:
    """Lower-case and collapse separators, so `CustomerID`, `CUSTOMER_ID` and
    `customer id` all compare equal."""
    if not name:
        return ""
    return _NON_ALPHANUMERIC.sub("_", name.strip().lower()).strip("_")


def name_variants(word: str) -> set[str]:
    """Singular/plural variants of an entity name.

    Needed because the column is `order_id` while the table is `orders`.
    A human reads through that instantly; the rule has to be explicit.
    """
    if not word:
        return set()

    variants = {word}
    if word.endswith("ies") and len(word) > 3:
        variants.add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 2:
        variants.add(word[:-2])
    if word.endswith("s") and len(word) > 1:
        variants.add(word[:-1])
    if word.endswith("y") and len(word) > 1:
        variants.add(word[:-1] + "ies")
    variants.add(word + "s")
    variants.add(word + "es")
    return variants


def entity_candidates(column_name: str) -> list[tuple[str, str, float]]:
    """Derive candidate entity names from a column name.

    Returns a list of ``(entity_name, rule_id, base_score)``. Rule N1 (the
    column name *is* another table's primary key name) is not handled here —
    it needs the primary-key index and is resolved in the engine.
    """
    normalized = normalize_identifier(column_name)
    if not normalized:
        return []

    if normalized.endswith("_id") and len(normalized) > 3:
        return [(normalized[:-3], "N2", BASE_SCORE_ENTITY_ID_SUFFIX)]

    if normalized.endswith("id") and len(normalized) > 2:
        return [(normalized[:-2].strip("_"), "N3", BASE_SCORE_ENTITY_ID_NO_SEPARATOR)]

    return []


def qualified_name(schema_name: str, table_name: str) -> str:
    return f"{schema_name}.{table_name}"


def relationship_id(
    source_schema: str,
    source_table: str,
    source_columns: list[str],
    target_schema: str,
    target_table: str,
    target_columns: list[str],
    separator: str = "->",
) -> str:
    """Deterministic identity for a relationship. Stable across runs."""
    source = f"{source_schema}.{source_table}({', '.join(source_columns)})"
    target = f"{target_schema}.{target_table}({', '.join(target_columns)})"
    return f"{source}{separator}{target}"
