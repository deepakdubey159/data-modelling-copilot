"""
Output Writer

Responsible for writing generated artifacts to disk.

This module contains no business logic.

Current artifacts:
    - metadata.json

Future:
    - profile.json
    - conceptual.md
    - logical.md
    - physical.md
    - ddl.sql
    - dml.sql
    - migration_report.md
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from migration.canonical.models import MetadataPackage
from migration.profiler.models import ProfilePackage
from migration.relationship.models import RelationshipPackage


class OutputWriter:
    """
    Writes generated artifacts into the output directory.
    """

    def __init__(self, output_directory: str):

        self.output_directory = Path(output_directory)

    def create_run_directory(self) -> Path:
        """
        Creates a timestamped execution folder.

        Example

        output/

            20260721_224512_123456/

        Microsecond precision (rather than the previous second-level
        `%Y%m%d_%H%M%S`) makes two runs in the same second land in
        different directories in the overwhelmingly common case. A numeric
        suffix is appended on top of that for the rare case where the
        clock's actual resolution is coarser than a microsecond (or two
        calls land in the same tick) - this guarantees a distinct directory
        per call rather than silently reusing/overwriting a prior run's
        output.
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        run_directory = self.output_directory / timestamp
        suffix = 1
        while run_directory.exists():
            run_directory = self.output_directory / f"{timestamp}_{suffix}"
            suffix += 1

        run_directory.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {self.output_directory.resolve()}")
        print(f"Run directory: {run_directory.resolve()}")

        return run_directory

    def write_metadata(
        self,
        metadata: MetadataPackage,
        run_directory: Path,
    ) -> Path:
        """
        Writes metadata.json
        """

        output_file = run_directory / "metadata.json"

        with open(output_file, "w", encoding="utf-8") as fp:

            json.dump(
                metadata.model_dump(),
                fp,
                indent=4,
                default=str,
            )

        return output_file

    def write_profile(
        self,
        profile: ProfilePackage,
        run_directory: Path,
     ) -> Path:
        """
        Writes profile.json
        """

        output_file = run_directory / "profile.json"

        with open(output_file, "w", encoding="utf-8") as fp:

            json.dump(
                profile.model_dump(),
                fp,
                indent=4,
                default=str,
            )

        return output_file

    def write_relationships(
        self,
        relationships: RelationshipPackage,
        run_directory: Path,
    ) -> Path:
        """
        Writes relationships.json
        """

        output_file = run_directory / "relationships.json"

        with open(output_file, "w", encoding="utf-8") as fp:

            json.dump(
                relationships.model_dump(mode="json"),
                fp,
                indent=4,
                default=str,
            )

        return output_file

    def write_execution_summary(
        self,
        run_directory: Path,
        database_name: str,
    ) -> None:
        """
        Simple execution summary.

        This file is temporary.
        Later it will become migration_report.md
        """

        summary = run_directory / "summary.txt"

        with open(summary, "w", encoding="utf-8") as fp:

            fp.write("AI Data Migration Accelerator\n")
            fp.write("---------------------------------\n")
            fp.write(f"Database : {database_name}\n")
            fp.write(
                f"Generated : {datetime.now().isoformat()}\n"
            )