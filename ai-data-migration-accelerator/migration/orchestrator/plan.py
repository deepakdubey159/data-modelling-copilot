"""
Migration plan mode (`--plan`).

Connects to the source, extracts metadata read-only, and hands it to
`SchemaDependencyAnalyzer`. No profiling, no AI calls, no artifacts are
written - this is a preview a user runs before committing to a real
migration. Reuses `MetadataBuilder` and the connector factory exactly as the
full pipeline does, so the metadata a plan is computed from is identical to
what a real run would see.
"""

from __future__ import annotations

import logging

from migration.connectors.factory import create_connector
from migration.metadata.builder import MetadataBuilder
from migration.planner.dependency_analyzer import SchemaDependencyAnalyzer
from migration.planner.models import MigrationPlan

logger = logging.getLogger(__name__)


def build_migration_plan(config, schemas: list[str] | None = None) -> MigrationPlan:
    """Connect, extract metadata for `schemas` (default: every configured
    schema), and return the deterministic dependency-ordered plan.

    Always disconnects, even if analysis raises.
    """
    source = config.source
    target_schemas = schemas or list(source.schema_)

    connector = create_connector(source)
    connector.connect()
    try:
        builder = MetadataBuilder(
            connector=connector,
            database_name=source.database,
            database_type=source.type,
        )
        metadata = builder.build(target_schemas)
    finally:
        connector.disconnect()

    return SchemaDependencyAnalyzer(metadata).analyze()
