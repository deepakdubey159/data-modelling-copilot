#!/usr/bin/env python3
"""
AI Data Migration Accelerator — CLI entry point.

Usage:
    python migrate.py --config config.yaml
    python migrate.py --config config.yaml --plan
    python migrate.py --config config.yaml --execute-plan
    python migrate.py --config config.yaml --schema bronze
    python migrate.py --config config.yaml --schema bronze --schema silver
    python migrate.py --config config.yaml --schema bronze --force
    python migrate.py --config config.yaml --publish
    python migrate.py --config config.yaml --execute-ddl output/bronze/20260101_000000/ddl.json
    python migrate.py --config config.yaml --execute-ddl output/bronze/20260101_000000/ddl.json --live
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from migration.connectors.factory import UnsupportedSourceError
from migration.ddl.models import DDLPackage
from migration.llm.factory import (
    MissingAPIKeyError,
    UnsupportedProviderError,
    create_llm_client,
)
from migration.orchestrator.plan import build_migration_plan
from migration.orchestrator.schema_runner import run_schemas
from migration.connectors.base import ConnectorError
from migration.target.databricks_executor import (
    DatabricksExecutionError,
    DatabricksExecutor,
)
from migration.utils.config_loader import ConfigError, load_config
from migration.utils.logging_setup import setup_logging
from migration.workspace import DatabricksWorkspaceClient

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
    parser.add_argument(
        "--schema",
        action="append",
        dest="schemas",
        metavar="SCHEMA",
        help="Run only this schema. Repeat to select several "
        "(e.g. --schema bronze --schema silver). Default: every schema "
        "listed under source.schema in config.yaml.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show the recommended migration order (FK dependency analysis) "
        "and exit. Connects to the source read-only; writes nothing.",
    )
    parser.add_argument(
        "--execute-plan",
        action="store_true",
        help="Compute the same deterministic FK-dependency order as --plan, "
        "then execute schemas in that order. Refuses to execute (exit code "
        "1) if a circular schema or table dependency is detected, instead "
        "of guessing an order.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun schemas even if a previous run already completed them.",
    )
    parser.add_argument(
        "--execute-ddl",
        metavar="DDL_JSON_PATH",
        help="Execute a previously generated ddl.json against the "
        "configured Databricks target. Defaults to a dry run (no "
        "connection); pass --live to actually execute.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="With --execute-ddl, actually run the DDL against Databricks "
        "instead of previewing it.",
    )
    parser.add_argument(
        "--publish-ddl",
        metavar="SQL_FILE_PATH",
        help="Publish the generated SQL file to Databricks Workspace using the "
        "Workspace REST API. Requires DATABRICKS_HOST, DATABRICKS_TOKEN, and "
        "DATABRICKS_WORKSPACE_PATH environment variables.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Run the full migration pipeline and automatically publish the "
        "generated databricks.sql to Databricks Workspace. Requires the same "
        "environment variables as --publish-ddl. Does NOT execute the SQL.",
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


def _print_plan(plan) -> None:
    console.print("\n[bold]Recommended migration order (schemas):[/bold]")
    if plan.schema_cycles:
        console.print("[bold red]Circular schema dependencies detected — no linear order exists:[/bold red]")
        for cycle in plan.schema_cycles:
            console.print(f"  [red]cycle:[/red] {' -> '.join(cycle.tables)}")
    else:
        for i, schema_name in enumerate(plan.recommended_schema_order, start=1):
            console.print(f"  {i}. {schema_name}")

    console.print("\n[bold]Recommended migration order (tables):[/bold]")
    if plan.table_cycles:
        console.print("[bold red]Circular table dependencies detected — no linear order exists:[/bold red]")
        for cycle in plan.table_cycles:
            console.print(f"  [red]cycle:[/red] {' -> '.join(cycle.tables)}")
    else:
        for i, table_name in enumerate(plan.recommended_table_order, start=1):
            console.print(f"  {i}. {table_name}")

    if plan.cross_schema_foreign_keys:
        console.print("\n[bold]Cross-schema foreign keys:[/bold]")
        for dep in plan.cross_schema_foreign_keys:
            console.print(f"  {dep.table} -> {dep.depends_on} ({dep.constraint_name})")

    if plan.explanation:
        console.print("\n[bold]Why this order:[/bold]")
        for line in plan.explanation:
            console.print(f"  - {line}")


def _run_plan_mode(config, args) -> int:
    try:
        plan = build_migration_plan(config, schemas=args.schemas)
    except ConnectorError as exc:
        console.print(f"[bold red]Connection failed:[/bold red] {exc}")
        return 1
    except Exception as exc:
        logger.exception(exc)
        console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        return 1

    _print_plan(plan)
    return 1 if plan.has_cycles else 0


def _run_execute_ddl_mode(config, args) -> int:
    ddl_path = Path(args.execute_ddl)
    if not ddl_path.exists():
        console.print(f"[bold red]DDL file not found:[/bold red] {ddl_path}")
        return 1

    try:
        with ddl_path.open("r", encoding="utf-8") as f:
            package = DDLPackage.model_validate(json.load(f))
    except Exception as exc:
        console.print(f"[bold red]Could not read DDL file:[/bold red] {exc}")
        return 1

    dry_run = not args.live
    executor = DatabricksExecutor(config.target)

    try:
        result = executor.run(package.ddl_script, dry_run=dry_run)
    except DatabricksExecutionError as exc:
        console.print(f"[bold red]Databricks execution failed:[/bold red] {exc}")
        return 1

    if dry_run:
        console.print(
            f"\n[bold]Dry run:[/bold] {result.statement_count} statement(s) would "
            f"be executed. Pass --live to actually run them."
        )
        for r in result.results:
            console.print(f"  [cyan]{r.statement.statement_type}[/cyan] {r.statement.statement[:100]}")
        return 0

    console.print(
        f"\n[bold]Executed {result.statement_count} statement(s), "
        f"{result.failed_count} failed.[/bold]"
    )
    if not result.succeeded:
        console.print(f"[bold red]First error:[/bold red] {result.first_error}")
        return 1
    return 0


def _run_publish_ddl_mode(config, args) -> int:
    """Publish SQL file to Databricks Workspace using REST API."""
    sql_path = Path(args.publish_ddl)
    if not sql_path.exists():
        console.print(f"[bold red]SQL file not found:[/bold red] {sql_path}")
        return 1

    # Get Databricks credentials from config
    try:
        host = os.getenv(config.target.host_env)
        token = os.getenv(config.target.token_env)
        workspace_path = os.getenv(config.target.workspace_path_env)

        if not host:
            console.print(f"[bold red]Missing environment variable:[/bold red] {config.target.host_env}")
            return 1
        if not token:
            console.print(f"[bold red]Missing environment variable:[/bold red] {config.target.token_env}")
            return 1
        if not workspace_path:
            console.print(f"[bold red]Missing environment variable:[/bold red] {config.target.workspace_path_env}")
            return 1
    except AttributeError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        return 1

    # Create client and publish
    try:
        client = DatabricksWorkspaceClient(host=host, token=token)
        client.publish_sql_file(sql_file_path=sql_path, workspace_path=workspace_path)
        console.print(f"[green]Published SQL file to workspace:[/green] {workspace_path}")
        return 0
    except FileNotFoundError as exc:
        console.print(f"[bold red]File error:[/bold red] {exc}")
        return 1
    except Exception as exc:
        logger.exception(exc)
        console.print(f"[bold red]Workspace publishing failed:[/bold red] {exc}")
        return 1


def _print_schema_results(results) -> bool:
    """Print the per-schema outcome table. Returns True if any schema failed."""
    any_failed = False
    console.print("\n[bold]Schema execution summary:[/bold]")
    for result in results:
        if result.status == "completed":
            console.print(f"  [green]completed[/green] {result.schema_name} -> {result.run_directory}")
        elif result.status == "skipped":
            console.print(f"  [yellow]skipped[/yellow]   {result.schema_name} (already completed; use --force to rerun)")
        else:
            any_failed = True
            console.print(f"  [red]failed[/red]    {result.schema_name}: {result.error}")
    return any_failed


def _migrate_schemas(config, args) -> tuple[list, bool]:
    """Run migration for selected schemas. Returns (results, any_failed)."""
    llm_client = _build_llm_client(config)
    schemas = args.schemas or list(config.source.schema_)

    try:
        results = run_schemas(config, llm_client, schemas=schemas, force=args.force)
    except UnsupportedSourceError as exc:
        console.print(f"[bold red]Unsupported source:[/bold red] {exc}")
        return [], True

    any_failed = _print_schema_results(results)
    return results, any_failed


def _run_migration_mode(config, args) -> int:
    results, any_failed = _migrate_schemas(config, args)
    return 1 if any_failed else 0


def _run_execute_plan_mode(config, args) -> int:
    """Compute the deterministic FK-dependency order (identical analysis to
    --plan, never LLM-driven) and execute schemas in that order. Refuses to
    execute - rather than guess - when a circular dependency exists."""
    try:
        plan = build_migration_plan(config, schemas=args.schemas)
    except ConnectorError as exc:
        console.print(f"[bold red]Connection failed:[/bold red] {exc}")
        return 1
    except Exception as exc:
        logger.exception(exc)
        console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        return 1

    if plan.has_cycles:
        console.print(
            "[bold red]Refusing to execute: circular dependency detected.[/bold red]"
        )
        _print_plan(plan)
        return 1

    console.print("\n[bold]Executing schemas in dependency order:[/bold]")
    for i, schema_name in enumerate(plan.recommended_schema_order, start=1):
        console.print(f"  {i}. {schema_name}")

    llm_client = _build_llm_client(config)

    try:
        results = run_schemas(
            config,
            llm_client,
            schemas=plan.recommended_schema_order,
            force=args.force,
        )
    except UnsupportedSourceError as exc:
        console.print(f"[bold red]Unsupported source:[/bold red] {exc}")
        return 1

    any_failed = _print_schema_results(results)
    return 1 if any_failed else 0


def _run_publish_and_migrate_mode(config, args) -> int:
    """Run migration, then automatically publish generated databricks.sql files."""
    # Run migration
    results, migration_failed = _migrate_schemas(config, args)
    if migration_failed or not results:
        return 1

    # Get Databricks credentials
    try:
        host = os.getenv(config.target.host_env)
        token = os.getenv(config.target.token_env)
        workspace_path = os.getenv(config.target.workspace_path_env)

        if not host:
            console.print(f"[bold red]Missing environment variable:[/bold red] {config.target.host_env}")
            return 1
        if not token:
            console.print(f"[bold red]Missing environment variable:[/bold red] {config.target.token_env}")
            return 1
        if not workspace_path:
            console.print(f"[bold red]Missing environment variable:[/bold red] {config.target.workspace_path_env}")
            return 1
    except AttributeError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        return 1

    # Publish generated SQL files
    client = DatabricksWorkspaceClient(host=host, token=token)
    publish_failed = False

    for result in results:
        if result.status != "completed":
            continue

        run_dir = Path(result.run_directory)
        sql_file = run_dir / "databricks.sql"

        if not sql_file.exists():
            console.print(f"[yellow]Warning:[/yellow] databricks.sql not found in {run_dir}")
            continue

        try:
            client.publish_sql_file(sql_file_path=sql_file, workspace_path=workspace_path)
            console.print(f"[green]Published SQL for schema:[/green] {result.schema_name}")
        except FileNotFoundError as exc:
            console.print(f"[bold red]File error:[/bold red] {exc}")
            publish_failed = True
        except Exception as exc:
            logger.exception(exc)
            console.print(f"[bold red]Publishing failed for {result.schema_name}:[/bold red] {exc}")
            publish_failed = True

    return 1 if publish_failed else 0


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

    if args.publish_ddl:
        return _run_publish_ddl_mode(config, args)

    if args.publish:
        return _run_publish_and_migrate_mode(config, args)

    if args.execute_ddl:
        return _run_execute_ddl_mode(config, args)

    if args.plan:
        return _run_plan_mode(config, args)

    if args.execute_plan:
        return _run_execute_plan_mode(config, args)

    return _run_migration_mode(config, args)


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


def main() -> None:
    """Console-script entry point (`migration-accelerator`)."""
    sys.exit(run())


if __name__ == "__main__":
    main()
