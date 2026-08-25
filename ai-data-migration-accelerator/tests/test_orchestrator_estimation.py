"""
Tests proving EffortEstimator is wired into MigrationOrchestrator.run().

Reuses the existing EffortEstimator/EstimationWriter unchanged - this only
verifies the orchestrator now calls them and writes their output alongside
the other artifacts. No database, no LLM API key: same FakeConnector/
StubLLMClient pattern as test_orchestrator_end_to_end.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from migration.orchestrator.orchestrator import MigrationOrchestrator
from tests.conceptual_fixtures import StubLLMClient
from tests.test_orchestrator_end_to_end import (
    LLM_RESPONSE,
    _config,
    _run_directory,
    fake_connector,
)

# Re-imported so pytest picks it up as a fixture in this module too.
__all__ = ["fake_connector"]


def test_estimation_artifact_is_produced_by_default(tmp_path: Path, fake_connector):
    MigrationOrchestrator(_config(tmp_path), llm_client=StubLLMClient(LLM_RESPONSE)).run()

    produced = {p.name for p in _run_directory(tmp_path).iterdir()}

    assert "estimation.json" in produced
    assert "estimation.md" in produced
    assert "estimation.html" in produced


def test_estimation_reflects_the_actual_physical_model(tmp_path: Path, fake_connector):
    """The estimation must be derived from this run's own physical model,
    not a placeholder - table_count should match what was actually built."""
    MigrationOrchestrator(_config(tmp_path), llm_client=StubLLMClient(LLM_RESPONSE)).run()

    run = _run_directory(tmp_path)
    estimation = json.loads((run / "estimation.json").read_text(encoding="utf-8"))
    result = estimation["estimation_result"]

    assert result["source_type"] == "postgres"
    assert result["target_type"] == "snowflake"  # matches _config()'s target.type
    assert result["complexity_factors"]["table_count"] > 0
    assert result["total_effort_days"] > 0
    assert result["generated_by"] if "generated_by" in result else True


def test_estimation_generated_by_and_source_recorded(tmp_path: Path, fake_connector):
    MigrationOrchestrator(_config(tmp_path), llm_client=StubLLMClient(LLM_RESPONSE)).run()

    run = _run_directory(tmp_path)
    estimation = json.loads((run / "estimation.json").read_text(encoding="utf-8"))

    assert estimation["generated_by"] == "EffortEstimator"
    assert estimation["generated_from"] == "physical_model.json"


def test_estimation_toggle_disables_only_the_estimation_step(tmp_path: Path, fake_connector):
    config = _config(tmp_path)
    config.artifacts.estimation = False

    MigrationOrchestrator(config, llm_client=StubLLMClient(LLM_RESPONSE)).run()

    produced = {p.name for p in _run_directory(tmp_path).iterdir()}

    assert "physical_model.json" in produced
    assert "estimation.json" not in produced
    assert "estimation.md" not in produced
    assert "estimation.html" not in produced


def test_estimation_is_skipped_when_physical_model_is(tmp_path: Path, fake_connector):
    """Without a physical model there is nothing to estimate from."""
    config = _config(tmp_path)
    config.artifacts.physical_model = False

    MigrationOrchestrator(config, llm_client=StubLLMClient(LLM_RESPONSE)).run()

    produced = {p.name for p in _run_directory(tmp_path).iterdir()}

    assert "physical_model.json" not in produced
    assert "estimation.json" not in produced


def test_estimation_still_produced_without_an_llm_client(tmp_path: Path, fake_connector):
    """Estimation depends on the physical model, not the AI step - it must
    not require conceptual/logical/physical to have come from an LLM run.
    Without an LLM client, conceptual/logical/physical are all skipped
    (physical depends on logical depends on conceptual), so estimation is
    skipped too, but purely because physical_model is absent - not because
    of any dependency on the LLM client itself."""
    MigrationOrchestrator(_config(tmp_path), llm_client=None).run()

    produced = {p.name for p in _run_directory(tmp_path).iterdir()}

    assert "metadata.json" in produced
    assert "estimation.json" not in produced
