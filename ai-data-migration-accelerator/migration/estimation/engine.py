"""Deterministic effort estimation: Technical effort + Calendar planning.

Separates the calculation into two independent models:

1. TECHNICAL EFFORT MODEL
   - Calculates person-hours based on schema complexity
   - Agnostic to team size, working hours, productivity
   - Deterministic and reproducible

2. CALENDAR/RESOURCE MODEL
   - Converts person-hours to calendar duration
   - Accounts for team size, hours per day, productivity
   - Models phase dependencies and parallelization
   - Configurable through config.yaml or environment

This allows the same migration to have:
- Same technical person-hours (10 tables = 160 person-hours)
- Different calendar durations (3-person team → 2 weeks vs 1-person team → 5 weeks)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from migration.estimation.models import (
    ComplexityFactors,
    ComplexityLevel,
    EffortComponent,
    EstimationPackage,
    EstimationResult,
)
from migration.physical.models import ConstraintType, PhysicalModelPackage
from migration.models.config import SourceType, TargetType
from migration.canonical.models import MetadataPackage

logger = logging.getLogger(__name__)


# ============================================================================
# TECHNICAL EFFORT MODEL: Complexity → Person-Hours
# ============================================================================


@dataclass
class TechnicalEffortFactors:
    """Effort multipliers based on schema complexity, not team/calendar."""

    # Base effort per phase (person-hours)
    analysis_base_hours = 8.0
    modeling_base_hours = 6.0
    development_base_hours = 8.0
    testing_base_hours = 12.0
    deployment_base_hours = 4.0

    # Effort per unit of complexity (person-hours)
    hours_per_table = 2.0
    hours_per_column = 0.2
    hours_per_fk = 1.5
    hours_per_complex_relationship = 4.0
    hours_per_large_table = 8.0
    hours_per_unique_constraint = 0.5
    hours_per_check_constraint = 0.3
    hours_per_normalization_action = 1.0

    # Source-specific complexity (multiplier on all phases)
    source_multipliers = {
        SourceType.POSTGRES: 1.0,
        SourceType.ORACLE: 1.3,
        SourceType.SQLSERVER: 1.2,
        SourceType.MYSQL: 0.9,
        SourceType.SAP_HANA: 1.4,
        SourceType.SNOWFLAKE: 0.8,
        SourceType.DATABRICKS: 0.7,
        SourceType.BIGQUERY: 0.8,
        SourceType.REDSHIFT: 0.9,
        SourceType.DB2: 1.4,
    }

    # Target-specific complexity (multiplier on development/testing/deployment)
    target_multipliers = {
        TargetType.POSTGRES: 1.0,
        TargetType.SNOWFLAKE: 1.1,
        TargetType.DATABRICKS: 1.0,
        TargetType.BIGQUERY: 1.2,
        TargetType.REDSHIFT: 1.05,
    }


@dataclass
class TechnicalEffortResult:
    """Breakdown of technical effort in person-hours."""

    analysis_hours: float
    """Schema discovery, profiling, relationship analysis."""

    modeling_hours: float
    """Logical and physical model design."""

    development_hours: float
    """DDL generation, transformation logic, type mapping."""

    testing_hours: float
    """Functional, data, integration testing."""

    deployment_hours: float
    """Migration execution, cutover, validation."""

    total_person_hours: float
    """Sum of all phases."""

    complexity_level: ComplexityLevel
    """Overall complexity assessment."""


# ============================================================================
# CALENDAR/RESOURCE MODEL: Person-Hours → Calendar Duration
# ============================================================================


@dataclass
class TeamConfiguration:
    """Configurable team and resource assumptions."""

    hours_per_day: float = 8.0
    """Actual productive working hours per day (default 8, could be 6–10)."""

    team_size: int = 1
    """Number of people on the project (default 1)."""

    productivity_factor: float = 0.8
    """Time spent on actual work vs meetings/overhead (default 0.8 = 80%)."""

    phase_parallelization: dict[str, float] = None
    """Fraction of effort that can run in parallel with the previous phase.

    Example: {"modeling": 0.3} means 30% of modeling can overlap with analysis.
    Default: phases are sequential.
    """

    def __post_init__(self):
        if self.phase_parallelization is None:
            self.phase_parallelization = {
                "modeling": 0.0,  # Must wait for analysis
                "development": 0.1,  # Slight overlap with modeling
                "testing": 0.2,  # Testing can start before all dev is done
                "deployment": 0.0,  # Sequential after testing
            }


@dataclass
class CalendarEstimate:
    """Calendar duration and phase timing."""

    analysis_days: float
    modeling_days: float
    development_days: float
    testing_days: float
    deployment_days: float

    total_calendar_days: float
    """Wall-clock duration from start to finish (accounting for parallelization)."""

    total_calendar_weeks: float
    total_calendar_months: float


# ============================================================================
# EFFORT ESTIMATOR
# ============================================================================


class EffortEstimator:
    """Deterministic two-tier effort estimation.

    Tier 1: Technical effort (person-hours, team-independent)
    Tier 2: Calendar planning (wall-clock duration, team-dependent)
    """

    def __init__(
        self,
        package: PhysicalModelPackage,
        source_type: str,
        target_type: str,
        team_config: Optional[TeamConfiguration] = None,
        technical_factors: Optional[TechnicalEffortFactors] = None,
        canonical_metadata: Optional[MetadataPackage] = None,
    ):
        self.package = package
        self.model = package.physical_model
        self.source_type = source_type
        self.target_type = target_type
        self.team_config = team_config or TeamConfiguration()
        self.technical_factors = technical_factors or TechnicalEffortFactors()
        self.canonical_metadata = canonical_metadata

    def estimate(self) -> EstimationPackage:
        """Calculate technical effort and calendar duration."""
        factors = self._calculate_complexity_factors()
        complexity = self._classify_complexity(factors)

        # Tier 1: Technical effort in person-hours
        tech_result = self._estimate_technical_effort(factors, complexity)

        # Tier 2: Calendar duration based on team config
        calendar = self._estimate_calendar_duration(tech_result)

        # Store TECHNICAL EFFORT in person-days (team-independent)
        # Report calendar duration separately in descriptions
        analysis_person_days = tech_result.analysis_hours / 8.0
        modeling_person_days = tech_result.modeling_hours / 8.0
        development_person_days = tech_result.development_hours / 8.0
        testing_person_days = tech_result.testing_hours / 8.0
        deployment_person_days = tech_result.deployment_hours / 8.0
        total_person_days = tech_result.total_person_hours / 8.0

        result = EstimationResult(
            source_type=self.source_type,
            target_type=self.target_type,
            complexity_level=complexity,
            complexity_factors=factors,
            # Store TECHNICAL EFFORT in person-days (team-independent)
            total_effort_days=total_person_days,
            total_effort_weeks=total_person_days / 5.0,
            total_effort_months=total_person_days / 22.0,
            # Breakdown by phase in PERSON-DAYS
            discovery_effort_days=analysis_person_days,
            modeling_effort_days=modeling_person_days,
            ddl_effort_days=development_person_days,
            conversion_effort_days=development_person_days,
            testing_effort_days=testing_person_days,
            migration_effort_days=deployment_person_days,
            assumptions=self._generate_assumptions(factors, complexity),
            risks=self._identify_risks(factors, complexity),
            recommendations=self._generate_recommendations(factors, complexity),
            effort_components=[
                EffortComponent(
                    name="Analysis & Discovery",
                    effort_days=analysis_person_days,
                    description=(
                        f"Schema profiling, relationship discovery: {analysis_person_days:.1f} person-days; "
                        f"calendar duration: ~{calendar.analysis_days:.1f} days with {self.team_config.team_size} person(s)."
                    ),
                ),
                EffortComponent(
                    name="Modeling & Design",
                    effort_days=modeling_person_days,
                    description=(
                        f"Logical & physical model design: {modeling_person_days:.1f} person-days; "
                        f"calendar duration: ~{calendar.modeling_days:.1f} days with {self.team_config.team_size} person(s)."
                    ),
                ),
                EffortComponent(
                    name="Development & Conversion",
                    effort_days=development_person_days,
                    description=(
                        f"DDL generation, transformation logic, type mapping: {development_person_days:.1f} person-days; "
                        f"calendar duration: ~{calendar.development_days:.1f} days with {self.team_config.team_size} person(s)."
                    ),
                ),
                EffortComponent(
                    name="Testing & Validation",
                    effort_days=testing_person_days,
                    description=(
                        f"Functional, data, integration testing: {testing_person_days:.1f} person-days; "
                        f"calendar duration: ~{calendar.testing_days:.1f} days with {self.team_config.team_size} person(s)."
                    ),
                ),
                EffortComponent(
                    name="Deployment & Cutover",
                    effort_days=deployment_person_days,
                    description=(
                        f"Migration execution, cutover, validation: {deployment_person_days:.1f} person-days; "
                        f"calendar duration: ~{calendar.deployment_days:.1f} days with {self.team_config.team_size} person(s)."
                    ),
                ),
            ],
        )

        logger.info(
            "Effort estimated: %d person-hours (%.1f person-days) → "
            "~%.1f calendar days with %d person(s) at %d hrs/day, complexity: %s",
            int(tech_result.total_person_hours),
            tech_result.total_person_hours / 8.0,
            calendar.total_calendar_days,
            self.team_config.team_size,
            int(self.team_config.hours_per_day),
            complexity.value,
        )

        return EstimationPackage(
            estimation_result=result,
            generated_from="physical_model.json",
            generated_by="EffortEstimator",
        )

    def _calculate_complexity_factors(self) -> ComplexityFactors:
        """Calculate individual complexity drivers (same as before)."""
        tables = self.model.tables
        total_columns = sum(len(t.columns) for t in tables)

        pk_count = 0
        fk_count = 0
        unique_count = 0
        check_count = 0
        large_table_count = 0

        for table in tables:
            for constraint in table.constraints:
                if constraint.constraint_type == ConstraintType.PRIMARY_KEY:
                    pk_count += 1
                elif constraint.constraint_type == ConstraintType.FOREIGN_KEY:
                    fk_count += 1
                elif constraint.constraint_type == ConstraintType.UNIQUE:
                    unique_count += 1
                elif constraint.constraint_type == ConstraintType.CHECK:
                    check_count += 1

            if table.size_category.value in ("LARGE", "VERY_LARGE"):
                large_table_count += 1

        complex_rel_count = sum(
            1 for table in tables if len(table.name.lower().split("_")) >= 3
        ) // 2

        return ComplexityFactors(
            table_count=len(tables),
            total_columns=total_columns,
            primary_key_relationships=pk_count,
            foreign_key_relationships=fk_count,
            complex_relationships=complex_rel_count,
            unique_constraints=unique_count,
            check_constraints=check_count,
            large_tables=large_table_count,
            datatype_conversions=0,
            target_specific_complexity=5,
        )

    def _classify_complexity(self, factors: ComplexityFactors) -> ComplexityLevel:
        """Classify overall complexity (same formula as before)."""
        score = (
            factors.table_count * 2
            + factors.foreign_key_relationships * 3
            + factors.complex_relationships * 5
            + factors.large_tables * 10
        )

        if score < 10:
            return ComplexityLevel.LOW
        elif score < 50:
            return ComplexityLevel.MEDIUM
        elif score < 100:
            return ComplexityLevel.HIGH
        else:
            return ComplexityLevel.VERY_HIGH

    def _estimate_technical_effort(
        self, factors: ComplexityFactors, complexity: ComplexityLevel
    ) -> TechnicalEffortResult:
        """Tier 1: Calculate technical effort in person-hours."""
        f = self.technical_factors

        # Get source/target multipliers
        try:
            source_mult = f.source_multipliers.get(SourceType(self.source_type), 1.0)
        except (ValueError, KeyError):
            source_mult = 1.0

        try:
            target_mult = f.target_multipliers.get(TargetType(self.target_type), 1.0)
        except (ValueError, KeyError):
            target_mult = 1.0

        # Analysis: discover schema structure
        analysis = (
            f.analysis_base_hours
            + factors.table_count * f.hours_per_table
            + factors.total_columns * f.hours_per_column
            + factors.foreign_key_relationships * f.hours_per_fk * 0.2  # FK discovery
        ) * source_mult

        # Modeling: design logical and physical models
        modeling = (
            f.modeling_base_hours
            + factors.table_count * f.hours_per_table * 0.5
            + factors.foreign_key_relationships * f.hours_per_fk
            + factors.unique_constraints * f.hours_per_unique_constraint
        ) * source_mult

        # Development: generate DDL and transformation logic
        development = (
            f.development_base_hours
            + factors.table_count * f.hours_per_table * 0.3
            + factors.foreign_key_relationships * f.hours_per_fk * 0.3
            + factors.large_tables * f.hours_per_large_table
        ) * source_mult * target_mult

        # Testing: validate data, schema, business logic
        testing = (
            f.testing_base_hours
            + factors.table_count * f.hours_per_table * 0.4
            + factors.large_tables * f.hours_per_large_table * 0.5
            + factors.foreign_key_relationships * f.hours_per_fk * 0.1
        ) * source_mult

        # Deployment: cutover and validation
        deployment = (
            f.deployment_base_hours
            + factors.large_tables * f.hours_per_large_table * 0.5
        ) * source_mult * target_mult

        total = analysis + modeling + development + testing + deployment

        return TechnicalEffortResult(
            analysis_hours=analysis,
            modeling_hours=modeling,
            development_hours=development,
            testing_hours=testing,
            deployment_hours=deployment,
            total_person_hours=total,
            complexity_level=complexity,
        )

    def _estimate_calendar_duration(
        self, tech_result: TechnicalEffortResult
    ) -> CalendarEstimate:
        """Tier 2: Convert person-hours to calendar days based on team config."""
        cfg = self.team_config
        parallel = cfg.phase_parallelization or {}

        # Convert person-hours to calendar days per phase
        # person-hours → calendar_days = person_hours / (team_size × hours_per_day × productivity)
        effective_hours_per_day = cfg.team_size * cfg.hours_per_day * cfg.productivity_factor

        analysis_days = tech_result.analysis_hours / effective_hours_per_day
        modeling_days = tech_result.modeling_hours / effective_hours_per_day
        development_days = tech_result.development_hours / effective_hours_per_day
        testing_days = tech_result.testing_hours / effective_hours_per_day
        deployment_days = tech_result.deployment_hours / effective_hours_per_day

        # Calculate total calendar days accounting for parallelization
        # Total = analysis + max(overlap with modeling, modeling) + max(overlap with dev, dev) + ...
        calendar_days = analysis_days
        calendar_days += (1.0 - parallel.get("modeling", 0.0)) * modeling_days
        calendar_days += (1.0 - parallel.get("development", 0.0)) * development_days
        calendar_days += (1.0 - parallel.get("testing", 0.0)) * testing_days
        calendar_days += (1.0 - parallel.get("deployment", 0.0)) * deployment_days

        return CalendarEstimate(
            analysis_days=analysis_days,
            modeling_days=modeling_days,
            development_days=development_days,
            testing_days=testing_days,
            deployment_days=deployment_days,
            total_calendar_days=calendar_days,
            total_calendar_weeks=calendar_days / 5.0,
            total_calendar_months=calendar_days / 22.0,
        )

    def _generate_assumptions(
        self, factors: ComplexityFactors, _complexity: ComplexityLevel
    ) -> list[str]:
        """Generate assumptions underlying the estimate."""
        return [
            f"Schema contains {factors.table_count} tables with {factors.total_columns} total columns.",
            f"Found {factors.foreign_key_relationships} foreign key relationships.",
            f"{factors.large_tables} tables classified as large (>1M rows).",
            f"Team size: {self.team_config.team_size} person(s) at {self.team_config.hours_per_day} hours/day.",
            f"Productivity factor: {self.team_config.productivity_factor * 100:.0f}% (overhead accounted for).",
            "Assumes standard complexity migration with historical project data.",
        ]

    def _identify_risks(
        self, factors: ComplexityFactors, complexity: ComplexityLevel
    ) -> list[str]:
        """Identify risks impacting the estimate."""
        risks = []

        if factors.large_tables > 0:
            risks.append(
                f"Large tables ({factors.large_tables}) may require partitioning strategy."
            )

        if factors.complex_relationships > 0:
            risks.append(
                f"Complex relationships ({factors.complex_relationships}) may need custom logic."
            )

        if complexity in (ComplexityLevel.VERY_HIGH, ComplexityLevel.HIGH):
            risks.append("High complexity may increase discovery and testing effort.")

        if self.team_config.team_size == 1:
            risks.append("Single-person team may have coordination bottlenecks.")

        return risks

    def _generate_recommendations(
        self, factors: ComplexityFactors, _complexity: ComplexityLevel
    ) -> list[str]:
        """Generate recommendations to manage effort."""
        recommendations = []

        if factors.large_tables > 0:
            recommendations.append("Use partitioning/parallelization for large tables.")

        if factors.foreign_key_relationships > 10:
            recommendations.append("Consider referential integrity validation automation.")

        if self.team_config.team_size == 1:
            recommendations.append(
                "Consider adding 1-2 team members to reduce calendar duration from "
                f"{self.team_config.team_size} → {self.team_config.team_size + 2}."
            )

        return recommendations
