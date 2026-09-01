"""Tests for EffortEstimator: two-tier effort estimation."""

from __future__ import annotations

import pytest

from migration.estimation.engine import (
    EffortEstimator,
    TechnicalEffortFactors,
    TeamConfiguration,
)
from migration.physical.models import (
    ConstraintType,
    PhysicalColumn,
    PhysicalConstraint,
    PhysicalDataType,
    PhysicalModel,
    PhysicalModelPackage,
    PhysicalTable,
    TableClassification,
    SizeCategory,
)


def small_schema() -> PhysicalModelPackage:
    """Simple 3-table schema with minimal complexity."""
    return PhysicalModelPackage(
        physical_model=PhysicalModel(
            database_name="test",
            summary="Small schema.",
            tables=[
                PhysicalTable(
                    name="customers",
                    logical_entity="Customer",
                    classification=TableClassification.MASTER,
                    size_category=SizeCategory.SMALL,
                    columns=[
                        PhysicalColumn(
                            name="customer_id",
                            data_type=PhysicalDataType.IDENTIFIER,
                            nullable=False,
                            is_primary_key=True,
                            ordinal_position=1,
                        ),
                        PhysicalColumn(
                            name="name",
                            data_type=PhysicalDataType.STRING,
                            length=100,
                            nullable=False,
                            ordinal_position=2,
                        ),
                    ],
                    constraints=[
                        PhysicalConstraint(
                            name="pk_customers",
                            constraint_type=ConstraintType.PRIMARY_KEY,
                            table="customers",
                            columns=["customer_id"],
                        ),
                    ],
                ),
                PhysicalTable(
                    name="orders",
                    logical_entity="Order",
                    classification=TableClassification.TRANSACTION,
                    size_category=SizeCategory.SMALL,
                    columns=[
                        PhysicalColumn(
                            name="order_id",
                            data_type=PhysicalDataType.IDENTIFIER,
                            nullable=False,
                            is_primary_key=True,
                            ordinal_position=1,
                        ),
                        PhysicalColumn(
                            name="customer_id",
                            data_type=PhysicalDataType.IDENTIFIER,
                            nullable=False,
                            is_foreign_key=True,
                            ordinal_position=2,
                        ),
                    ],
                    constraints=[
                        PhysicalConstraint(
                            name="pk_orders",
                            constraint_type=ConstraintType.PRIMARY_KEY,
                            table="orders",
                            columns=["order_id"],
                        ),
                        PhysicalConstraint(
                            name="fk_orders_customers",
                            constraint_type=ConstraintType.FOREIGN_KEY,
                            table="orders",
                            columns=["customer_id"],
                            referenced_table="customers",
                            referenced_columns=["customer_id"],
                        ),
                    ],
                ),
                PhysicalTable(
                    name="products",
                    logical_entity="Product",
                    classification=TableClassification.MASTER,
                    size_category=SizeCategory.SMALL,
                    columns=[
                        PhysicalColumn(
                            name="product_id",
                            data_type=PhysicalDataType.IDENTIFIER,
                            nullable=False,
                            is_primary_key=True,
                            ordinal_position=1,
                        ),
                        PhysicalColumn(
                            name="name",
                            data_type=PhysicalDataType.STRING,
                            nullable=False,
                            ordinal_position=2,
                        ),
                    ],
                    constraints=[
                        PhysicalConstraint(
                            name="pk_products",
                            constraint_type=ConstraintType.PRIMARY_KEY,
                            table="products",
                            columns=["product_id"],
                        ),
                    ],
                ),
            ],
        )
    )


def bronze_schema() -> PhysicalModelPackage:
    """Approximate bronze schema: 19 tables, 23 FKs."""
    tables = []

    for i in range(19):
        columns = [
            PhysicalColumn(
                name=f"id_{i}",
                data_type=PhysicalDataType.IDENTIFIER,
                nullable=False,
                is_primary_key=True,
                ordinal_position=1,
            ),
        ]

        for j in range(6):
            columns.append(
                PhysicalColumn(
                    name=f"col_{i}_{j}",
                    data_type=PhysicalDataType.STRING if j % 2 == 0 else PhysicalDataType.DECIMAL,
                    nullable=j % 3 != 0,
                    ordinal_position=j + 2,
                )
            )

        constraints = [
            PhysicalConstraint(
                name=f"pk_table_{i}",
                constraint_type=ConstraintType.PRIMARY_KEY,
                table=f"table_{i}",
                columns=[f"id_{i}"],
            ),
        ]

        # Create FK chain to get 18 FKs
        if i > 0 and i < 19:
            constraints.append(
                PhysicalConstraint(
                    name=f"fk_table_{i}",
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table=f"table_{i}",
                    columns=[f"id_{i}"],
                    referenced_table=f"table_{i-1}",
                    referenced_columns=[f"id_{i-1}"],
                )
            )

        if i % 3 == 0:
            constraints.append(
                PhysicalConstraint(
                    name=f"uk_table_{i}",
                    constraint_type=ConstraintType.UNIQUE,
                    table=f"table_{i}",
                    columns=[f"col_{i}_0"],
                )
            )

        size_cat = SizeCategory.LARGE if i % 6 == 0 else SizeCategory.MEDIUM
        table = PhysicalTable(
            name=f"table_{i}",
            logical_entity=f"Entity{i}",
            classification=TableClassification.TRANSACTION if i % 2 == 0 else TableClassification.LOOKUP,
            size_category=size_cat,
            columns=columns,
            constraints=constraints,
        )
        tables.append(table)

    return PhysicalModelPackage(
        physical_model=PhysicalModel(
            database_name="bronze",
            summary="Bronze schema: 19 tables, 23 FKs",
            tables=tables,
        )
    )


def complex_schema() -> PhysicalModelPackage:
    """Complex schema with 20 tables, multiple FKs, large tables."""
    tables = []

    for i in range(20):
        columns = [
            PhysicalColumn(
                name=f"id_{i}",
                data_type=PhysicalDataType.IDENTIFIER,
                nullable=False,
                is_primary_key=True,
                ordinal_position=1,
            ),
        ]

        for j in range(5 + (i % 3)):
            columns.append(
                PhysicalColumn(
                    name=f"col_{i}_{j}",
                    data_type=PhysicalDataType.STRING if j % 2 == 0 else PhysicalDataType.DECIMAL,
                    nullable=j % 3 != 0,
                    ordinal_position=j + 2,
                )
            )

        constraints = [
            PhysicalConstraint(
                name=f"pk_table_{i}",
                constraint_type=ConstraintType.PRIMARY_KEY,
                table=f"table_{i}",
                columns=[f"id_{i}"],
            ),
        ]

        if i > 0:
            constraints.append(
                PhysicalConstraint(
                    name=f"fk_table_{i}",
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table=f"table_{i}",
                    columns=[f"id_{i}"],
                    referenced_table=f"table_{i-1}",
                    referenced_columns=[f"id_{i-1}"],
                )
            )

        if i % 4 == 0:
            constraints.append(
                PhysicalConstraint(
                    name=f"uk_table_{i}",
                    constraint_type=ConstraintType.UNIQUE,
                    table=f"table_{i}",
                    columns=[f"col_{i}_0"],
                )
            )

        size_cat = SizeCategory.LARGE if i % 6 == 0 else SizeCategory.MEDIUM
        classification = (
            TableClassification.TRANSACTION if i % 2 == 0 else TableClassification.LOOKUP
        )

        table = PhysicalTable(
            name=f"table_{i}",
            logical_entity=f"Entity{i}",
            classification=classification,
            size_category=size_cat,
            columns=columns,
            constraints=constraints,
        )
        tables.append(table)

    return PhysicalModelPackage(
        physical_model=PhysicalModel(
            database_name="test_complex",
            summary="Complex schema with 20 tables",
            tables=tables,
        )
    )


class TestTechnicalEffortModel:
    """Test Tier 1: technical effort calculation (person-hours)."""

    def test_small_schema_minimal_effort(self):
        """Small 3-table schema should require minimal effort."""
        estimator = EffortEstimator(
            package=small_schema(),
            source_type="postgres",
            target_type="databricks",
        )

        result = estimator.estimate()
        model = result.estimation_result

        # Small schema: 3 tables, 5 columns, 1 FK
        # Total should be minimal (~7 calendar days for 1 person at 8 hrs/day, 80% productivity)
        assert model.total_effort_days < 10.0, "Small schema should require <10 calendar days for 1 person"

    def test_complex_schema_significant_effort(self):
        """Complex schema should require significant effort."""
        estimator = EffortEstimator(
            package=complex_schema(),
            source_type="postgres",
            target_type="databricks",
        )

        result = estimator.estimate()
        model = result.estimation_result

        # 20 tables, ~140 columns, 19 FKs
        # Should require more effort than small schema
        assert model.total_effort_days > 20.0, "Complex schema should require >20 person-days"

    def test_effort_breakdown_exists(self):
        """Effort components should be provided in the breakdown."""
        estimator = EffortEstimator(
            package=small_schema(),
            source_type="postgres",
            target_type="databricks",
        )

        result = estimator.estimate()
        components = result.estimation_result.effort_components

        # Should have 5 phases: Analysis, Modeling, Development, Testing, Deployment
        assert len(components) == 5, "Should have 5 effort components"

        # Each component should have positive effort
        for comp in components:
            assert comp.effort_days > 0, f"{comp.name} should have positive effort"
            assert comp.description, f"{comp.name} should have description"

    def test_source_complexity_affects_all_phases(self):
        """DB2 source should increase effort compared to Postgres."""
        postgres_est = EffortEstimator(
            package=small_schema(),
            source_type="postgres",
            target_type="databricks",
        )
        db2_est = EffortEstimator(
            package=small_schema(),
            source_type="db2",
            target_type="databricks",
        )

        postgres_effort = postgres_est.estimate().estimation_result.total_effort_days
        db2_effort = db2_est.estimate().estimation_result.total_effort_days

        assert db2_effort > postgres_effort * 1.3, (
            f"DB2 (1.4×) should significantly increase effort vs Postgres (1.0×)"
        )


class TestCalendarEstimationModel:
    """Test Tier 2: calendar duration based on team configuration."""

    def test_single_person_calendar_duration(self):
        """Single person working 8 hours/day."""
        team_1person = TeamConfiguration(
            hours_per_day=8.0,
            team_size=1,
            productivity_factor=0.8,
        )

        estimator = EffortEstimator(
            package=small_schema(),
            source_type="postgres",
            target_type="databricks",
            team_config=team_1person,
        )

        result = estimator.estimate()
        model = result.estimation_result

        # With 1 person at 8 hours/day and 80% productivity = 6.4 hours/day effective
        # Calendar days should be person-hours / 6.4
        person_hours = model.discovery_effort_days * 8  # Convert back to hours
        expected_calendar = person_hours / (8.0 * 1 * 0.8)

        assert model.discovery_effort_days > 0, "Discovery effort should be positive"

    def test_larger_team_reduces_calendar_duration(self):
        """Same effort, larger team → shorter calendar duration."""
        team_1person = TeamConfiguration(team_size=1, hours_per_day=8.0, productivity_factor=0.8)
        team_3person = TeamConfiguration(team_size=3, hours_per_day=8.0, productivity_factor=0.8)

        schema = small_schema()

        est_1 = EffortEstimator(schema, "postgres", "databricks", team_config=team_1person)
        est_3 = EffortEstimator(schema, "postgres", "databricks", team_config=team_3person)

        # Calendar duration should scale with team size
        result_1 = est_1.estimate()
        result_3 = est_3.estimate()

        # Extract calendar days from component descriptions (format: "~X.X days")
        import re
        def extract_calendar_days(desc):
            match = re.search(r"calendar duration: ~([\d.]+) days", desc)
            return float(match.group(1)) if match else None

        calendar_1 = extract_calendar_days(result_1.estimation_result.effort_components[0].description)
        calendar_3 = extract_calendar_days(result_3.estimation_result.effort_components[0].description)

        # 3-person team should have ~3× shorter calendar duration
        ratio = calendar_1 / calendar_3
        assert 2.5 < ratio < 3.5, (
            f"3-person team should be ~3× faster in calendar time, got ratio {ratio:.1f}"
        )

    def test_productivity_factor_scales_calendar(self):
        """Lower productivity → longer calendar duration."""
        team_high_prod = TeamConfiguration(
            team_size=1, hours_per_day=8.0, productivity_factor=1.0
        )
        team_low_prod = TeamConfiguration(
            team_size=1, hours_per_day=8.0, productivity_factor=0.6
        )

        schema = small_schema()
        est_high = EffortEstimator(schema, "postgres", "databricks", team_config=team_high_prod)
        est_low = EffortEstimator(schema, "postgres", "databricks", team_config=team_low_prod)

        result_high = est_high.estimate()
        result_low = est_low.estimate()

        # Extract calendar days from component descriptions
        import re
        def extract_calendar_days(desc):
            match = re.search(r"calendar duration: ~([\d.]+) days", desc)
            return float(match.group(1)) if match else None

        calendar_days_high = extract_calendar_days(result_high.estimation_result.effort_components[0].description)
        calendar_days_low = extract_calendar_days(result_low.estimation_result.effort_components[0].description)

        # Lower productivity (0.6) should have longer calendar duration than higher productivity (1.0)
        assert calendar_days_low > calendar_days_high * 1.3, (
            f"Lower productivity ({team_low_prod.productivity_factor}) should increase calendar duration, "
            f"got high={calendar_days_high:.1f}, low={calendar_days_low:.1f}"
        )

    def test_hours_per_day_affects_calendar_duration(self):
        """Working 6 hours/day vs 10 hours/day changes calendar days."""
        team_6hr = TeamConfiguration(team_size=1, hours_per_day=6.0, productivity_factor=0.8)
        team_10hr = TeamConfiguration(team_size=1, hours_per_day=10.0, productivity_factor=0.8)

        schema = small_schema()
        est_6 = EffortEstimator(schema, "postgres", "databricks", team_config=team_6hr)
        est_10 = EffortEstimator(schema, "postgres", "databricks", team_config=team_10hr)

        result_6 = est_6.estimate()
        result_10 = est_10.estimate()

        # Extract calendar days from component descriptions
        import re
        def extract_calendar_days(desc):
            match = re.search(r"calendar duration: ~([\d.]+) days", desc)
            return float(match.group(1)) if match else None

        calendar_6 = extract_calendar_days(result_6.estimation_result.effort_components[0].description)
        calendar_10 = extract_calendar_days(result_10.estimation_result.effort_components[0].description)

        # 10 hours/day should have fewer calendar days than 6 hours/day
        assert calendar_10 < calendar_6 * 0.7, (
            f"Working 10 hrs/day should reduce calendar duration vs 6 hrs/day, "
            f"got 6hr={calendar_6:.1f}, 10hr={calendar_10:.1f}"
        )


class TestBronzeSchemaValidation:
    """Validate new estimator against bronze schema (19 tables, 23 FKs)."""

    def test_bronze_schema_realistic_estimate(self):
        """Bronze schema should produce realistic estimate."""
        schema = bronze_schema()

        # Default team (1 person, 8 hours/day, 80% productivity)
        estimator = EffortEstimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
        )

        result = estimator.estimate()
        model = result.estimation_result

        # Previous model: 65 days (highly inflated)
        # New model: ~32 technical person-days → ~40 calendar days (1 person at 8 hrs/day, 80% prod)
        # Should be significantly lower and more realistic
        assert model.total_effort_days < 50, (
            f"Bronze estimate ({model.total_effort_days:.1f} calendar days) should be much lower "
            f"than the inflated 65 days from old model"
        )

    def test_bronze_schema_team_scaling(self):
        """Bronze schema with 3-person team should have shorter calendar."""
        schema = bronze_schema()

        team_1 = TeamConfiguration(team_size=1, hours_per_day=8.0, productivity_factor=0.8)
        team_3 = TeamConfiguration(team_size=3, hours_per_day=8.0, productivity_factor=0.8)

        est_1 = EffortEstimator(schema, "postgres", "databricks", team_config=team_1)
        est_3 = EffortEstimator(schema, "postgres", "databricks", team_config=team_3)

        result_1 = est_1.estimate()
        result_3 = est_3.estimate()

        # Extract calendar days from component descriptions
        import re
        def extract_calendar_days(desc):
            match = re.search(r"calendar duration: ~([\d.]+) days", desc)
            return float(match.group(1)) if match else None

        calendar_1 = extract_calendar_days(result_1.estimation_result.effort_components[0].description)
        calendar_3 = extract_calendar_days(result_3.estimation_result.effort_components[0].description)

        # 3 people should be roughly 3× faster
        expected_ratio = calendar_1 / calendar_3
        assert 2.5 < expected_ratio < 3.5, (
            f"3-person team should be ~3× faster in calendar time, got ratio {expected_ratio:.1f} "
            f"(1 person: {calendar_1:.1f} days, 3 people: {calendar_3:.1f} days)"
        )
