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

            20260721_224512/
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        run_directory = self.output_directory / timestamp

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