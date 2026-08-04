"""
Migration Orchestrator

Coordinates the end-to-end execution flow.

Responsibilities

Load configuration
        ↓
Create connector
        ↓
Connect
        ↓
Extract metadata
        ↓
Build canonical metadata
        ↓
Write metadata.json
        ↓
Disconnect
"""

from __future__ import annotations

import logging

from migration.connectors.factory import create_connector
from migration.metadata.builder import MetadataBuilder
from migration.output.writer import OutputWriter
from migration.profiler.engine import DataProfiler
from migration.relationship.engine import RelationshipEngine

logger = logging.getLogger(__name__)


class MigrationOrchestrator:

    def __init__(self, config):

        self.config = config

    def run(self):

        source = self.config.source

        logger.info("Creating connector...")

        connector = create_connector(
            source
        )

        logger.info("Connecting...")

        connector.connect()

        logger.info("Connection successful.")

        try:

            logger.info("Building metadata...")

            builder = MetadataBuilder(
                connector=connector,
                database_name=source.database,
                database_type=source.type,
            )

            metadata = builder.build(
                source.schema_
            )

            writer = OutputWriter(
                self.config.project.output_directory
            )

            run_directory = writer.create_run_directory()

            metadata_file = writer.write_metadata(
                metadata,
                run_directory,
            )

            logger.info(
                "Metadata written to %s",
                metadata_file,
            )

            profile = None

            profile_file = None

            if hasattr(self.config.artifacts, "profile") and self.config.artifacts.profile:

                logger.info("Profiling data...")

                profiler = DataProfiler(connector=connector)

                profile = profiler.profile(metadata.metadata)

                profile_file = writer.write_profile(
                    profile,
                    run_directory,
                )

                logger.info(
                    "Profile written to %s",
                    profile_file,
                )

            relationships_file = None

            if getattr(self.config.artifacts, "relationships", True):

                logger.info("Discovering relationships...")

                engine = RelationshipEngine(
                    metadata=metadata.metadata,
                    profile=profile.profile if profile is not None else None,
                )

                relationships = engine.discover()

                relationships_file = writer.write_relationships(
                    relationships,
                    run_directory,
                )

                logger.info(
                    "Relationships written to %s",
                    relationships_file,
                )

            writer.write_execution_summary(
                run_directory,
                source.database,
            )

            print()

            print("=" * 70)

            print("Metadata extraction completed successfully.")

            print(f"Output Folder : {run_directory}")

            print(f"Metadata File : {metadata_file}")

            if profile_file is not None:

                print(f"Profile File  : {profile_file}")

            if relationships_file is not None:

                print(f"Relationships : {relationships_file}")

            print("=" * 70)

            print()

        finally:

            connector.disconnect()

            logger.info("Disconnected from database.")