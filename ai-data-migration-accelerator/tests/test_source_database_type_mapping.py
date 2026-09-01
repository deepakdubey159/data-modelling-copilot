"""Tests for source database type mapping (DB2, PostgreSQL -> Databricks).

Source type name, length, precision and scale are always structured fields
on PhysicalColumn (`source_database_type`, `source_length`,
`source_precision`, `source_scale`) - never a single combined string like
"DECIMAL(18,2)". A DB2/PostgreSQL catalog reports the base type name and its
size as separate columns, and the pipeline preserves them the same way from
canonical metadata through to here.
"""

import pytest

from migration.physical.models import PhysicalColumn, PhysicalDataType
from migration.physical.source_types import classify_source_type
from migration.target.databricks import DatabricksTargetAdapter
from migration.physical.models import PhysicalModel, PhysicalModelPackage, PhysicalTable
from migration.target.models import TargetCapability


class TestSourceDatabaseTypeMapping:
    """Tests for direct source database type mapping to Databricks."""

    @pytest.fixture
    def databricks_adapter(self):
        """Create a Databricks adapter for testing."""
        package = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test",
                tables=[],
            )
        )
        adapter = DatabricksTargetAdapter(package)
        adapter._build_type_mappings()  # Initialize type mappings
        return adapter

    # -- DB2 integer types ---------------------------------------------------

    def test_db2_smallint_maps_to_int(self, databricks_adapter):
        """DB2 SMALLINT -> Databricks INT."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="age",
            data_type=PhysicalDataType.INTEGER,
            source_database_type="SMALLINT",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "INT"
        assert length is None
        assert precision is None
        assert scale is None

    def test_db2_integer_maps_to_int(self, databricks_adapter):
        """DB2 INTEGER -> Databricks INT."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="count",
            data_type=PhysicalDataType.INTEGER,
            source_database_type="INTEGER",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "INT"

    def test_db2_bigint_maps_to_bigint(self, databricks_adapter):
        """DB2 BIGINT -> Databricks BIGINT."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="id",
            data_type=PhysicalDataType.INTEGER,
            source_database_type="BIGINT",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "BIGINT"

    # -- DB2 character types --------------------------------------------------

    def test_db2_varchar_maps_to_string(self, databricks_adapter):
        """DB2 VARCHAR(255) -> Databricks STRING (no length)."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="name",
            data_type=PhysicalDataType.STRING,
            length=255,
            source_database_type="VARCHAR",
            source_length=255,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"
        assert length is None  # Databricks STRING has no length

    def test_db2_char_maps_to_string(self, databricks_adapter):
        """DB2 CHAR(10) -> Databricks STRING."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="code",
            data_type=PhysicalDataType.STRING,
            length=10,
            source_database_type="CHAR",
            source_length=10,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"
        assert length is None

    def test_db2_long_varchar_maps_to_string(self, databricks_adapter):
        """DB2 LONG VARCHAR -> Databricks STRING."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="notes",
            data_type=PhysicalDataType.STRING,
            source_database_type="LONG VARCHAR",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"

    def test_db2_graphic_maps_to_string(self, databricks_adapter):
        """DB2 GRAPHIC (fixed-width DBCS) -> Databricks STRING."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="kanji_code",
            data_type=PhysicalDataType.STRING,
            source_database_type="GRAPHIC",
            source_length=10,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"
        assert length is None

    def test_db2_vargraphic_maps_to_string(self, databricks_adapter):
        """DB2 VARGRAPHIC (variable-width DBCS) -> Databricks STRING."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="kanji_name",
            data_type=PhysicalDataType.STRING,
            source_database_type="VARGRAPHIC",
            source_length=40,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"

    def test_db2_clob_maps_to_string(self, databricks_adapter):
        """DB2 CLOB -> Databricks STRING."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="description",
            data_type=PhysicalDataType.STRING,
            source_database_type="CLOB",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"

    def test_db2_dbclob_maps_to_string(self, databricks_adapter):
        """DB2 DBCLOB -> Databricks STRING."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="notes_dbcs",
            data_type=PhysicalDataType.STRING,
            source_database_type="DBCLOB",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"

    def test_db2_blob_maps_to_binary(self, databricks_adapter):
        """DB2 BLOB -> Databricks BINARY."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="image",
            data_type=PhysicalDataType.BINARY,
            source_database_type="BLOB",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "BINARY"

    # -- DB2 decimal precision/scale -------------------------------------------

    def test_db2_decimal_preserves_precision_scale(self, databricks_adapter):
        """DB2 DECIMAL(18,2) -> Databricks DECIMAL(18,2), read from the
        source's structured precision/scale fields, not a parsed string."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="amount",
            data_type=PhysicalDataType.DECIMAL,
            precision=18,
            scale=2,
            source_database_type="DECIMAL",
            source_precision=18,
            source_scale=2,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "DECIMAL"
        assert precision == 18
        assert scale == 2

    def test_db2_decimal_with_different_precision_scale(self, databricks_adapter):
        """A second DECIMAL precision/scale pair is preserved distinctly -
        proves the value comes from the source, not a hardcoded default."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="rate",
            data_type=PhysicalDataType.DECIMAL,
            source_database_type="DECIMAL",
            source_precision=9,
            source_scale=4,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "DECIMAL"
        assert precision == 9
        assert scale == 4

    def test_db2_numeric_maps_to_decimal(self, databricks_adapter):
        """DB2 NUMERIC(18,2) -> Databricks DECIMAL(18,2)."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="price",
            data_type=PhysicalDataType.DECIMAL,
            source_database_type="NUMERIC",
            source_precision=18,
            source_scale=2,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "DECIMAL"
        assert precision == 18
        assert scale == 2

    # -- DB2 temporal types -----------------------------------------------------

    def test_db2_date_maps_to_date(self, databricks_adapter):
        """DB2 DATE -> Databricks DATE."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="birth_date",
            data_type=PhysicalDataType.DATE,
            source_database_type="DATE",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "DATE"

    def test_db2_time_falls_back_to_string_with_warning(self):
        """DB2 TIME has no native Databricks equivalent: documented fallback
        to STRING, with an explicit warning - never silently dropped."""
        classification = classify_source_type("TIME")
        assert classification.data_type == PhysicalDataType.STRING
        assert classification.is_explicit is True
        assert classification.warning is not None
        assert "TIME" in classification.warning

    def test_db2_timestamp_maps_to_timestamp(self, databricks_adapter):
        """DB2 TIMESTAMP -> Databricks TIMESTAMP."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="created_at",
            data_type=PhysicalDataType.TIMESTAMP,
            source_database_type="TIMESTAMP",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "TIMESTAMP"

    # -- DB2 floating point -------------------------------------------------

    def test_db2_real_maps_to_float(self, databricks_adapter):
        """DB2 REAL (single precision) -> Databricks FLOAT."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="measurement",
            data_type=PhysicalDataType.DECIMAL,
            source_database_type="REAL",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "FLOAT"

    def test_db2_double_maps_to_double(self, databricks_adapter):
        """DB2 DOUBLE -> Databricks DOUBLE."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="reading",
            data_type=PhysicalDataType.DECIMAL,
            source_database_type="DOUBLE",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "DOUBLE"

    # -- PostgreSQL types -----------------------------------------------------

    def test_postgresql_text_maps_to_string(self, databricks_adapter):
        """PostgreSQL TEXT -> Databricks STRING."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="description",
            data_type=PhysicalDataType.STRING,
            source_database_type="TEXT",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"

    def test_postgresql_character_varying_maps_to_string(self, databricks_adapter):
        """PostgreSQL 'character varying' -> Databricks STRING."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="name",
            data_type=PhysicalDataType.STRING,
            source_database_type="character varying",
            source_length=100,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "STRING"
        assert length is None

    def test_postgresql_numeric_maps_to_decimal(self, databricks_adapter):
        """PostgreSQL NUMERIC(18,2) -> Databricks DECIMAL(18,2)."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="amount",
            data_type=PhysicalDataType.DECIMAL,
            source_database_type="numeric",
            source_precision=18,
            source_scale=2,
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "DECIMAL"
        assert precision == 18
        assert scale == 2

    def test_postgresql_boolean_maps_to_boolean(self, databricks_adapter):
        """PostgreSQL BOOLEAN -> Databricks BOOLEAN."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="is_active",
            data_type=PhysicalDataType.BOOLEAN,
            source_database_type="boolean",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "BOOLEAN"

    def test_postgresql_date_maps_to_date(self, databricks_adapter):
        """PostgreSQL DATE -> Databricks DATE."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="order_date",
            data_type=PhysicalDataType.DATE,
            source_database_type="date",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "DATE"

    def test_postgresql_timestamp_without_time_zone_maps_to_timestamp(self, databricks_adapter):
        """PostgreSQL 'timestamp without time zone' -> Databricks TIMESTAMP."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="created_at",
            data_type=PhysicalDataType.TIMESTAMP,
            source_database_type="timestamp without time zone",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "TIMESTAMP"

    def test_postgresql_bytea_maps_to_binary(self, databricks_adapter):
        """PostgreSQL BYTEA -> Databricks BINARY."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="data",
            data_type=PhysicalDataType.BINARY,
            source_database_type="bytea",
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        assert target_type == "BINARY"

    # -- Fallback behavior -----------------------------------------------------

    def test_no_source_type_falls_back_to_generic_mapping(self, databricks_adapter):
        """When source type unavailable, fall back to generic physical type mapping."""
        adapter = databricks_adapter
        col = PhysicalColumn(
            name="code",
            data_type=PhysicalDataType.STRING,
            length=30,
            # No source_database_type set
        )
        target_type, length, precision, scale = adapter._map_data_type(col)
        # Should use generic mapping (STRING with length)
        assert target_type == "STRING"
        # Length is preserved from generic mapping
        assert length == 30

    def test_unrecognized_source_type_falls_back_to_string_with_warning(self):
        """An unsupported source type gets a documented STRING fallback and
        an explicit warning - never a silent, undocumented type change."""
        classification = classify_source_type("MAINFRAME_PACKED_DECIMAL")
        assert classification.data_type == PhysicalDataType.STRING
        assert classification.is_explicit is False
        assert classification.warning is not None
        assert "MAINFRAME_PACKED_DECIMAL" in classification.warning

    def test_ddl_contains_no_string_with_length(self):
        """Verify generated Databricks DDL contains no STRING(n), VARCHAR(n), or CHAR(n)."""
        from migration.ddl.databricks_generator import DatabricksDDLGenerator
        from migration.target.models import (
            TargetModelPackage,
            TargetModel,
            TargetTable,
            TargetColumn,
            TargetIdentifierRule,
        )

        target_col = TargetColumn(
            name="name",
            target_type="STRING",
            length=None,  # Important: no length
            precision=None,
            scale=None,
            nullable=True,
            source_column="name",
            physical_type="STRING",
        )

        target_table = TargetTable(
            name="customers",
            source_table="customers",
            logical_entity="Customer",
            columns=[target_col],
        )

        identifier_rule = TargetIdentifierRule(
            max_length=255,
            allow_unicode=True,
            reserved_words=[],
            quote_char="`",
            supports_case_sensitivity=True,
        )

        target_model = TargetModel(
            database_name="test",
            summary="Test",
            target_type="databricks",
            capabilities=[TargetCapability.PRIMARY_KEYS],
            identifier_rules=identifier_rule,
            data_type_mappings=[],
            tables=[target_table],
        )

        target_pkg = TargetModelPackage(
            target_model=target_model,
            generated_from="test",
            generated_by="test",
        )

        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()
        script = ddl.ddl_script.to_sql()

        # Verify no invalid Databricks types appear
        assert "STRING(" not in script
        assert "VARCHAR(" not in script
        assert "CHAR(" not in script
        assert "`name` STRING" in script  # Should be STRING without length
