"""
End-to-end integration test for `migrate.py --execute-plan`.

Unlike test_migrate_cli.py (which mocks build_migration_plan/run_schemas to
test dispatch logic in isolation), this exercises the real
SchemaDependencyAnalyzer and the real MigrationOrchestrator pipeline
together, through migrate.run(), with only the connector faked at the
factory boundary. No database, no LLM API key, no Databricks connection.
"""

from __future__ import annotations

from pathlib import Path

import migrate
from migration.orchestrator import orchestrator as orchestrator_module
from migration.orchestrator import plan as plan_module
from tests.conceptual_fixtures import StubLLMClient
from tests.test_orchestrator_end_to_end import LLM_RESPONSE, FakeConnector, _config


def test_execute_plan_runs_the_real_pipeline_using_real_dependency_order(
    tmp_path: Path, monkeypatch
):
    """No mocking of build_migration_plan or run_schemas: the plan is
    computed from FakeConnector's real FK metadata (orders -> customer,
    both in schema 'app'), and the orchestrator actually runs."""
    connector = FakeConnector()
    monkeypatch.setattr(plan_module, "create_connector", lambda source: connector)
    monkeypatch.setattr(orchestrator_module, "create_connector", lambda source: connector)
    monkeypatch.setattr(
        migrate, "_build_llm_client", lambda cfg: StubLLMClient(LLM_RESPONSE, model="claude-opus-5")
    )

    config = _config(tmp_path)

    def fake_load_config(path):
        return config

    monkeypatch.setattr(migrate, "load_config", fake_load_config)

    exit_code = migrate.run(["--config", "c.yaml", "--execute-plan"])

    assert exit_code == 0
    # The real pipeline ran and wrote its own output subdirectory for schema "app".
    app_dir = tmp_path / "app"
    assert app_dir.is_dir()
    run_dirs = [p for p in app_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "metadata.json").exists()
    assert (run_dirs[0] / "estimation.json").exists()
