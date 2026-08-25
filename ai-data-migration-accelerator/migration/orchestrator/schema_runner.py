"""
Schema-wise migration execution.

Wraps `MigrationOrchestrator` - unchanged - to run one schema at a time
instead of sending every configured schema through a single pipeline run.
Each schema gets its own output directory
(`<output_directory>/<schema_name>/<timestamp>/...`) and its own entry in a
status file, so a later rerun can skip schemas that already completed.

This module contains no pipeline logic of its own: it only clones the
validated config per schema and delegates to `MigrationOrchestrator.run()`,
which is why adding schema-wise execution required no change to the
orchestrator's engines or artifact-writing logic.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from migration.orchestrator.orchestrator import MigrationOrchestrator

logger = logging.getLogger(__name__)

STATUS_FILENAME = ".migration_status.json"


class SchemaExecutionError(Exception):
    """Raised when one schema's pipeline run fails. Carries the schema name
    so a multi-schema run can report which one broke without stopping the
    others."""

    def __init__(self, schema_name: str, cause: Exception):
        self.schema_name = schema_name
        self.cause = cause
        super().__init__(f"Schema '{schema_name}' failed: {cause}")


class SchemaRunResult:
    """Outcome for one schema in a schema-wise run."""

    def __init__(
        self,
        schema_name: str,
        status: str,
        run_directory: Optional[Path] = None,
        error: Optional[str] = None,
    ):
        self.schema_name = schema_name
        self.status = status  # "completed" | "failed" | "skipped"
        self.run_directory = run_directory
        self.error = error


def _status_file_path(output_directory: Path) -> Path:
    return output_directory / STATUS_FILENAME


def load_status(output_directory: Path) -> dict:
    """Read the status file. Returns {} if it does not exist yet - a first
    run of any schema is never blocked by a missing status file."""
    path = _status_file_path(output_directory)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read status file %s (%s); treating as empty.", path, exc)
        return {}


def save_status(output_directory: Path, status: dict) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    path = _status_file_path(output_directory)
    with path.open("w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, default=str)


def _schema_config(config, schema_name: str):
    """Clone the validated config for a single-schema run: same source
    connection, but scoped to one schema and writing under its own
    subdirectory of the configured output directory."""
    per_schema = config.model_copy(deep=True)
    per_schema.source.schema_ = [schema_name]
    per_schema.project.output_directory = Path(config.project.output_directory) / schema_name
    return per_schema


def run_schemas(
    config,
    llm_client,
    schemas: list[str],
    force: bool = False,
) -> list[SchemaRunResult]:
    """Run the full pipeline once per schema in `schemas`.

    A schema already marked "completed" in the status file is skipped
    unless `force=True` - this is what makes a rerun after a partial
    failure resume rather than reprocess everything. Schemas are
    independent: one failing does not stop the others from running, so the
    caller gets a complete picture of what succeeded.
    """
    base_output_directory = Path(config.project.output_directory)
    status = load_status(base_output_directory)
    results: list[SchemaRunResult] = []

    for schema_name in schemas:
        existing = status.get(schema_name)
        if not force and existing and existing.get("status") == "completed":
            logger.info(
                "Skipping schema '%s': already completed at %s "
                "(use --force to rerun).",
                schema_name,
                existing.get("run_directory"),
            )
            results.append(
                SchemaRunResult(
                    schema_name,
                    status="skipped",
                    run_directory=Path(existing["run_directory"])
                    if existing.get("run_directory")
                    else None,
                )
            )
            continue

        logger.info("Running pipeline for schema '%s'...", schema_name)
        per_schema_config = _schema_config(config, schema_name)

        try:
            run_directory = MigrationOrchestrator(per_schema_config, llm_client=llm_client).run()
            status[schema_name] = {
                "status": "completed",
                "run_directory": str(run_directory),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            save_status(base_output_directory, status)
            results.append(
                SchemaRunResult(schema_name, status="completed", run_directory=run_directory)
            )
        except Exception as exc:
            logger.exception("Schema '%s' failed", schema_name)
            status[schema_name] = {
                "status": "failed",
                "error": str(exc),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
            save_status(base_output_directory, status)
            results.append(SchemaRunResult(schema_name, status="failed", error=str(exc)))

    return results
