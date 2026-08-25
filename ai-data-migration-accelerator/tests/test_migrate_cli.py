"""
Focused tests for migrate.py's CLI dispatch logic.

No real database, no real LLM call, no real Databricks connection: every
boundary (config loading, plan building, schema running, DDL execution) is
monkeypatched. These tests exercise argument parsing and mode dispatch only.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import migrate
from migration.orchestrator.schema_runner import SchemaRunResult
from migration.utils.config_loader import ConfigError


def _fake_config(tmp_path: Path, schemas=("bronze", "silver")):
    return SimpleNamespace(
        project=SimpleNamespace(name="test"),
        source=SimpleNamespace(schema_=list(schemas)),
        target=SimpleNamespace(type="databricks"),
        llm=SimpleNamespace(provider="anthropic", model="claude-opus-5"),
        artifacts=SimpleNamespace(conceptual_model=True),
        logging=SimpleNamespace(level=SimpleNamespace(value="INFO")),
    )


class TestArgParsing:
    def test_schema_flag_is_repeatable(self):
        args = migrate.parse_args(["--config", "c.yaml", "--schema", "bronze", "--schema", "silver"])
        assert args.schemas == ["bronze", "silver"]

    def test_schema_flag_defaults_to_none(self):
        args = migrate.parse_args(["--config", "c.yaml"])
        assert args.schemas is None

    def test_plan_flag_defaults_to_false(self):
        args = migrate.parse_args(["--config", "c.yaml"])
        assert args.plan is False

    def test_force_flag_defaults_to_false(self):
        args = migrate.parse_args(["--config", "c.yaml"])
        assert args.force is False

    def test_execute_ddl_and_live_flags(self):
        args = migrate.parse_args(["--config", "c.yaml", "--execute-ddl", "out/ddl.json", "--live"])
        assert args.execute_ddl == "out/ddl.json"
        assert args.live is True

    def test_execute_plan_flag_defaults_to_false(self):
        args = migrate.parse_args(["--config", "c.yaml"])
        assert args.execute_plan is False

    def test_execute_plan_flag_can_be_set(self):
        args = migrate.parse_args(["--config", "c.yaml", "--execute-plan"])
        assert args.execute_plan is True


class TestConfigErrorHandling:
    def test_invalid_config_returns_1_without_calling_any_orchestration(self, monkeypatch):
        def boom(path):
            raise ConfigError("bad yaml")

        monkeypatch.setattr(migrate, "load_config", boom)
        called = {"plan": False, "schemas": False}
        monkeypatch.setattr(migrate, "build_migration_plan", lambda *a, **k: called.__setitem__("plan", True))
        monkeypatch.setattr(migrate, "run_schemas", lambda *a, **k: called.__setitem__("schemas", True))

        exit_code = migrate.run(["--config", "missing.yaml"])

        assert exit_code == 1
        assert called == {"plan": False, "schemas": False}


class TestPlanModeDispatch:
    def test_plan_flag_calls_build_migration_plan_not_run_schemas(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)

        fake_plan = SimpleNamespace(
            has_cycles=False,
            recommended_schema_order=["bronze", "silver"],
            recommended_table_order=["bronze.customer"],
            schema_cycles=[],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=["bronze has no dependencies"],
        )
        plan_calls = []
        monkeypatch.setattr(
            migrate,
            "build_migration_plan",
            lambda cfg, schemas=None: (plan_calls.append(schemas), fake_plan)[1],
        )
        schema_run_called = []
        monkeypatch.setattr(migrate, "run_schemas", lambda *a, **k: schema_run_called.append(True))

        exit_code = migrate.run(["--config", "c.yaml", "--plan"])

        assert exit_code == 0
        assert plan_calls == [None]
        assert schema_run_called == []

    def test_plan_with_cycles_returns_nonzero_exit_code(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)

        fake_plan = SimpleNamespace(
            has_cycles=True,
            recommended_schema_order=[],
            recommended_table_order=[],
            schema_cycles=[SimpleNamespace(tables=["a", "b", "a"])],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=[],
        )
        monkeypatch.setattr(migrate, "build_migration_plan", lambda cfg, schemas=None: fake_plan)

        exit_code = migrate.run(["--config", "c.yaml", "--plan"])

        assert exit_code == 1

    def test_plan_passes_selected_schemas_through(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)

        fake_plan = SimpleNamespace(
            has_cycles=False,
            recommended_schema_order=["bronze"],
            recommended_table_order=[],
            schema_cycles=[],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=[],
        )
        captured = {}

        def fake_build_plan(cfg, schemas=None):
            captured["schemas"] = schemas
            return fake_plan

        monkeypatch.setattr(migrate, "build_migration_plan", fake_build_plan)

        migrate.run(["--config", "c.yaml", "--plan", "--schema", "bronze"])

        assert captured["schemas"] == ["bronze"]


class TestMigrationModeDispatch:
    def test_default_run_uses_all_configured_schemas(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path, schemas=("bronze", "silver"))
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)

        captured = {}

        def fake_run_schemas(cfg, llm, schemas, force):
            captured["schemas"] = schemas
            captured["force"] = force
            return [
                SchemaRunResult("bronze", "completed", run_directory=tmp_path / "bronze" / "run1"),
                SchemaRunResult("silver", "completed", run_directory=tmp_path / "silver" / "run1"),
            ]

        monkeypatch.setattr(migrate, "run_schemas", fake_run_schemas)

        exit_code = migrate.run(["--config", "c.yaml"])

        assert exit_code == 0
        assert captured["schemas"] == ["bronze", "silver"]
        assert captured["force"] is False

    def test_schema_flag_restricts_which_schemas_run(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path, schemas=("bronze", "silver"))
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)

        captured = {}

        def fake_run_schemas(cfg, llm, schemas, force):
            captured["schemas"] = schemas
            return [SchemaRunResult("bronze", "completed", run_directory=tmp_path / "bronze")]

        monkeypatch.setattr(migrate, "run_schemas", fake_run_schemas)

        migrate.run(["--config", "c.yaml", "--schema", "bronze"])

        assert captured["schemas"] == ["bronze"]

    def test_force_flag_is_forwarded(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)

        captured = {}

        def fake_run_schemas(cfg, llm, schemas, force):
            captured["force"] = force
            return []

        monkeypatch.setattr(migrate, "run_schemas", fake_run_schemas)

        migrate.run(["--config", "c.yaml", "--force"])

        assert captured["force"] is True

    def test_any_failed_schema_returns_nonzero_exit_code(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)
        monkeypatch.setattr(
            migrate,
            "run_schemas",
            lambda cfg, llm, schemas, force: [
                SchemaRunResult("bronze", "completed", run_directory=tmp_path),
                SchemaRunResult("silver", "failed", error="boom"),
            ],
        )

        exit_code = migrate.run(["--config", "c.yaml"])

        assert exit_code == 1

    def test_all_completed_or_skipped_returns_zero_exit_code(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)
        monkeypatch.setattr(
            migrate,
            "run_schemas",
            lambda cfg, llm, schemas, force: [
                SchemaRunResult("bronze", "completed", run_directory=tmp_path),
                SchemaRunResult("silver", "skipped", run_directory=tmp_path),
            ],
        )

        exit_code = migrate.run(["--config", "c.yaml"])

        assert exit_code == 0


class TestExecuteDdlModeDispatch:
    def test_missing_ddl_file_returns_1(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)

        exit_code = migrate.run(
            ["--config", "c.yaml", "--execute-ddl", str(tmp_path / "does_not_exist.json")]
        )

        assert exit_code == 1

    def test_dry_run_is_the_default_for_execute_ddl(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)

        ddl_path = tmp_path / "ddl.json"
        ddl_path.write_text(
            '{"ddl_script": {"database_name": "db", "target_type": "databricks", '
            '"table_creation_statements": [{"statement": "CREATE TABLE t (id BIGINT)"}]}}'
        )

        captured = {}

        class FakeExecutor:
            def __init__(self, target):
                pass

            def run(self, script, dry_run):
                captured["dry_run"] = dry_run
                return SimpleNamespace(
                    dry_run=dry_run,
                    statement_count=1,
                    failed_count=0,
                    succeeded=True,
                    first_error=None,
                    results=[
                        SimpleNamespace(
                            statement=SimpleNamespace(statement_type="CREATE", statement="CREATE TABLE t (id BIGINT)")
                        )
                    ],
                )

        monkeypatch.setattr(migrate, "DatabricksExecutor", FakeExecutor)

        exit_code = migrate.run(["--config", "c.yaml", "--execute-ddl", str(ddl_path)])

        assert exit_code == 0
        assert captured["dry_run"] is True

    def test_live_flag_disables_dry_run(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)

        ddl_path = tmp_path / "ddl.json"
        ddl_path.write_text(
            '{"ddl_script": {"database_name": "db", "target_type": "databricks", '
            '"table_creation_statements": [{"statement": "CREATE TABLE t (id BIGINT)"}]}}'
        )

        captured = {}

        class FakeExecutor:
            def __init__(self, target):
                pass

            def run(self, script, dry_run):
                captured["dry_run"] = dry_run
                return SimpleNamespace(
                    dry_run=dry_run, statement_count=1, failed_count=0,
                    succeeded=True, first_error=None, results=[],
                )

        monkeypatch.setattr(migrate, "DatabricksExecutor", FakeExecutor)

        migrate.run(["--config", "c.yaml", "--execute-ddl", str(ddl_path), "--live"])

        assert captured["dry_run"] is False


class TestExecutePlanModeDispatch:
    """--execute-plan must use the deterministic plan's schema order, refuse
    on cycles, and never fall through to --plan's (read-only) or the
    default migration mode's own schema ordering."""

    def test_execute_plan_runs_schemas_in_recommended_order(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path, schemas=("bronze", "silver"))
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)

        fake_plan = SimpleNamespace(
            has_cycles=False,
            recommended_schema_order=["bronze", "silver"],
            recommended_table_order=[],
            schema_cycles=[],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=[],
        )
        monkeypatch.setattr(migrate, "build_migration_plan", lambda cfg, schemas=None: fake_plan)

        captured = {}

        def fake_run_schemas(cfg, llm, schemas, force):
            captured["schemas"] = schemas
            return [
                SchemaRunResult("bronze", "completed", run_directory=tmp_path / "bronze"),
                SchemaRunResult("silver", "completed", run_directory=tmp_path / "silver"),
            ]

        monkeypatch.setattr(migrate, "run_schemas", fake_run_schemas)

        exit_code = migrate.run(["--config", "c.yaml", "--execute-plan"])

        assert exit_code == 0
        assert captured["schemas"] == ["bronze", "silver"]

    def test_execute_plan_uses_plan_order_even_if_it_differs_from_config_order(
        self, tmp_path, monkeypatch
    ):
        """Proves execution order comes from the dependency analyzer, not
        from config.source.schema or --schema argument order."""
        config = _fake_config(tmp_path, schemas=("silver", "bronze"))  # config lists silver first
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)

        fake_plan = SimpleNamespace(
            has_cycles=False,
            recommended_schema_order=["bronze", "silver"],  # analyzer says bronze first
            recommended_table_order=[],
            schema_cycles=[],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=[],
        )
        monkeypatch.setattr(migrate, "build_migration_plan", lambda cfg, schemas=None: fake_plan)

        captured = {}

        def fake_run_schemas(cfg, llm, schemas, force):
            captured["schemas"] = schemas
            return []

        monkeypatch.setattr(migrate, "run_schemas", fake_run_schemas)

        migrate.run(["--config", "c.yaml", "--execute-plan"])

        assert captured["schemas"] == ["bronze", "silver"]

    def test_execute_plan_refuses_to_run_on_circular_dependency(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)

        fake_plan = SimpleNamespace(
            has_cycles=True,
            recommended_schema_order=[],
            recommended_table_order=[],
            schema_cycles=[SimpleNamespace(tables=["bronze", "silver", "bronze"])],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=[],
        )
        monkeypatch.setattr(migrate, "build_migration_plan", lambda cfg, schemas=None: fake_plan)

        run_schemas_called = []
        monkeypatch.setattr(migrate, "run_schemas", lambda *a, **k: run_schemas_called.append(True))

        exit_code = migrate.run(["--config", "c.yaml", "--execute-plan"])

        assert exit_code == 1
        assert run_schemas_called == []  # never guessed an order and executed

    def test_execute_plan_forwards_force_flag(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)

        fake_plan = SimpleNamespace(
            has_cycles=False,
            recommended_schema_order=["bronze"],
            recommended_table_order=[],
            schema_cycles=[],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=[],
        )
        monkeypatch.setattr(migrate, "build_migration_plan", lambda cfg, schemas=None: fake_plan)

        captured = {}

        def fake_run_schemas(cfg, llm, schemas, force):
            captured["force"] = force
            return []

        monkeypatch.setattr(migrate, "run_schemas", fake_run_schemas)

        migrate.run(["--config", "c.yaml", "--execute-plan", "--force"])

        assert captured["force"] is True

    def test_execute_plan_any_failed_schema_returns_nonzero(self, tmp_path, monkeypatch):
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)
        monkeypatch.setattr(migrate, "_build_llm_client", lambda cfg: None)

        fake_plan = SimpleNamespace(
            has_cycles=False,
            recommended_schema_order=["bronze"],
            recommended_table_order=[],
            schema_cycles=[],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=[],
        )
        monkeypatch.setattr(migrate, "build_migration_plan", lambda cfg, schemas=None: fake_plan)
        monkeypatch.setattr(
            migrate,
            "run_schemas",
            lambda cfg, llm, schemas, force: [SchemaRunResult("bronze", "failed", error="boom")],
        )

        exit_code = migrate.run(["--config", "c.yaml", "--execute-plan"])

        assert exit_code == 1

    def test_plan_flag_takes_precedence_over_execute_plan_and_stays_read_only(
        self, tmp_path, monkeypatch
    ):
        """--plan must remain read-only even if --execute-plan is also
        passed (--plan wins so a typo'd combination can never execute)."""
        config = _fake_config(tmp_path)
        monkeypatch.setattr(migrate, "load_config", lambda path: config)

        fake_plan = SimpleNamespace(
            has_cycles=False,
            recommended_schema_order=["bronze"],
            recommended_table_order=[],
            schema_cycles=[],
            table_cycles=[],
            cross_schema_foreign_keys=[],
            explanation=[],
        )
        monkeypatch.setattr(migrate, "build_migration_plan", lambda cfg, schemas=None: fake_plan)

        run_schemas_called = []
        monkeypatch.setattr(migrate, "run_schemas", lambda *a, **k: run_schemas_called.append(True))

        migrate.run(["--config", "c.yaml", "--plan", "--execute-plan"])

        assert run_schemas_called == []
