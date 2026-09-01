"""
Tests for TargetConfig's Databricks connection fields.

Connection fields (host_env/token_env/http_path_env/catalog) are optional at
config-parse time — DDL generation needs none of them. They only become
required when live execution is requested, which is validated by
DatabricksExecutor (see test_databricks_executor.py), not here.
"""

from __future__ import annotations

from migration.models.config import TargetConfig, TargetType


def test_target_config_defaults_env_var_names():
    target = TargetConfig(type=TargetType.DATABRICKS)

    assert target.host_env == "DATABRICKS_HOST"
    assert target.token_env == "DATABRICKS_TOKEN"
    assert target.http_path_env == "DATABRICKS_HTTP_PATH"
    assert target.catalog is None


def test_target_config_accepts_custom_env_var_names():
    target = TargetConfig(
        type=TargetType.DATABRICKS,
        host_env="MY_DBX_HOST",
        token_env="MY_DBX_TOKEN",
        http_path_env="MY_DBX_PATH",
        catalog="prod_catalog",
    )

    assert target.host_env == "MY_DBX_HOST"
    assert target.catalog == "prod_catalog"


def test_target_config_without_databricks_fields_still_parses():
    """A non-Databricks target (or DDL-generation-only usage) needs none of
    these fields set explicitly."""
    target = TargetConfig(type=TargetType.SNOWFLAKE)

    assert target.type == TargetType.SNOWFLAKE
    assert target.host_env == "DATABRICKS_HOST"  # harmless default, unused
