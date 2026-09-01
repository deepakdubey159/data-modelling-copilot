"""
Tests for migration.orchestrator.plan.build_migration_plan (--plan mode).

No database: the connector is faked at the factory boundary, same pattern
as the orchestrator end-to-end tests.
"""

from __future__ import annotations

from pathlib import Path

from migration.orchestrator import plan as plan_module
from migration.orchestrator.plan import build_migration_plan
from tests.test_orchestrator_end_to_end import FakeConnector, _config


def test_plan_connects_extracts_and_disconnects(tmp_path: Path, monkeypatch):
    connector = FakeConnector()
    monkeypatch.setattr(plan_module, "create_connector", lambda source: connector)

    build_migration_plan(_config(tmp_path))

    assert connector.connected is True
    assert connector.disconnected is True


def test_plan_reflects_the_configured_schema_fks(tmp_path: Path, monkeypatch):
    connector = FakeConnector()
    monkeypatch.setattr(plan_module, "create_connector", lambda source: connector)

    plan = build_migration_plan(_config(tmp_path))

    # FakeConnector's fixed FK data: orders -> customer within schema "app".
    assert "app.customer" in plan.root_tables
    assert plan.recommended_table_order.index("app.customer") < plan.recommended_table_order.index("app.orders")


def test_plan_disconnects_even_when_analysis_fails(tmp_path: Path, monkeypatch):
    connector = FakeConnector()
    monkeypatch.setattr(plan_module, "create_connector", lambda source: connector)

    def boom(schemas):
        raise RuntimeError("extraction failed")

    connector.extract_tables = boom

    try:
        build_migration_plan(_config(tmp_path))
    except RuntimeError:
        pass

    assert connector.disconnected is True
