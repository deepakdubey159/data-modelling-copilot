"""End-to-end test of the full pipeline through MigrationOrchestrator.

Proves that a single run produces all five artifacts and that the AI step is
wired correctly. No database and no API key: the connector is faked at the
factory boundary and the LLM client is a stub.

This is the test that would catch a broken `migrate.py` run — every other
test exercises one engine in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from migration.models.config import AppConfig
from migration.orchestrator import orchestrator as orchestrator_module
from migration.orchestrator.orchestrator import MigrationOrchestrator
from tests.conceptual_fixtures import StubLLMClient

# A miniature source database, in the native row shape the connector returns.
TABLES = [
    {"table_schema": "app", "table_name": "customer", "table_type": "BASE TABLE"},
    {"table_schema": "app", "table_name": "orders", "table_type": "BASE TABLE"},
]

COLUMNS = [
    {
        "table_schema": "app",
        "table_name": "customer",
        "column_name": "customer_id",
        "data_type": "integer",
        "is_nullable": "NO",
        "column_default": None,
        "ordinal_position": 1,
        "character_maximum_length": None,
        "numeric_precision": 32,
        "numeric_scale": 0,
    },
    {
        "table_schema": "app",
        "table_name": "orders",
        "column_name": "order_id",
        "data_type": "integer",
        "is_nullable": "NO",
        "column_default": None,
        "ordinal_position": 1,
        "character_maximum_length": None,
        "numeric_precision": 32,
        "numeric_scale": 0,
    },
    {
        "table_schema": "app",
        "table_name": "orders",
        "column_name": "customer_id",
        "data_type": "integer",
        "is_nullable": "YES",
        "column_default": None,
        "ordinal_position": 2,
        "character_maximum_length": None,
        "numeric_precision": 32,
        "numeric_scale": 0,
    },
]

PRIMARY_KEYS = [
    {
        "table_schema": "app",
        "table_name": "customer",
        "column_name": "customer_id",
        "constraint_name": "customer_pkey",
        "ordinal_position": 1,
    },
    {
        "table_schema": "app",
        "table_name": "orders",
        "column_name": "order_id",
        "constraint_name": "orders_pkey",
        "ordinal_position": 1,
    },
]

FOREIGN_KEYS = [
    {
        "table_schema": "app",
        "table_name": "orders",
        "column_name": "customer_id",
        "foreign_table_schema": "app",
        "foreign_table_name": "customer",
        "foreign_column_name": "customer_id",
        "constraint_name": "orders_customer_fkey",
    }
]

LLM_RESPONSE = json.dumps(
    {
        "database_name": "shop",
        "summary": "A small retail database covering customers and their orders.",
        "domains": [
            {
                "name": "Sales",
                "description": "Customers and the orders they place.",
                "entities": ["Customer", "Sales Order"],
            }
        ],
        "entities": [
            {
                "name": "Customer",
                "description": "Someone who buys from the business.",
                "business_key": ["Customer Number"],
                "attributes": ["Customer Number"],
                "source_tables": ["app.customer"],
                "relationships": [
                    {
                        "related_entity": "Sales Order",
                        "verb_phrase": "places",
                        "cardinality": "ONE_TO_MANY",
                        "is_optional": True,
                        "description": "A customer may place many orders.",
                    }
                ],
            },
            {
                "name": "Sales Order",
                "description": "A request to buy goods.",
                "business_key": ["Order Number"],
                "attributes": ["Order Number"],
                "source_tables": ["app.orders"],
                "relationships": [],
            },
        ],
        "business_rules": ["An order belongs to at most one customer."],
        "assumptions": ["'orders' was read as customer orders."],
        "recommendations": ["Confirm whether order lines exist elsewhere."],
    }
)


class FakeConnector:
    """Stands in for a real source connector at the factory boundary."""

    def __init__(self):
        self.connected = False
        self.disconnected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.disconnected = True

    def extract_tables(self, schemas):
        return TABLES

    def extract_columns(self, schemas):
        return COLUMNS

    def extract_primary_keys(self, schemas):
        return PRIMARY_KEYS

    def extract_foreign_keys(self, schemas):
        return FOREIGN_KEYS

    def extract_constraints(self, schemas):
        return []

    def extract_indexes(self, schemas):
        return []

    def extract_statistics(self, schemas):
        return []

    def profile_table(self, schema, table, columns):
        return {
            "row_count": 10,
            "duplicate_row_count": 0,
            "columns": {
                column["name"]: {
                    "null_count": 0,
                    "distinct_count": 10,
                    "min_value": "1",
                    "max_value": "10",
                    "min_length": 1,
                    "max_length": 2,
                }
                for column in columns
            },
        }

    def sample_column_values(self, schema, table, column, limit=200):
        return []


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "project": {"name": "e2e", "output_directory": str(tmp_path)},
            "source": {
                "type": "postgres",
                "host": "localhost",
                "port": 5432,
                "database": "shop",
                "username": "postgres",
                "password": "unused",
                "schema": ["app"],
            },
            "target": {"type": "snowflake"},
            "llm": {"provider": "anthropic", "model": "claude-opus-5"},
            "logging": {"level": "INFO"},
        }
    )


@pytest.fixture
def fake_connector(monkeypatch) -> FakeConnector:
    connector = FakeConnector()
    monkeypatch.setattr(
        orchestrator_module, "create_connector", lambda source: connector
    )
    return connector


def _run_directory(tmp_path: Path) -> Path:
    runs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(runs) == 1, f"expected exactly one run directory, found {runs}"
    return runs[0]


# -- The full run ----------------------------------------------------------


def test_full_run_produces_every_artifact(tmp_path: Path, fake_connector):
    client = StubLLMClient(LLM_RESPONSE, model="claude-opus-5")

    MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

    run = _run_directory(tmp_path)
    produced = {p.name for p in run.iterdir()}

    assert produced == {
        "metadata.json",
        "profile.json",
        "relationships.json",
        "conceptual_model.json",
        "conceptual_model.md",
        "conceptual_model.html",
        "logical_model.json",
        "logical_model.md",
        "logical_model.html",
        "summary.txt",
    }


def test_logical_model_is_derived_from_the_conceptual_model(tmp_path: Path, fake_connector):
    """Module 5 runs inside the pipeline, not only as a standalone script."""
    MigrationOrchestrator(
        _config(tmp_path), llm_client=StubLLMClient(LLM_RESPONSE)
    ).run()

    run = _run_directory(tmp_path)
    logical = json.loads((run / "logical_model.json").read_text(encoding="utf-8"))
    model = logical["logical_model"]

    assert logical["generated_from"] == "conceptual_model.json"
    assert {e["name"] for e in model["entities"]} >= {"Customer", "Sales Order"}
    assert model["relationships"]

    html = (run / "logical_model.html").read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "Logical Data Model" in html


def test_logical_model_is_skipped_when_the_conceptual_model_is(
    tmp_path: Path, fake_connector
):
    """Without an LLM client there is no conceptual model, so there is
    nothing to derive a logical model from."""
    MigrationOrchestrator(_config(tmp_path), llm_client=None).run()

    produced = {p.name for p in _run_directory(tmp_path).iterdir()}

    assert "metadata.json" in produced
    assert "logical_model.json" not in produced


def test_logical_toggle_disables_only_the_logical_step(tmp_path: Path, fake_connector):
    config = _config(tmp_path)
    config.artifacts.logical_model = False

    MigrationOrchestrator(config, llm_client=StubLLMClient(LLM_RESPONSE)).run()

    produced = {p.name for p in _run_directory(tmp_path).iterdir()}

    assert "conceptual_model.json" in produced
    assert "logical_model.json" not in produced


def test_conceptual_html_is_produced_and_self_contained(tmp_path: Path, fake_connector):
    MigrationOrchestrator(
        _config(tmp_path), llm_client=StubLLMClient(LLM_RESPONSE)
    ).run()

    html = (_run_directory(tmp_path) / "conceptual_model.html").read_text(
        encoding="utf-8"
    )

    assert html.startswith("<!DOCTYPE html>")
    assert "<svg" in html
    assert "Conceptual Data Model" in html
    assert 'data-id="Customer"' in html
    # No network dependency: the SVG namespace is the only URL on the page.
    assert "cdn" not in html.lower()


def test_conceptual_markdown_is_complete(tmp_path: Path, fake_connector):
    MigrationOrchestrator(
        _config(tmp_path), llm_client=StubLLMClient(LLM_RESPONSE)
    ).run()

    markdown = (_run_directory(tmp_path) / "conceptual_model.md").read_text(
        encoding="utf-8"
    )

    for section in (
        "# Executive Summary",
        "# Business Overview",
        "# Business Domains",
        "# Business Entities",
        "# Entity Relationships",
        "# Mermaid Diagram",
        "# Business Rules",
        "# Assumptions",
        "# Recommendations",
    ):
        assert section in markdown

    assert "CUSTOMER ||--o{ SALES_ORDER" in markdown


def test_the_ai_receives_the_real_discovered_context(tmp_path: Path, fake_connector):
    """The AI step must be fed the deterministic artifacts from this run,
    not an empty or placeholder context."""
    client = StubLLMClient(LLM_RESPONSE)

    MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

    assert len(client.calls) == 1
    _, user_prompt, schema = client.calls[0]

    assert "app.customer" in user_prompt
    assert "app.orders.customer_id -> app.customer.customer_id" in user_prompt
    assert schema["additionalProperties"] is False


def test_run_without_an_llm_client_still_produces_deterministic_artifacts(
    tmp_path: Path, fake_connector
):
    """A missing API key must not cost the user the rest of the pipeline."""
    MigrationOrchestrator(_config(tmp_path), llm_client=None).run()

    produced = {p.name for p in _run_directory(tmp_path).iterdir()}

    assert "metadata.json" in produced
    assert "relationships.json" in produced
    assert "conceptual_model.md" not in produced


def test_conceptual_toggle_disables_only_the_ai_step(tmp_path: Path, fake_connector):
    config = _config(tmp_path)
    config.artifacts.conceptual_model = False
    client = StubLLMClient(LLM_RESPONSE)

    MigrationOrchestrator(config, llm_client=client).run()

    assert client.calls == []
    assert "conceptual_model.json" not in {
        p.name for p in _run_directory(tmp_path).iterdir()
    }


def test_connector_is_released_even_when_the_ai_step_fails(tmp_path: Path, fake_connector):
    """The AI step runs inside the try/finally, so a failure there must not
    leak the database connection."""

    class Boom:
        model = "boom"

        def complete(self, *args, **kwargs):
            raise RuntimeError("provider exploded")

    with pytest.raises(RuntimeError, match="provider exploded"):
        MigrationOrchestrator(_config(tmp_path), llm_client=Boom()).run()

    assert fake_connector.disconnected is True
    # The deterministic artifacts were already on disk before the failure.
    assert (_run_directory(tmp_path) / "metadata.json").exists()
