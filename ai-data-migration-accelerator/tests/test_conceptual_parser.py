"""Tests for migration.conceptual.parser — the AI trust boundary."""

from __future__ import annotations

import json

import pytest

from migration.conceptual.models import ConceptualModel
from migration.conceptual.parser import (
    ConceptualModelParseError,
    parse_conceptual_model,
    parse_model,
    strip_code_fences,
)
from migration.relationship.models import Cardinality
from tests.conceptual_fixtures import response_with, valid_response_json


def test_parses_a_valid_response():
    model = parse_conceptual_model(valid_response_json())

    assert isinstance(model, ConceptualModel)
    assert model.database_name == "testdb"
    assert [e.name for e in model.entities] == ["Customer", "Order", "Product"]
    assert model.entities[0].relationships[0].cardinality == Cardinality.ONE_TO_MANY


def test_strips_json_code_fence():
    fenced = f"```json\n{valid_response_json()}\n```"

    assert parse_conceptual_model(fenced).database_name == "testdb"


def test_strips_bare_code_fence():
    assert strip_code_fences("```\n{}\n```") == "{}"


def test_leaves_unfenced_text_alone():
    assert strip_code_fences('  {"a": 1}  ') == '{"a": 1}'


def test_empty_response_is_rejected():
    with pytest.raises(ConceptualModelParseError, match="empty response"):
        parse_conceptual_model("   ")


def test_non_json_response_is_rejected():
    with pytest.raises(ConceptualModelParseError, match="not valid JSON"):
        parse_conceptual_model("Here is your conceptual model, I hope it helps!")


def test_json_array_at_top_level_is_rejected():
    with pytest.raises(ConceptualModelParseError, match="JSON object at the top level"):
        parse_conceptual_model("[1, 2, 3]")


def test_missing_required_field_is_rejected():
    payload = json.loads(valid_response_json())
    del payload["summary"]

    with pytest.raises(ConceptualModelParseError, match="did not match the required"):
        parse_conceptual_model(json.dumps(payload))


def test_invalid_cardinality_is_rejected():
    payload = json.loads(valid_response_json())
    payload["entities"][0]["relationships"][0]["cardinality"] = "SOMETIMES"

    with pytest.raises(ConceptualModelParseError, match="did not match the required"):
        parse_conceptual_model(json.dumps(payload))


def test_model_with_no_entities_is_rejected():
    with pytest.raises(ConceptualModelParseError, match="no entities"):
        parse_conceptual_model(response_with(entities=[], domains=[]))


def test_empty_summary_is_rejected():
    with pytest.raises(ConceptualModelParseError, match="empty summary"):
        parse_conceptual_model(response_with(summary="   "))


# -- Referential integrity -------------------------------------------------


def test_domain_referencing_unknown_entity_is_rejected():
    payload = json.loads(valid_response_json())
    payload["domains"][0]["entities"].append("Warehouse")

    with pytest.raises(ConceptualModelParseError, match="not defined in the model"):
        parse_conceptual_model(json.dumps(payload))


def test_domain_referencing_sales_employee_is_rejected():
    """Reproduces the reported failure: a domain lists an entity name that
    reads as plausible business vocabulary but was never defined in
    entities[]. This must fail loudly rather than be silently dropped or
    fuzzy-matched to an unrelated entity like 'Customer'."""
    payload = json.loads(valid_response_json())
    payload["domains"][0]["name"] = "Sales and Orders"
    payload["domains"][0]["entities"].append("Sales Employee")

    with pytest.raises(
        ConceptualModelParseError,
        match=r"Domain 'Sales and Orders' lists entity 'Sales Employee', which is not "
        r"defined in the model",
    ):
        parse_conceptual_model(json.dumps(payload))


def test_domain_with_valid_exact_entity_references_parses():
    """The positive counterpart: every domain entity name matches an
    entities[].name exactly across the whole model, so parsing succeeds and
    no name is altered."""
    payload = json.loads(valid_response_json())
    payload["domains"] = [
        {
            "name": "Sales and Orders",
            "description": "Customer demand and its fulfilment.",
            "entities": ["Customer", "Order"],
        },
        {
            "name": "Product Management",
            "description": "The catalogue of sellable goods.",
            "entities": ["Product"],
        },
    ]

    model = parse_conceptual_model(json.dumps(payload))

    assert model.domains[0].entities == ["Customer", "Order"]
    assert model.domains[1].entities == ["Product"]


def test_relationship_to_unknown_entity_is_rejected():
    payload = json.loads(valid_response_json())
    payload["entities"][0]["relationships"][0]["related_entity"] = "Shipment"

    with pytest.raises(ConceptualModelParseError, match="Shipment"):
        parse_conceptual_model(json.dumps(payload))


def test_case_mismatch_resolves_to_the_canonical_name():
    """A cosmetic slip must not fail the whole run."""
    payload = json.loads(valid_response_json())
    payload["entities"][0]["relationships"][0]["related_entity"] = "order"
    payload["domains"][0]["entities"] = ["customer", "ORDER"]

    model = parse_conceptual_model(json.dumps(payload))

    assert model.entities[0].relationships[0].related_entity == "Order"
    assert model.domains[0].entities == ["Customer", "Order"]


def test_whitespace_and_punctuation_variants_resolve():
    payload = json.loads(valid_response_json())
    payload["entities"][0]["relationships"][0]["related_entity"] = " Order "

    assert parse_conceptual_model(json.dumps(payload)).entities[0].relationships[
        0
    ].related_entity == "Order"


def test_duplicate_entity_names_are_rejected():
    payload = json.loads(valid_response_json())
    payload["entities"].append(dict(payload["entities"][0]))

    with pytest.raises(ConceptualModelParseError, match="duplicate entity names"):
        parse_conceptual_model(json.dumps(payload))


# -- Generic parser --------------------------------------------------------


def test_parse_model_is_generic_over_response_models():
    from pydantic import BaseModel

    class Tiny(BaseModel):
        value: int

    assert parse_model('{"value": 7}', Tiny).value == 7


def test_parse_model_reports_the_model_name_on_failure():
    from pydantic import BaseModel

    class Tiny(BaseModel):
        value: int

    with pytest.raises(ConceptualModelParseError, match="Tiny"):
        parse_model('{"value": "not-an-int"}', Tiny)
