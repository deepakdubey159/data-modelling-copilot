"""Tests for migration.utils.config_loader and migration.models.config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from migration.models.config import AppConfig, SourceType
from migration.utils.config_loader import ConfigError, load_config

VALID_CONFIG = """
project:
  name: customer_migration
  output_directory: output/

source:
  type: postgres
  host: localhost
  port: 5432
  database: sales
  username: postgres
  password: postgres
  schema:
    - public

target:
  type: snowflake

llm:
  provider: openai
  model: gpt-5.5
  temperature: 0

artifacts:
  conceptual_model: true
  logical_model: true
  physical_model: true
  ddl: true
  dml: true
  report: true
  estimation: true

logging:
  level: INFO
"""


@pytest.fixture
def valid_config_file(tmp_path: Path) -> Path:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_CONFIG)
    return config_file


def test_load_config_success(valid_config_file: Path):
    config = load_config(valid_config_file)
    assert isinstance(config, AppConfig)
    assert config.project.name == "customer_migration"
    assert config.source.type == SourceType.POSTGRES
    assert config.source.schema_ == ["public"]
    assert config.llm.temperature == 0


def test_missing_file_raises_config_error(tmp_path: Path):
    missing_path = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ConfigError, match="not found"):
        load_config(missing_path)


def test_empty_file_raises_config_error(tmp_path: Path):
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("")
    with pytest.raises(ConfigError, match="empty"):
        load_config(empty_file)


def test_invalid_yaml_raises_config_error(tmp_path: Path):
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("project: [unclosed")
    with pytest.raises(ConfigError, match="Failed to parse YAML"):
        load_config(bad_file)


def test_missing_required_field_raises_config_error(tmp_path: Path):
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text("project:\n  name: test\n")
    with pytest.raises(ConfigError, match="validation failed"):
        load_config(incomplete)


def test_empty_schema_list_rejected(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        VALID_CONFIG.replace("  schema:\n    - public", "  schema: []")
    )
    with pytest.raises(ConfigError, match="at least one schema"):
        load_config(config_file)


def test_env_var_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TEST_DB_PASSWORD", "secret123")
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        VALID_CONFIG.replace("password: postgres", "password: ${TEST_DB_PASSWORD}")
    )
    config = load_config(config_file)
    assert config.source.password == "secret123"


def test_env_var_missing_without_default_raises(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        VALID_CONFIG.replace("password: postgres", "password: ${UNSET_TEST_VAR}")
    )
    os.environ.pop("UNSET_TEST_VAR", None)
    with pytest.raises(ConfigError, match="not set"):
        load_config(config_file)


def test_env_var_with_default(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        VALID_CONFIG.replace("password: postgres", "password: ${UNSET_VAR:-fallback}")
    )
    config = load_config(config_file)
    assert config.source.password == "fallback"


def test_invalid_port_rejected(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(VALID_CONFIG.replace("port: 5432", "port: 99999"))
    with pytest.raises(ConfigError, match="validation failed"):
        load_config(config_file)
