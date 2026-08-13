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

from migration.conceptual.engine import ConceptualModelEngine
from migration.conceptual.writer import ConceptualModelWriter
from migration.logical.engine import LogicalModelEngine
from migration.logical.writer import LogicalModelWriter
from migration.connectors.factory import create_connector
from migration.metadata.builder import MetadataBuilder
from migration.output.writer import OutputWriter
from migration.profiler.engine import DataProfiler
from migration.relationship.engine import RelationshipEngine

logger = logging.getLogger(__name__)


class MigrationOrchestrator:

    def __init__(self, config, llm_client=None):

        self.config = config

        # Injected rather than constructed here, so a run without an AI
        # provider configured still produces every deterministic artifact.
        # Nothing in the deterministic pipeline depends on this being set.
        self.llm_client = llm_client

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

            relationships = None

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

            conceptual = None

            conceptual_files = None

            if getattr(self.config.artifacts, "conceptual_model", True):

                if self.llm_client is None:

                    logger.warning(
                        "Skipping conceptual model: no LLM client configured. "
                        "All deterministic artifacts were still produced."
                    )

                else:

                    logger.info("Generating conceptual model...")

                    conceptual_engine = ConceptualModelEngine(
                        client=self.llm_client,
                        model_name=self.config.llm.model,
                    )

                    conceptual = conceptual_engine.generate(
                        metadata,
                        profile,
                        relationships,
                    )

                    conceptual_files = ConceptualModelWriter().write(
                        conceptual,
                        run_directory,
                    )

                    logger.info(
                        "Conceptual model written to %s, %s and %s",
                        conceptual_files[0],
                        conceptual_files[1],
                        conceptual_files[2],
                    )

            logical_files = None

            if getattr(self.config.artifacts, "logical_model", True):

                if conceptual is None:

                    logger.warning(
                        "Skipping logical model: it is derived from the conceptual "
                        "model, which was not produced in this run."
                    )

                else:

                    logger.info("Deriving logical model...")

                    logical = LogicalModelEngine(
                        conceptual,
                        source_artifact="conceptual_model.json",
                    ).generate()

                    logical_files = LogicalModelWriter().write(
                        logical,
                        run_directory,
                    )

                    logger.info(
                        "Logical model written to %s, %s and %s",
                        logical_files[0],
                        logical_files[1],
                        logical_files[2],
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

            if conceptual_files is not None:

                print(f"Conceptual    : {conceptual_files[0]}")

                print(f"                {conceptual_files[1]}")

                print(f"                {conceptual_files[2]}")

            if logical_files is not None:

                print(f"Logical       : {logical_files[0]}")

                print(f"                {logical_files[1]}")

                print(f"                {logical_files[2]}")

            print("=" * 70)

            print()

        finally:

            connector.disconnect()

            logger.info("Disconnected from database.")