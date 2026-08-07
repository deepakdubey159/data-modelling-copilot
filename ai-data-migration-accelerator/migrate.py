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
from migration.llm.factory import (
    MissingAPIKeyError,
    UnsupportedProviderError,
    create_llm_client,
)
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


def _load_dotenv() -> None:
    """Load a local .env so API keys and passwords resolve without exporting
    them by hand. Absent file and absent package are both fine — the config
    loader falls back to the real environment either way."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _build_llm_client(config):
    """Build the LLM client, or return None with a clear explanation.

    A missing key must not cost the user their metadata, profile and
    relationship artifacts, so this degrades rather than aborting. The
    deterministic pipeline has no dependency on the AI layer.
    """
    if not getattr(config.artifacts, "conceptual_model", True):
        return None

    try:
        return create_llm_client(config.llm)
    except MissingAPIKeyError as exc:
        console.print(f"[yellow]Skipping AI artifacts:[/yellow] {exc}")
    except UnsupportedProviderError as exc:
        console.print(f"[yellow]Skipping AI artifacts:[/yellow] {exc}")
    return None


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Logging is set up before config validation so that even a config
    # failure is captured in a log file, not just printed to stderr.
    setup_logging(level="INFO")
    _load_dotenv()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        return 1

    # Now that config is validated, reconfigure logging at the requested level.
    setup_logging(level=config.logging.level.value)
    logger.info("Loaded configuration for project '%s'", config.project.name)

    llm_client = _build_llm_client(config)

    try:
        orchestrator = MigrationOrchestrator(config, llm_client=llm_client)
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
