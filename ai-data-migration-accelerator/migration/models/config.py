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


class LLMEffort(str, Enum):
    """How much reasoning effort the model should spend.

    Replaces `temperature` as the tuning dial for current Claude models.
    Higher effort means deeper reasoning at higher token cost.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


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

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    """DEPRECATED - accepted for backward compatibility, never sent.

    Sampling parameters (`temperature`, `top_p`, `top_k`) were removed from
    current Claude models: a request carrying one is rejected with a 400.
    The field is kept so existing config files keep loading, but the client
    does not forward it. Use `effort` instead — that is the supported dial
    for controlling how the model reasons. A config that sets this logs a
    warning at startup.
    """

    max_tokens: int = Field(default=32000, gt=0)
    """Hard ceiling on the response, covering reasoning and answer together.
    Generous by default because a conceptual model for a large schema is a
    long structured document and a truncated one is worthless."""

    effort: LLMEffort = LLMEffort.HIGH
    """Reasoning depth. `high` suits interpretive work like conceptual
    modelling; drop to `medium` or `low` to cut cost on simpler engines."""

    api_key_env: str = Field(default="ANTHROPIC_API_KEY", min_length=1)
    """Name of the environment variable holding the API key. The key itself
    is never read from config.yaml — that file is not git-ignored, and a key
    committed to it is a key leaked."""


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
