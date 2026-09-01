"""
Tests for migration.orchestrator.schema_runner - schema-wise execution and
resumability. No database and no API key: the connector is faked at the
factory boundary (same pattern as test_orchestrator_end_to_end.py) and the
LLM client is a stub.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from migration.orchestrator import orchestrator as orchestrator_module
from migration.orchestrator.schema_runner import load_status, run_schemas
from tests.conceptual_fixtures import StubLLMClient
from tests.test_orchestrator_end_to_end import LLM_RESPONSE, FakeConnector, _config


@pytest.fixture
def fake_connector(monkeypatch) -> FakeConnector:
    connector = FakeConnector()
    monkeypatch.setattr(orchestrator_module, "create_connector", lambda source: connector)
    return connector


class FailingConnector(FakeConnector):
    def connect(self):
        raise RuntimeError("connection refused")


def test_each_schema_gets_its_own_output_directory(tmp_path: Path, fake_connector):
    config = _config(tmp_path)
    client = StubLLMClient(LLM_RESPONSE, model="claude-opus-5")

    results = run_schemas(config, client, schemas=["bronze", "silver"])

    assert {r.schema_name for r in results} == {"bronze", "silver"}
    assert all(r.status == "completed" for r in results)
    assert (tmp_path / "bronze").is_dir()
    assert (tmp_path / "silver").is_dir()


def test_completed_schema_is_skipped_on_rerun(tmp_path: Path, fake_connector):
    config = _config(tmp_path)
    client = StubLLMClient(LLM_RESPONSE, model="claude-opus-5")

    first = run_schemas(config, client, schemas=["bronze"])
    assert first[0].status == "completed"

    # A second run of the same schema, without --force, must not re-execute
    # the pipeline for it.
    second = run_schemas(config, client, schemas=["bronze"])

    assert second[0].status == "skipped"
    # Only the first run created a subdirectory under bronze/.
    bronze_runs = [p for p in (tmp_path / "bronze").iterdir() if p.is_dir()]
    assert len(bronze_runs) == 1


def test_force_reruns_a_completed_schema(tmp_path: Path, monkeypatch):
    """--force must re-execute the pipeline rather than skip, even though
    the schema already completed. Proven by counting connector.connect()
    calls directly, rather than by directory uniqueness -
    `create_run_directory()` has only second-level timestamp resolution, so
    two runs in the same test can legitimately land in the same directory."""
    config = _config(tmp_path)
    client = StubLLMClient(LLM_RESPONSE, model="claude-opus-5")

    connect_calls = []

    def factory(source):
        connector = FakeConnector()
        original_connect = connector.connect

        def counted_connect():
            connect_calls.append(1)
            return original_connect()

        connector.connect = counted_connect
        return connector

    monkeypatch.setattr(orchestrator_module, "create_connector", factory)

    run_schemas(config, client, schemas=["bronze"])
    assert len(connect_calls) == 1

    forced = run_schemas(config, client, schemas=["bronze"], force=True)

    assert forced[0].status == "completed"
    assert len(connect_calls) == 2  # pipeline genuinely reran, not skipped


def test_status_file_records_completed_schemas(tmp_path: Path, fake_connector):
    config = _config(tmp_path)
    client = StubLLMClient(LLM_RESPONSE, model="claude-opus-5")

    run_schemas(config, client, schemas=["bronze"])

    status = load_status(tmp_path)
    assert status["bronze"]["status"] == "completed"
    assert "run_directory" in status["bronze"]


def test_one_schema_failing_does_not_block_the_others(tmp_path: Path, monkeypatch):
    """Schema A succeeds, schema B fails - A's result must still be reported
    as completed, and B's failure must not raise out of run_schemas."""
    config = _config(tmp_path)
    client = StubLLMClient(LLM_RESPONSE, model="claude-opus-5")

    def factory(source):
        if source.schema_ == ["silver"]:
            return FailingConnector()
        return FakeConnector()

    monkeypatch.setattr(orchestrator_module, "create_connector", factory)

    results = run_schemas(config, client, schemas=["bronze", "silver"])
    by_name = {r.schema_name: r for r in results}

    assert by_name["bronze"].status == "completed"
    assert by_name["silver"].status == "failed"
    assert "connection refused" in by_name["silver"].error


def test_failed_schema_can_be_retried_after_fix(tmp_path: Path, monkeypatch):
    """Rerunning after a failure must attempt the failed schema again (not
    skip it) since it never reached 'completed'."""
    config = _config(tmp_path)
    client = StubLLMClient(LLM_RESPONSE, model="claude-opus-5")

    attempt = {"count": 0}

    def factory(source):
        if source.schema_ == ["silver"] and attempt["count"] == 0:
            attempt["count"] += 1
            return FailingConnector()
        return FakeConnector()

    monkeypatch.setattr(orchestrator_module, "create_connector", factory)

    first = run_schemas(config, client, schemas=["silver"])
    assert first[0].status == "failed"

    second = run_schemas(config, client, schemas=["silver"])
    assert second[0].status == "completed"
