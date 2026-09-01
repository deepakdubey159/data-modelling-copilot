"""Tests for the deterministic Databricks DDL validator.

Each test constructs a minimal DDLScript containing exactly the invalid
pattern under test, so a failure points at one specific rule rather than
requiring a full pipeline run.
"""

from __future__ import annotations

import pytest

from migration.ddl.models import DDLScript, DDLStatement
from migration.ddl.validator import DDLValidationError, validate_ddl_script


def _script(**statement_lists) -> DDLScript:
    return DDLScript(database_name="test", target_type="databricks", **statement_lists)


class TestForbiddenSyntax:
    @pytest.mark.parametrize(
        "bad_sql",
        [
            "CREATE TABLE `t` (`c` STRING) COLLATE utf8;",
            "CREATE TABLE `t` (`c` STRING) TABLESPACE ts1;",
            "ALTER TABLE `t` OWNER TO admin;",
            "CREATE INDEX `idx` ON `t` USING btree (`c`);",
            "SELECT * FROM `t` WHERE id = 1::regclass;",
            "CREATE SEQUENCE `seq1`;",
            "CREATE TABLE `t` (`c` STRING) IN TABLESPACE ts1;",
            "CREATE TABLE `t` (`c` STRING) BUFFERPOOL bp1;",
            "CREATE INDEX `idx` ON `t`(`c`);",
            "CREATE UNIQUE INDEX `idx` ON `t`(`c`);",
            "CREATE TABLE `t` (`c` STRING) CLUSTERED BY (`c`);",
        ],
    )
    def test_rejects_forbidden_syntax_in_executable_statement(self, bad_sql):
        script = _script(table_creation_statements=[DDLStatement(statement=bad_sql)])
        with pytest.raises(DDLValidationError):
            validate_ddl_script(script)

    def test_allows_forbidden_terms_inside_a_comment(self):
        """A recommendation comment may explain, in prose, that Databricks
        lacks CREATE INDEX - that must not itself fail validation."""
        script = _script(
            index_statements=[
                DDLStatement(
                    statement="-- Index recommendation: Delta Lake has no CREATE INDEX",
                    statement_type="COMMENT",
                )
            ]
        )
        validate_ddl_script(script)  # Should not raise.


class TestStatementBoundaries:
    def test_rejects_missing_semicolon(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(statement="CREATE TABLE `t` (`c` STRING)")
            ]
        )
        with pytest.raises(DDLValidationError):
            validate_ddl_script(script)

    def test_comment_statements_do_not_require_semicolon(self):
        script = _script(
            index_statements=[
                DDLStatement(statement="-- just a note", statement_type="COMMENT")
            ]
        )
        validate_ddl_script(script)


class TestEmptyIdentifiers:
    def test_rejects_empty_backtick_identifier(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(statement="CREATE TABLE `` (`c` STRING);")
            ]
        )
        with pytest.raises(DDLValidationError):
            validate_ddl_script(script)


class TestDuplicateConstraintNames:
    def test_rejects_duplicate_constraint_name_across_statements(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement=(
                        "CREATE TABLE IF NOT EXISTS `a` (\n"
                        "  `id` BIGINT NOT NULL,\n"
                        "  CONSTRAINT `pk_shared` PRIMARY KEY (`id`)\n"
                        ");"
                    )
                )
            ],
            constraint_statements=[
                DDLStatement(
                    statement=(
                        "ALTER TABLE `b` ADD CONSTRAINT `pk_shared` "
                        "FOREIGN KEY (`a_id`) REFERENCES `a`(`id`);"
                    ),
                    statement_type="ALTER",
                )
            ],
        )
        with pytest.raises(DDLValidationError):
            validate_ddl_script(script)

    def test_allows_the_same_constraint_named_once(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement=(
                        "CREATE TABLE IF NOT EXISTS `a` (\n"
                        "  `id` BIGINT NOT NULL,\n"
                        "  CONSTRAINT `pk_a` PRIMARY KEY (`id`)\n"
                        ");"
                    )
                )
            ]
        )
        validate_ddl_script(script)


class TestQualifiedNames:
    def test_rejects_more_than_three_segments(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement="CREATE TABLE IF NOT EXISTS `a`.`b`.`c`.`d` (`id` BIGINT);"
                )
            ]
        )
        with pytest.raises(DDLValidationError):
            validate_ddl_script(script)

    def test_allows_up_to_three_segments(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement="CREATE TABLE IF NOT EXISTS `cat`.`sch`.`tbl` (`id` BIGINT);"
                )
            ]
        )
        validate_ddl_script(script)


class TestColumnTypes:
    def test_rejects_unsupported_type(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement=(
                        "CREATE TABLE IF NOT EXISTS `t` (\n"
                        "  `c` VARCHAR2\n"
                        ");"
                    )
                )
            ]
        )
        with pytest.raises(DDLValidationError):
            validate_ddl_script(script)

    def test_allows_valid_databricks_types(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement=(
                        "CREATE TABLE IF NOT EXISTS `t` (\n"
                        "  `a` STRING,\n"
                        "  `b` BIGINT NOT NULL,\n"
                        "  `c` DECIMAL(10,2),\n"
                        "  `d` DATE,\n"
                        "  `e` TIMESTAMP,\n"
                        "  `f` BOOLEAN,\n"
                        "  `g` BINARY\n"
                        ");"
                    )
                )
            ]
        )
        validate_ddl_script(script)


class TestClusteringGate:
    def test_rejects_partitioned_by_when_clustering_disabled(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement=(
                        "CREATE TABLE IF NOT EXISTS `t` (`c` DATE)\n"
                        "PARTITIONED BY (`c`)\n;"
                    )
                )
            ]
        )
        with pytest.raises(DDLValidationError):
            validate_ddl_script(script, enable_clustering=False)

    def test_allows_partitioned_by_when_clustering_enabled(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement=(
                        "CREATE TABLE IF NOT EXISTS `t` (`c` DATE)\n"
                        "PARTITIONED BY (`c`)\n;"
                    )
                )
            ]
        )
        validate_ddl_script(script, enable_clustering=True)


class TestValidScriptPasses:
    def test_a_well_formed_script_passes_every_check(self):
        script = _script(
            table_creation_statements=[
                DDLStatement(
                    statement=(
                        "CREATE TABLE IF NOT EXISTS `cat`.`sch`.`customers` (\n"
                        "  `customer_id` BIGINT NOT NULL,\n"
                        "  `name` STRING NOT NULL,\n"
                        "  CONSTRAINT `pk_customers` PRIMARY KEY (`customer_id`)\n"
                        ");"
                    )
                )
            ],
            constraint_statements=[
                DDLStatement(
                    statement=(
                        "ALTER TABLE `cat`.`sch`.`orders` ADD CONSTRAINT `fk_orders_customers` "
                        "FOREIGN KEY (`customer_id`) REFERENCES `cat`.`sch`.`customers`(`customer_id`);"
                    ),
                    statement_type="ALTER",
                )
            ],
            index_statements=[
                DDLStatement(
                    statement="-- Index recommendation: no CREATE INDEX in Delta Lake",
                    statement_type="COMMENT",
                )
            ],
        )
        validate_ddl_script(script)  # Should not raise.
