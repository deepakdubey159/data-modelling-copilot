#!/usr/bin/env python3
"""
AI Data Migration Accelerator — CLI entry point.

Milestone 1 scope:
    - Load and validate config.yaml
    - Initialize the source connector (PostgreSQL only)
    - Validate the connection
    - Extract table metadata and print discovered schemas/tables

Usage:
    python migrate.py --config config.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys

from rich.console import Console
from rich.table import Table

from migration.connectors.factory import UnsupportedSourceError, create_connector
from migration.orchestrator.orchestrator import MigrationOrchestrator
from migration.connectors.base import ConnectorError
from migration.utils.config_loader import ConfigError, load_config
from migration.utils.logging_setup import setup_logging

console = Console()
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="migrate.py",
        description="AI-powered universal data migration accelerator.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the YAML configuration file (e.g. config.yaml)",
    )
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Logging is set up before config validation so that even a config
    # failure is captured in a log file, not just printed to stderr.
    setup_logging(level="INFO")

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        return 1

    # Now that config is validated, reconfigure logging at the requested level.
    setup_logging(level=config.logging.level.value)
    logger.info("Loaded configuration for project '%s'", config.project.name)

    try:
        orchestrator = MigrationOrchestrator(config)
        orchestrator.run()
    except UnsupportedSourceError as exc:
        console.print(f"[bold red]Unsupported source:[/bold red] {exc}")
        return 1

    
    except ConnectorError as exc:
        console.print(f"[bold red]Connection failed:[/bold red] {exc}")
        return 1



    except Exception  as exc:
        logger.exception(exc)
        console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        return 1


    return 0


def _print_discovered_tables(schemas: list[str], tables: list[dict]) -> None:
    console.print(f"\n[bold]Schemas requested:[/bold] {', '.join(schemas)}")

    if not tables:
        console.print("[yellow]No tables found in the requested schema(s).[/yellow]")
        return

    table = Table(title="Discovered Tables")
    table.add_column("Schema", style="cyan")
    table.add_column("Table", style="magenta")
    table.add_column("Type", style="green")

    for row in tables:
        table.add_row(row["table_schema"], row["table_name"], row["table_type"])

    console.print(table)
    console.print(f"\n[bold]Total tables discovered:[/bold] {len(tables)}")


if __name__ == "__main__":
    sys.exit(run())
