"""Tests for migration.logical.engine.

The derivation is fully deterministic, so every test is an assertion over
in-memory models. No database, no AI, no fixtures on disk.
"""

from __future__ import annotations

import pytest

from migration.conceptual.models import (
    ConceptualDomain,
    ConceptualEntity,
    ConceptualModel,
    ConceptualModelPackage,
    ConceptualRelationship,
)
from migration.logical.engine import LogicalModelEngine, _infer_type
from migration.logical.models import (
    AttributeRole,
    EntityKind,
    LogicalDataType,
    NormalForm,
    Optionality,
)
from migration.relationship.models import Cardinality


def entity(
    name: str,
    *,
    business_key: list[str] | None = None,
    attributes: list[str] | None = None,
    relationships: list[ConceptualRelationship] | None = None,
    source_tables: list[str] | None = None,
) -> ConceptualEntity:
    return ConceptualEntity(
        name=name,
        description=f"The {name}.",
        business_key=business_key or [],
        attributes=attributes or [],
        relationships=relationships or [],
        source_tables=source_tables or [],
    )


def relationship(
    related: str,
    cardinality: Cardinality,
    *,
    verb: str = "relates to",
    optional: bool = False,
) -> ConceptualRelationship:
    return ConceptualRelationship(
        related_entity=related,
        verb_phrase=verb,
        cardinality=cardinality,
        is_optional=optional,
    )


def build(entities, domains=None, generated_by="stub") -> ConceptualModelPackage:
    return ConceptualModelPackage(
        conceptual_model=ConceptualModel(
            database_name="testdb",
            summary="A test model.",
            domains=domains or [],
            entities=entities,
        ),
        generated_by=generated_by,
    )


def derive(entities, domains=None):
    return LogicalModelEngine(build(entities, domains)).generate().logical_model


def find(model, name):
    return next(e for e in model.entities if e.name == name)


def attribute(entity_obj, name):
    return next(a for a in entity_obj.attributes if a.name == name)


# -- Entity derivation -----------------------------------------------------


def test_every_conceptual_entity_becomes_a_logical_entity():
    model = derive([entity("Customer"), entity("Product")])

    assert {e.name for e in model.entities} == {"Customer", "Product"}
    assert all(e.kind == EntityKind.FUNDAMENTAL for e in model.entities)


def test_business_key_becomes_the_primary_key():
    model = derive(
        [entity("Customer", business_key=["Customer Number"], attributes=["First Name"])]
    )
    customer = find(model, "Customer")

    assert customer.primary_key.attributes == ["Customer Number"]
    assert customer.primary_key.is_surrogate is False
    assert attribute(customer, "Customer Number").role == AttributeRole.PRIMARY_KEY
    assert attribute(customer, "Customer Number").optionality == Optionality.MANDATORY


def test_key_attributes_lead_the_attribute_list():
    """A reader expects the identifier first, not buried mid-list."""
    model = derive(
        [entity("Customer", business_key=["Customer Number"], attributes=["First Name", "Customer Number"])]
    )

    assert find(model, "Customer").attributes[0].name == "Customer Number"


def test_missing_business_key_introduces_a_surrogate():
    model = derive([entity("Event", attributes=["Description"])])
    event = find(model, "Event")

    assert event.primary_key.is_surrogate is True
    assert event.primary_key.attributes == ["Event Identifier"]
    assert attribute(event, "Event Identifier").data_type == LogicalDataType.IDENTIFIER


def test_surrogate_key_is_recorded_as_a_decision_not_hidden():
    model = derive([entity("Event")])

    actions = [a for a in model.normalization_actions if "surrogate" in a.action.lower()]
    assert len(actions) == 1
    assert actions[0].entity == "Event"
    assert any("surrogate" in note.lower() for note in model.assumptions)


def test_source_tables_are_carried_through_for_traceability():
    model = derive([entity("Customer", source_tables=["bronze.customer"])])

    assert find(model, "Customer").source_tables == ["bronze.customer"]


# -- Attribute typing ------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Email Address", LogicalDataType.EMAIL),
        ("Telephone Number", LogicalDataType.PHONE),
        ("Order Date", LogicalDataType.DATE),
        ("Performed At", LogicalDataType.TIMESTAMP),
        ("Discount Percentage", LogicalDataType.PERCENTAGE),
        ("Agreed Unit Price", LogicalDataType.AMOUNT),
        ("Credit Limit", LogicalDataType.AMOUNT),
        ("Quantity Ordered", LogicalDataType.WHOLE_NUMBER),
        ("Order Status", LogicalDataType.CODE),
        ("Stock Keeping Unit", LogicalDataType.CODE),
        ("Customer Number", LogicalDataType.IDENTIFIER),
        ("Product Name", LogicalDataType.TEXT),
    ],
)
def test_attribute_names_resolve_to_abstract_domains(name, expected):
    assert _infer_type(name) == expected


def test_typing_matches_whole_words_not_substrings():
    """'Account Status' contains 'count'; matching without word boundaries
    types it as a number instead of a code."""
    assert _infer_type("Account Status") == LogicalDataType.CODE
    assert _infer_type("Discount Percentage") == LogicalDataType.PERCENTAGE


def test_domains_carry_no_platform_specifics():
    """The whole point of a logical model: nothing vendor-shaped."""
    model = derive([entity("Customer", attributes=["Credit Limit"])])
    values = {a.data_type.value for e in model.entities for a in e.attributes}

    for value in values:
        assert "(" not in value
        assert "VARCHAR" not in value.upper()
        assert "DECIMAL(" not in value.upper()


# -- Alternate keys --------------------------------------------------------


def test_uniquely_identifying_attributes_become_alternate_keys():
    model = derive(
        [
            entity(
                "Customer",
                business_key=["Customer Number"],
                attributes=["Email Address", "First Name"],
            )
        ]
    )
    customer = find(model, "Customer")

    assert [k.attributes for k in customer.alternate_keys] == [["Email Address"]]
    assert attribute(customer, "Email Address").role == AttributeRole.ALTERNATE_KEY
    assert attribute(customer, "First Name").role == AttributeRole.DESCRIPTIVE


def test_primary_key_attributes_are_never_also_alternate_keys():
    model = derive([entity("Customer", business_key=["Customer Number"])])

    assert find(model, "Customer").alternate_keys == []


# -- Relationships and foreign keys ---------------------------------------


def test_one_to_many_propagates_a_foreign_key_to_the_child():
    model = derive(
        [
            entity(
                "Customer",
                business_key=["Customer Number"],
                relationships=[relationship("Sales Order", Cardinality.ONE_TO_MANY)],
            ),
            entity("Sales Order", business_key=["Order Number"]),
        ]
    )
    order = find(model, "Sales Order")
    fk = attribute(order, "Customer Number")

    assert fk.role == AttributeRole.FOREIGN_KEY
    assert fk.references_entity == "Customer"
    assert [r.parent_entity for r in model.relationships] == ["Customer"]


def test_many_to_one_orients_the_parent_correctly():
    """The 'one' side is always the parent, whichever way it was declared."""
    model = derive(
        [
            entity(
                "Sales Order",
                business_key=["Order Number"],
                relationships=[relationship("Customer", Cardinality.MANY_TO_ONE)],
            ),
            entity("Customer", business_key=["Customer Number"]),
        ]
    )

    assert model.relationships[0].parent_entity == "Customer"
    assert model.relationships[0].child_entity == "Sales Order"
    assert attribute(find(model, "Sales Order"), "Customer Number")


def test_optionality_is_carried_through():
    model = derive(
        [
            entity(
                "Customer",
                business_key=["Customer Number"],
                relationships=[
                    relationship("Sales Order", Cardinality.ONE_TO_MANY, optional=True)
                ],
            ),
            entity("Sales Order", business_key=["Order Number"]),
        ]
    )

    assert model.relationships[0].optionality == Optionality.OPTIONAL
    assert (
        attribute(find(model, "Sales Order"), "Customer Number").optionality
        == Optionality.OPTIONAL
    )


def test_one_to_one_adds_an_alternate_key_on_the_child():
    """A one-to-one constrains the child's foreign key to be unique."""
    model = derive(
        [
            entity(
                "Person",
                business_key=["Person Number"],
                relationships=[relationship("Passport", Cardinality.ONE_TO_ONE)],
            ),
            entity("Passport", business_key=["Passport Number"]),
        ]
    )
    passport = find(model, "Passport")

    assert any("Person Number" in k.attributes for k in passport.alternate_keys)


def test_reciprocal_relationships_produce_one_foreign_key():
    model = derive(
        [
            entity(
                "Customer",
                business_key=["Customer Number"],
                relationships=[relationship("Sales Order", Cardinality.ONE_TO_MANY)],
            ),
            entity(
                "Sales Order",
                business_key=["Order Number"],
                relationships=[relationship("Customer", Cardinality.MANY_TO_ONE)],
            ),
        ]
    )

    assert len(model.relationships) == 1
    assert len(find(model, "Sales Order").attributes) == 2  # key + one FK


def test_self_reference_is_named_distinctly():
    model = derive(
        [
            entity(
                "Employee",
                business_key=["Employee Number"],
                relationships=[
                    relationship("Employee", Cardinality.MANY_TO_ONE, verb="reports to")
                ],
            )
        ]
    )
    employee = find(model, "Employee")
    foreign = [a for a in employee.attributes if a.role == AttributeRole.FOREIGN_KEY]

    assert len(foreign) == 1
    assert foreign[0].name != "Employee Number"
    assert foreign[0].references_entity == "Employee"


def test_foreign_key_name_does_not_repeat_the_parent_name():
    """Customer's key is 'Customer Number', not 'Customer Customer Number'."""
    model = derive(
        [
            entity(
                "Customer",
                business_key=["Customer Number"],
                relationships=[relationship("Sales Order", Cardinality.ONE_TO_MANY)],
            ),
            entity("Sales Order", business_key=["Order Number"]),
        ]
    )

    assert attribute(find(model, "Sales Order"), "Customer Number")


def test_relationship_to_unknown_entity_is_skipped():
    model = derive(
        [
            entity(
                "Customer",
                business_key=["Customer Number"],
                relationships=[relationship("Nowhere", Cardinality.ONE_TO_MANY)],
            )
        ]
    )

    assert model.relationships == []


# -- Normalization: many-to-many resolution -------------------------------


def _many_to_many_model():
    return derive(
        [
            entity(
                "Product",
                business_key=["Stock Keeping Unit"],
                relationships=[
                    relationship("Promotion", Cardinality.MANY_TO_MANY, verb="is promoted by")
                ],
            ),
            entity("Promotion", business_key=["Promotion Name"]),
        ]
    )


def test_many_to_many_is_resolved_into_an_associative_entity():
    model = _many_to_many_model()
    associative = [e for e in model.entities if e.kind == EntityKind.ASSOCIATIVE]

    assert len(associative) == 1
    assert associative[0].name == "Product Promotion Association"
    assert associative[0].source_entities == ["Product", "Promotion"]


def test_associative_entity_is_keyed_on_both_parents():
    model = _many_to_many_model()
    associative = next(e for e in model.entities if e.kind == EntityKind.ASSOCIATIVE)

    # Each key is named after its parent's key, prefixed with the parent
    # only where the key name does not already carry it: Promotion's key is
    # 'Promotion Name' and needs no prefix, Product's 'Stock Keeping Unit'
    # does.
    assert set(associative.primary_key.attributes) == {
        "Product Stock Keeping Unit",
        "Promotion Name",
    }
    assert all(a.role == AttributeRole.PRIMARY_KEY for a in associative.attributes)
    assert {a.references_entity for a in associative.attributes} == {"Product", "Promotion"}


def test_many_to_many_becomes_two_identifying_relationships():
    model = _many_to_many_model()

    assert len(model.relationships) == 2
    assert all(r.is_identifying for r in model.relationships)
    assert all(r.cardinality == Cardinality.ONE_TO_MANY for r in model.relationships)
    assert {r.parent_entity for r in model.relationships} == {"Product", "Promotion"}


def test_many_to_many_resolution_is_recorded_as_first_normal_form():
    model = _many_to_many_model()
    actions = [a for a in model.normalization_actions if a.normal_form == NormalForm.FIRST]

    assert any("many-to-many" in a.action.lower() for a in actions)


def test_no_many_to_many_relationship_survives_into_the_logical_model():
    model = _many_to_many_model()

    assert all(r.cardinality != Cardinality.MANY_TO_MANY for r in model.relationships)


# -- Normalization: dependent entities ------------------------------------


def _dependent_model():
    return derive(
        [
            entity(
                "Sales Order",
                business_key=["Order Number"],
                relationships=[relationship("Order Line", Cardinality.ONE_TO_MANY)],
            ),
            entity(
                "Order Line",
                business_key=["Order Number", "Line Number"],
                attributes=["Quantity Ordered"],
            ),
        ]
    )


def test_entity_keyed_through_its_parent_is_dependent():
    model = _dependent_model()

    assert find(model, "Order Line").kind == EntityKind.DEPENDENT
    assert model.relationships[0].is_identifying is True


def test_dependent_key_attribute_points_at_the_parent():
    model = _dependent_model()
    shared = attribute(find(model, "Order Line"), "Order Number")

    assert shared.role == AttributeRole.PRIMARY_KEY
    assert shared.references_entity == "Sales Order"
    assert shared.optionality == Optionality.MANDATORY


def test_redundant_foreign_key_is_removed_from_a_dependent_child():
    """The parent's key already lives in the child's own key; a second
    propagated copy is the redundancy normalization exists to remove."""
    line = find(_dependent_model(), "Order Line")
    names = [a.name for a in line.attributes]

    assert names.count("Order Number") == 1
    assert not any(name.endswith(" 2") for name in names)


def test_dependency_is_recorded_as_second_normal_form():
    model = _dependent_model()
    actions = [a for a in model.normalization_actions if a.normal_form == NormalForm.SECOND]

    assert any("dependent" in a.action.lower() for a in actions)


def test_composite_key_entities_are_checked_for_partial_dependency():
    """A check that finds nothing is still recorded, so a compliant design
    is distinguishable from one that was never examined."""
    model = _dependent_model()
    checks = [
        a
        for a in model.normalization_actions
        if a.normal_form == NormalForm.SECOND and "Checked" in a.action
    ]

    assert checks
    assert "Quantity Ordered" in checks[0].rationale


def test_transitive_chains_are_recorded_as_third_normal_form():
    model = derive(
        [
            entity(
                "Country",
                business_key=["Country Code"],
                relationships=[relationship("State", Cardinality.ONE_TO_MANY)],
            ),
            entity(
                "State",
                business_key=["State Name"],
                relationships=[relationship("City", Cardinality.ONE_TO_MANY)],
            ),
            entity("City", business_key=["City Name"]),
        ]
    )
    actions = [a for a in model.normalization_actions if a.normal_form == NormalForm.THIRD]

    assert any(a.entity == "City" for a in actions)


# -- Subject areas and assembly -------------------------------------------


def test_subject_areas_come_from_conceptual_domains():
    model = derive(
        [entity("Customer", business_key=["Customer Number"]), entity("Product")],
        domains=[
            ConceptualDomain(name="Sales", description="Demand.", entities=["Customer"])
        ],
    )
    areas = {a.name: a.entities for a in model.subject_areas}

    assert areas["Sales"] == ["Customer"]
    assert find(model, "Customer").subject_area == "Sales"


def test_entities_in_no_domain_are_grouped_as_unassigned():
    model = derive(
        [entity("Orphan")],
        domains=[ConceptualDomain(name="Sales", description="d", entities=[])],
    )

    assert any(a.name == "Unassigned" and a.entities == ["Orphan"] for a in model.subject_areas)


def test_summary_reports_the_shape_of_the_design():
    model = _many_to_many_model()

    assert "testdb" in model.summary
    assert "associative" in model.summary


def test_output_is_deterministic():
    first = LogicalModelEngine(build([entity("A"), entity("B")])).generate()
    second = LogicalModelEngine(build([entity("B"), entity("A")])).generate()

    assert first.model_dump_json() == second.model_dump_json()


def test_package_records_its_provenance():
    package = LogicalModelEngine(
        build([entity("A")], generated_by="claude-opus-5")
    ).generate()

    assert package.generated_from == "business_model.json"
    assert package.generated_by == "claude-opus-5"


def test_empty_conceptual_model_produces_an_empty_logical_model():
    model = derive([])

    assert model.entities == []
    assert model.relationships == []
