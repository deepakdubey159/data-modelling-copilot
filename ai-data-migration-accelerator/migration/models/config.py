"""
Configuration models for the AI Data Migration Accelerator.

These Pydantic models define the canonical, validated shape of `config.yaml`.
Nothing downstream should read raw YAML/dict data directly — everything flows
through these typed models so that invalid configuration fails fast, at
startup, with a clear error message rather than deep inside a connector.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    """Supported source database types.

    Only POSTGRES is implemented in Milestone 1. The enum exists up front so
    that config validation for future connectors (Oracle, SQL Server, etc.)
    is a one-line addition, not a redesign.
    """

    POSTGRES = "postgres"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    MYSQL = "mysql"
    SAP_HANA = "sap_hana"
    SNOWFLAKE = "snowflake"
    DATABRICKS = "databricks"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"


class TargetType(str, Enum):
    """Supported migration target platforms."""

    SNOWFLAKE = "snowflake"
    DATABRICKS = "databricks"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    POSTGRES = "postgres"


class LLMProvider(str, Enum):
    """Supported LLM providers for the AI layer (Milestone 4+)."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ProjectConfig(BaseModel):
    """Top-level project metadata and output location."""

    name: str = Field(..., min_length=1, description="Human-readable project name")
    output_directory: Path = Field(default=Path("output/"))

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("project.name must not be blank")
        return v


class SourceConfig(BaseModel):
    """Source database connection details."""

    type: SourceType
    host: str = Field(..., min_length=1)
    port: int = Field(..., gt=0, lt=65536)
    database: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(default="")
    schema_: list[str] = Field(default_factory=list, alias="schema")

    model_config = {"populate_by_name": True}

    @field_validator("schema_")
    @classmethod
    def at_least_one_schema(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("source.schema must contain at least one schema name")
        return v


class TargetConfig(BaseModel):
    """Migration target platform details."""

    type: TargetType


class LLMConfig(BaseModel):
    """LLM provider configuration for the AI layer."""

    provider: LLMProvider
    model: str = Field(..., min_length=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class ArtifactsConfig(BaseModel):
    """Toggles for which output artifacts to generate."""
    profile: bool = True
    relationships: bool = True
    conceptual_model: bool = True
    logical_model: bool = True
    physical_model: bool = True
    ddl: bool = True
    dml: bool = True
    report: bool = True
    estimation: bool = True


class LoggingConfig(BaseModel):
    level: LogLevel = LogLevel.INFO


class AppConfig(BaseModel):
    """Root configuration object — the fully validated `config.yaml`."""

    project: ProjectConfig
    source: SourceConfig
    target: TargetConfig
    llm: LLMConfig
    artifacts: ArtifactsConfig = Field(default_factory=ArtifactsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
