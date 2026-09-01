"""Effort estimation module: two-tier estimation (technical + calendar).

Separates technical effort (person-hours, team-independent) from calendar
planning (wall-clock duration, team-configurable).

Main entry point: create_estimator() factory function.
"""

from migration.estimation.engine import EffortEstimator, TeamConfiguration
from migration.estimation.models import EstimationPackage

__all__ = ["create_estimator", "EffortEstimator", "TeamConfiguration", "EstimationPackage"]


def create_estimator(
    package,
    source_type: str,
    target_type: str,
    canonical_metadata=None,
    team_size: int = None,
    hours_per_day: float = None,
    productivity_factor: float = None,
    config=None,
):
    """Factory function to create an effort estimator.

    Args:
        package: PhysicalModelPackage
        source_type: Source database type (e.g., "postgres", "db2")
        target_type: Target platform (e.g., "databricks", "snowflake")
        canonical_metadata: Optional MetadataPackage for DB2-specific complexity
        team_size: Number of people on the project (overrides config)
        hours_per_day: Productive hours per day (overrides config)
        productivity_factor: Fraction of time on actual work (overrides config)
        config: Project configuration object with estimation settings

    Returns:
        EffortEstimator instance configured for production use.
    """
    # Read from config if available, otherwise use provided values or defaults
    if config and hasattr(config, "estimation"):
        est_cfg = config.estimation
        _team_size = team_size if team_size is not None else est_cfg.get("team_size", 1)
        _hours_per_day = hours_per_day if hours_per_day is not None else est_cfg.get("hours_per_day", 8.0)
        _productivity_factor = productivity_factor if productivity_factor is not None else est_cfg.get("productivity_factor", 0.8)
        phase_parallelization = est_cfg.get("phase_parallelization")
    else:
        _team_size = team_size if team_size is not None else 1
        _hours_per_day = hours_per_day if hours_per_day is not None else 8.0
        _productivity_factor = productivity_factor if productivity_factor is not None else 0.8
        phase_parallelization = None

    team_config = TeamConfiguration(
        team_size=_team_size,
        hours_per_day=_hours_per_day,
        productivity_factor=_productivity_factor,
        phase_parallelization=phase_parallelization,
    )

    return EffortEstimator(
        package=package,
        source_type=source_type,
        target_type=target_type,
        team_config=team_config,
        canonical_metadata=canonical_metadata,
    )
