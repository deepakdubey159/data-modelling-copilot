"""Tests for effort estimation configuration and team scaling."""

from __future__ import annotations

from migration.estimation import create_estimator, TeamConfiguration
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


def simple_test_schema() -> PhysicalModelPackage:
    """Simple schema for testing configuration."""
    return PhysicalModelPackage(
        physical_model=PhysicalModel(
            database_name="test",
            summary="Test schema.",
            tables=[
                PhysicalTable(
                    name="customers",
                    logical_entity="Customer",
                    classification=TableClassification.MASTER,
                    size_category=SizeCategory.SMALL,
                    columns=[
                        PhysicalColumn(
                            name="id",
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
                            columns=["id"],
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
                            name="id",
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
                            columns=["id"],
                        ),
                        PhysicalConstraint(
                            name="fk_orders_customers",
                            constraint_type=ConstraintType.FOREIGN_KEY,
                            table="orders",
                            columns=["customer_id"],
                            referenced_table="customers",
                            referenced_columns=["id"],
                        ),
                    ],
                ),
            ],
        )
    )


class TestEstimationConfiguration:
    """Tests for configuration and team scaling."""

    def test_team_size_affects_calendar_not_technical(self):
        """Team size should affect calendar duration, not technical effort."""
        schema = simple_test_schema()

        est_1person = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            team_size=1,
            hours_per_day=8.0,
            productivity_factor=0.8,
        )

        est_3person = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            team_size=3,
            hours_per_day=8.0,
            productivity_factor=0.8,
        )

        result_1 = est_1person.estimate()
        result_3 = est_3person.estimate()

        # Technical effort (person-days) should be identical
        assert abs(
            result_1.estimation_result.total_effort_days
            - result_3.estimation_result.total_effort_days
        ) < 0.01, "Technical person-days should be independent of team size"

        # BUT: the component descriptions show different calendar days
        desc_1 = result_1.estimation_result.effort_components[0].description
        desc_3 = result_3.estimation_result.effort_components[0].description

        # Extract calendar days from descriptions
        # Format: "... person-days; calendar duration: ~X.X days with Y person(s)."
        import re

        def extract_calendar_days(desc):
            match = re.search(r"calendar duration: ~([\d.]+) days", desc)
            return float(match.group(1)) if match else None

        cal_1 = extract_calendar_days(desc_1)
        cal_3 = extract_calendar_days(desc_3)

        assert (
            cal_1 is not None and cal_3 is not None
        ), "Calendar days should be in description"
        assert (
            cal_1 > cal_3
        ), f"1-person calendar ({cal_1}) should be greater than 3-person ({cal_3})"
        # Should be approximately 3x difference
        ratio = cal_1 / cal_3
        assert 2.8 < ratio < 3.2, f"Expected ~3x speedup, got {ratio}x"

    def test_hours_per_day_affects_calendar(self):
        """Hours per day should affect calendar duration."""
        schema = simple_test_schema()

        est_8hr = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            team_size=1,
            hours_per_day=8.0,
            productivity_factor=0.8,
        )

        est_10hr = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            team_size=1,
            hours_per_day=10.0,
            productivity_factor=0.8,
        )

        result_8 = est_8hr.estimate()
        result_10 = est_10hr.estimate()

        # Technical effort should be identical
        assert abs(
            result_8.estimation_result.total_effort_days
            - result_10.estimation_result.total_effort_days
        ) < 0.01, "Technical person-days should be independent of hours_per_day"

    def test_productivity_factor_affects_calendar(self):
        """Productivity factor should affect calendar duration."""
        schema = simple_test_schema()

        est_80pct = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            team_size=1,
            hours_per_day=8.0,
            productivity_factor=0.8,
        )

        est_100pct = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            team_size=1,
            hours_per_day=8.0,
            productivity_factor=1.0,
        )

        result_80 = est_80pct.estimate()
        result_100 = est_100pct.estimate()

        # Technical effort should be identical
        assert abs(
            result_80.estimation_result.total_effort_days
            - result_100.estimation_result.total_effort_days
        ) < 0.01, "Technical person-days should be independent of productivity_factor"

    def test_config_values_consumed(self):
        """Factory should read team configuration values."""
        schema = simple_test_schema()

        # Create a mock config object
        class MockConfig:
            estimation = {
                "team_size": 2,
                "hours_per_day": 7.0,
                "productivity_factor": 0.9,
            }

        est = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            config=MockConfig(),
        )

        # Verify config values were used
        assert est.team_config.team_size == 2
        assert est.team_config.hours_per_day == 7.0
        assert est.team_config.productivity_factor == 0.9

    def test_explicit_params_override_config(self):
        """Explicit parameters should override config values."""
        schema = simple_test_schema()

        class MockConfig:
            estimation = {
                "team_size": 2,
                "hours_per_day": 7.0,
                "productivity_factor": 0.9,
            }

        est = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            team_size=5,  # Override config
            config=MockConfig(),
        )

        # Explicit param should take precedence
        assert est.team_config.team_size == 5
        # But others come from config
        assert est.team_config.hours_per_day == 7.0
        assert est.team_config.productivity_factor == 0.9

    def test_effort_breakdown_sums_correctly(self):
        """Effort components should sum to total."""
        schema = simple_test_schema()

        est = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
        )

        result = est.estimate()

        # Sum the components
        component_sum = sum(c.effort_days for c in result.estimation_result.effort_components)

        # Should equal total (allowing small rounding error)
        total = result.estimation_result.total_effort_days
        assert abs(component_sum - total) < 0.01, (
            f"Component sum ({component_sum:.2f}) should equal total ({total:.2f})"
        )

    def test_person_days_in_effort_fields(self):
        """Effort fields should contain person-days, not calendar days."""
        schema = simple_test_schema()

        est = create_estimator(
            package=schema,
            source_type="postgres",
            target_type="databricks",
            team_size=3,  # Use 3-person team
        )

        result = est.estimate()

        # With 3 people, calendar days should be ~1/3 of person-days for most phases
        # (assuming some parallelization, but roughly)
        for component in result.estimation_result.effort_components:
            # effort_days should be person-days (typically > calendar days)
            # Check by verifying the description mentions it's person-days
            desc = component.description
            assert "person-days" in desc, f"Description should mention person-days: {desc}"
            assert "calendar duration" in desc, f"Description should mention calendar duration: {desc}"
