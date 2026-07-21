"""
Configuration loading for the AI Data Migration Accelerator.

Responsibility (single): turn a path to a YAML file into a validated
`AppConfig`. Nothing else. Env-var resolution and file I/O live here so that
every other component can simply depend on an already-valid `AppConfig`
object.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from migration.models.config import AppConfig

_ENV_VAR_PATTERN = re.compile(r"\$\{(?P<name>[A-Z0-9_]+)(:-(?P<default>[^}]*))?\}")


class ConfigError(Exception):
    """Raised when a config file cannot be loaded or fails validation."""


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ``${VAR}`` / ``${VAR:-default}`` references.

    This lets `config.yaml` reference secrets (e.g. ``password:
    ${SOURCE_DB_PASSWORD}``) that are supplied via environment variables or a
    `.env` file, instead of being hardcoded in a file that might be committed.
    """
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(v) for v in value]
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            name = match.group("name")
            default = match.group("default")
            resolved = os.environ.get(name)
            if resolved is not None:
                return resolved
            if default is not None:
                return default
            raise ConfigError(
                f"Environment variable '{name}' referenced in config but not set, "
                "and no default was provided."
            )
        return _ENV_VAR_PATTERN.sub(_replace, value)
    return value


def load_raw_yaml(config_path: Path) -> dict[str, Any]:
    """Read and parse a YAML file into a plain dict. No validation here."""
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    if not config_path.is_file():
        raise ConfigError(f"Config path is not a file: {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML in {config_path}: {exc}") from exc

    if data is None:
        raise ConfigError(f"Config file is empty: {config_path}")
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must define a mapping at the top level: {config_path}")

    return data


def load_config(config_path: str | Path) -> AppConfig:
    """Load, resolve, and validate a config file into an `AppConfig`.

    Raises `ConfigError` for anything that goes wrong — missing file, bad
    YAML, unresolved env var, or a schema validation failure. Callers (the
    CLI) are expected to catch `ConfigError` and exit with a clean message
    rather than a raw traceback.
    """
    path = Path(config_path)
    raw = load_raw_yaml(path)
    resolved = _resolve_env_vars(raw)

    try:
        return AppConfig.model_validate(resolved)
    except ValidationError as exc:
        raise ConfigError(f"Configuration validation failed for {path}:\n{exc}") from exc
