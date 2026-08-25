"""DDL writer.

Writes generated DDL to files: SQL script and metadata JSON.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from migration.ddl.models import DDLPackage

logger = logging.getLogger(__name__)


class DDLWriter:
    """Writes DDL packages to disk."""

    def write(self, package: DDLPackage, run_directory: Path) -> tuple[Path, Path]:
        """Write DDL script and metadata. Returns (sql_file, json_file)."""
        return (
            self.write_sql(package, run_directory),
            self.write_json(package, run_directory),
        )

    def write_sql(self, package: DDLPackage, run_directory: Path) -> Path:
        """Write the SQL script."""
        output_file = run_directory / "databricks.sql"
        with open(output_file, "w", encoding="utf-8") as fp:
            fp.write(package.ddl_script.to_sql(include_comments=True))
        return output_file

    def write_json(self, package: DDLPackage, run_directory: Path) -> Path:
        """Write the DDL metadata."""
        output_file = run_directory / "ddl.json"
        with open(output_file, "w", encoding="utf-8") as fp:
            json.dump(package.model_dump(mode="json"), fp, indent=4, default=str)
        return output_file
