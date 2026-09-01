"""Regression test: 23 discovered relationships must survive conceptual model generation.

Verifies that:
1. RelationshipEngine discovers FK relationships
2. ConceptualModelEngine receives them in context
3. Prompt explicitly instructs LLM to map them to entity.relationships
4. Structured output schema enforces entity.relationships presence
5. Parsed conceptual model includes all source relationships
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from migration.canonical.models import MetadataPackage
from migration.conceptual.context_builder import ContextBuilder
from migration.conceptual.engine import ConceptualModelEngine
from migration.conceptual.prompt_builder import PromptBuilder, CONCEPTUAL_MODEL_PROMPT
from migration.logical.engine import LogicalModelEngine
from migration.metadata.builder import MetadataBuilder
from migration.profiler.engine import DataProfiler
from migration.relationship.engine import RelationshipEngine
from migration.relationship.models import Cardinality
from tests.conceptual_fixtures import StubLLMClient
from tests.relationship_fixtures import column, foreign_key, metadata as build_metadata, table
from tests.test_orchestrator_end_to_end import FakeConnector, _config


def _region_store_employee_metadata():
    """Region -> Store -> Employee: two FKs with different optionality.

    store.region_id is NOT NULL (mandatory); employee.store_id IS nullable
    (optional). Distinct optionality on each FK lets tests assert the
    correct value is threaded through independently, not a constant.
    """
    region = table(
        "region",
        [column("region_id", nullable=False, is_primary_key=True), column("name", "text")],
        primary_key=["region_id"],
    )
    store = table(
        "store",
        [
            column("store_id", nullable=False, is_primary_key=True),
            column("region_id", nullable=False),
        ],
        primary_key=["store_id"],
        foreign_keys=[foreign_key("store_region_fk", "region_id", "region", "region_id")],
    )
    employee = table(
        "employee",
        [
            column("employee_id", nullable=False, is_primary_key=True),
            column("store_id", nullable=True),
        ],
        primary_key=["employee_id"],
        foreign_keys=[foreign_key("employee_store_fk", "store_id", "store", "store_id")],
    )
    return build_metadata([region, store, employee])


def _conceptual_entities_payload(relationships_by_entity: dict[str, list[dict]] | None = None):
    relationships_by_entity = relationships_by_entity or {}
    return {
        "database_name": "test",
        "summary": "A retail operation with regions, stores and employees.",
        "domains": [
            {
                "name": "Operations",
                "description": "Regions, stores and staffing.",
                "entities": ["Region", "Store", "Employee"],
            }
        ],
        "entities": [
            {
                "name": "Region",
                "description": "A geographic area.",
                "business_key": ["region_id"],
                "attributes": ["region_id", "name"],
                "source_tables": ["app.region"],
                "relationships": relationships_by_entity.get("Region", []),
            },
            {
                "name": "Store",
                "description": "A retail location.",
                "business_key": ["store_id"],
                "attributes": ["store_id"],
                "source_tables": ["app.store"],
                "relationships": relationships_by_entity.get("Store", []),
            },
            {
                "name": "Employee",
                "description": "A person who works at a store.",
                "business_key": ["employee_id"],
                "attributes": ["employee_id"],
                "source_tables": ["app.employee"],
                "relationships": relationships_by_entity.get("Employee", []),
            },
        ],
        "business_rules": [],
        "assumptions": [],
        "recommendations": [],
    }


def test_prompt_explicitly_instructs_relationship_mapping():
    """The prompt must include explicit instruction to map FK relationships
    to entity.relationships so the LLM doesn't silently omit them."""
    prompt_template = CONCEPTUAL_MODEL_PROMPT

    instructions_text = " ".join(prompt_template.instructions)

    assert "relationships" in instructions_text.lower()
    assert "must" in instructions_text.lower() or "should" in instructions_text.lower()
    assert "entity" in instructions_text.lower()


def test_relationships_appear_in_business_context(tmp_path: Path):
    """RelationshipEngine discoveries must reach the BusinessContext passed to LLM."""
    config = _config(tmp_path)
    connector = FakeConnector()
    connector.connect()

    try:
        builder = MetadataBuilder(
            connector=connector, database_name="test", database_type="postgres"
        )
        metadata = builder.build(config.source.schema_)

        profiler = DataProfiler(connector=connector)
        profile = profiler.profile(metadata.metadata)

        engine = RelationshipEngine(
            metadata=metadata.metadata,
            profile=profile.profile if profile else None,
        )
        relationships_pkg = engine.discover()

        context_builder = ContextBuilder()
        context = context_builder.build(
            metadata.metadata,
            profile.profile if profile else None,
            relationships_pkg.relationships,
        )

        # Relationships MUST be in the context
        assert context.total_relationships > 0
        assert len(context.relationships) > 0
        # Relationship lines must be readable strings
        assert any("->" in rel for rel in context.relationships)
    finally:
        connector.disconnect()


def test_source_relationships_survive_conceptual_generation(tmp_path: Path, monkeypatch):
    """
    Complete data flow verification: source FKs survive conceptual generation.

    Trace:
    1. FakeConnector provides FK: app.customer -> app.orders
    2. RelationshipEngine discovers 1 relationship
    3. BusinessContext receives relationship line "app.customer -> app.orders [MANY_TO_ONE]"
    4. Prompt template includes explicit instruction to map relationships
    5. Conceptual model receives the instruction and relationship context
    6. Mocked LLM returns entity.relationships with Customer -> Order mapping
    7. Parser validates and persists the relationship
    8. Logical model sees the Customer -> Order relationship
    """
    config = _config(tmp_path)
    connector = FakeConnector()
    monkeypatch.setattr(
        "migration.orchestrator.orchestrator.create_connector", lambda source: connector
    )

    connector.connect()

    try:
        # Step 1-2: Extract metadata and discover relationships
        builder = MetadataBuilder(
            connector=connector, database_name="test", database_type="postgres"
        )
        metadata = builder.build(config.source.schema_)

        profiler = DataProfiler(connector=connector)
        profile = profiler.profile(metadata.metadata)

        engine = RelationshipEngine(
            metadata=metadata.metadata, profile=profile.profile if profile else None
        )
        relationships_pkg = engine.discover()

        # VERIFY Step 2: FakeConnector creates exactly 1 FK relationship
        assert (
            len(relationships_pkg.relationships.relationships) == 1
        ), "FakeConnector should create app.customer -> app.orders FK"
        fk_rel = relationships_pkg.relationships.relationships[0]
        assert (
            fk_rel.source_table == "orders"
            and fk_rel.target_table == "customer"
        ), "FK should be from orders (FK holder) to customer (PK target)"

        # Step 3: Verify relationships are in BusinessContext
        context_builder = ContextBuilder()
        business_context = context_builder.build(
            metadata.metadata,
            profile.profile if profile else None,
            relationships_pkg.relationships,
        )

        # VERIFY Step 3: Relationship lines are present in context
        assert business_context.total_relationships == 1
        assert len(business_context.relationships) == 1
        rel_line = business_context.relationships[0]
        assert "orders" in rel_line.lower()
        assert "customer" in rel_line.lower()
        assert "MANY_TO_ONE" in rel_line or "optional" in rel_line

        # Step 4: Verify prompt template includes mapping instruction
        prompt_template = CONCEPTUAL_MODEL_PROMPT
        instructions_text = " ".join(prompt_template.instructions)

        # VERIFY Step 4: Explicit mapping instruction is present
        assert (
            "relationships" in instructions_text.lower()
            and "MUST" in instructions_text.upper()
        ), "Prompt must explicitly require mapping FK relationships to entity.relationships"

        # Step 5-6: Generate conceptual model with mocked LLM response
        # This response maps the discovered FK to entity.relationships
        llm_response = json.dumps(
            {
                "database_name": "test",
                "summary": "Test database with customers and orders",
                "domains": [
                    {
                        "name": "Sales",
                        "description": "Customer and order management",
                        "entities": ["Customer", "Order"],
                    }
                ],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "A person who places orders",
                        "business_key": ["customer_id"],
                        "attributes": ["customer_id"],
                        "source_tables": ["app.customer"],
                        # VERIFY Step 6: LLM response includes entity.relationships
                        "relationships": [
                            {
                                "related_entity": "Order",
                                "verb_phrase": "places",
                                "cardinality": "ONE_TO_MANY",
                                "is_optional": False,
                                "description": "A customer places one or more orders",
                            }
                        ],
                    },
                    {
                        "name": "Order",
                        "description": "A purchase order",
                        "business_key": ["order_id"],
                        "attributes": ["order_id", "customer_id"],
                        "source_tables": ["app.orders"],
                        "relationships": [],
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        client = StubLLMClient(llm_response, model="claude-opus-5")

        conceptual_engine = ConceptualModelEngine(client=client)
        result = conceptual_engine.generate(metadata, profile, relationships_pkg)

        model = result.conceptual_model

        # Step 7-8: Verify parser and model contain the relationship
        # VERIFY Step 7-8: Parsed model has entities with correct relationship mapping
        assert len(model.entities) == 2, "Should have Customer and Order entities"

        customer = next(e for e in model.entities if e.name == "Customer")
        order = next(e for e in model.entities if e.name == "Order")

        # Most critical assertion: source FK survives to conceptual model
        assert (
            len(customer.relationships) > 0
        ), "Customer entity MUST have relationships (source FK was discovered)"
        assert (
            customer.relationships[0].related_entity == "Order"
        ), "Relationship target must be Order entity"
        assert (
            customer.relationships[0].cardinality.value == "ONE_TO_MANY"
        ), "Cardinality must match source FK"
        # Business semantics (verb_phrase) declared by the LLM are preserved...
        assert customer.relationships[0].verb_phrase == "places"
        # ...but technical optionality is corrected to match RelationshipPackage
        # (orders.customer_id is nullable in the fixture) even though the LLM
        # claimed is_optional=False. Reconciliation is the authority here, not the LLM.
        assert customer.relationships[0].is_optional == fk_rel.is_optional == True

    finally:
        connector.disconnect()


def test_reconciliation_restores_omitted_source_relationships(tmp_path: Path, monkeypatch):
    """
    Deterministic reconciliation: when LLM omits source FK relationships,
    they are restored from RelationshipPackage.

    Scenario:
    - Source has 1 FK: customer.customer_id → order.order_id
    - LLM returns 0 relationships (ignores the prompt instruction)
    - Reconciliation restores the FK with technical fields from source
    - Final model contains the relationship
    """
    config = _config(tmp_path)
    connector = FakeConnector()
    monkeypatch.setattr(
        "migration.orchestrator.orchestrator.create_connector", lambda source: connector
    )

    connector.connect()

    try:
        # Build metadata and discover relationships
        builder = MetadataBuilder(
            connector=connector, database_name="test", database_type="postgres"
        )
        metadata = builder.build(config.source.schema_)

        profiler = DataProfiler(connector=connector)
        profile = profiler.profile(metadata.metadata)

        engine = RelationshipEngine(
            metadata=metadata.metadata, profile=profile.profile if profile else None
        )
        relationships_pkg = engine.discover()

        # Verify we have source relationships
        assert len(relationships_pkg.relationships.relationships) > 0

        # LLM response that OMITS relationships (simulating failure to follow instruction)
        llm_response_with_no_rels = json.dumps(
            {
                "database_name": "test",
                "summary": "Test database with customers and orders",
                "domains": [
                    {
                        "name": "Sales",
                        "description": "Customer and order management",
                        "entities": ["Customer", "Order"],
                    }
                ],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "A person who places orders",
                        "business_key": ["customer_id"],
                        "attributes": ["customer_id"],
                        "source_tables": ["app.customer"],
                        "relationships": [],  # EMPTY - LLM omitted them
                    },
                    {
                        "name": "Order",
                        "description": "A purchase order",
                        "business_key": ["order_id"],
                        "attributes": ["order_id", "customer_id"],
                        "source_tables": ["app.orders"],
                        "relationships": [],  # EMPTY
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        client = StubLLMClient(llm_response_with_no_rels, model="claude-opus-5")

        conceptual_engine = ConceptualModelEngine(client=client)
        # Generate with relationships_pkg so reconciliation can restore them
        result = conceptual_engine.generate(metadata, profile, relationships_pkg)

        model = result.conceptual_model

        # CRITICAL: reconciliation restores the missing FK relationship
        assert len(model.entities) == 2
        customer = next(e for e in model.entities if e.name == "Customer")
        order = next(e for e in model.entities if e.name == "Order")

        # After reconciliation, the FK relationship is restored
        assert (
            len(customer.relationships) > 0
        ), "Reconciliation must restore FK relationship omitted by LLM"
        assert customer.relationships[0].related_entity == "Order"
        assert customer.relationships[0].cardinality.value == "ONE_TO_MANY"
        # orders.customer_id is nullable in the fixture, so the restored
        # relationship's optionality must match that (RelationshipPackage is
        # the authority, not a guess).
        fk_rel = relationships_pkg.relationships.relationships[0]
        assert customer.relationships[0].is_optional == fk_rel.is_optional == True

    finally:
        connector.disconnect()


def test_parser_rejects_response_omitting_source_relationships():
    """Parser must reject responses that omit relationships when source FKs exist.

    This prevents silent data loss when LLM doesn't map FK relationships.
    """
    from migration.conceptual.parser import parse_conceptual_model, ConceptualModelParseError

    # Response with 0 relationships but expected_relationship_count=1
    response_with_no_rels = json.dumps(
        {
            "database_name": "test",
            "summary": "Test database",
            "domains": [],
            "entities": [
                {
                    "name": "Customer",
                    "description": "A customer",
                    "business_key": ["id"],
                    "attributes": ["id"],
                    "source_tables": ["customers"],
                    "relationships": [],  # EMPTY even though FK exists
                },
                {
                    "name": "Order",
                    "description": "An order",
                    "business_key": ["id"],
                    "attributes": ["id"],
                    "source_tables": ["orders"],
                    "relationships": [],
                },
            ],
            "business_rules": [],
            "assumptions": [],
            "recommendations": [],
        }
    )

    # When expected_relationship_count > 0, empty relationships must be rejected
    with pytest.raises(ConceptualModelParseError) as exc_info:
        parse_conceptual_model(response_with_no_rels, expected_relationship_count=1)

    assert "omitted all source relationships" in str(exc_info.value).lower()
    assert "expected at least 1 relationship" in str(exc_info.value).lower()


def test_structured_output_schema_includes_relationships():
    """The JSON schema sent to the LLM must include entity.relationships
    so structured output validates that the response includes relationship data."""
    pb = PromptBuilder()
    schema = pb.response_json_schema(
        __import__("migration.conceptual.models", fromlist=["ConceptualModel"]).ConceptualModel
    )

    # Navigate to ConceptualEntity schema
    entity_schema = schema["$defs"]["ConceptualEntity"]
    assert "properties" in entity_schema
    assert (
        "relationships" in entity_schema["properties"]
    ), "ConceptualEntity schema must define relationships field"

    # relationships must be an array
    rel_schema = entity_schema["properties"]["relationships"]
    assert rel_schema.get("type") == "array"
    assert "items" in rel_schema

    # items must reference ConceptualRelationship
    assert "$ref" in rel_schema["items"]
    assert "ConceptualRelationship" in rel_schema["items"]["$ref"]


# -- Deterministic reconciliation: multi-FK, correction, and logical model ---


def test_llm_declared_relationship_is_kept_without_duplication():
    """Source has one FK and the LLM returns it correctly: reconciliation
    must not add a second, duplicate relationship."""
    meta = _region_store_employee_metadata()
    rels = RelationshipEngine(meta).discover()

    llm_response = json.dumps(
        _conceptual_entities_payload(
            {
                "Region": [
                    {
                        "related_entity": "Store",
                        "verb_phrase": "operates",
                        "cardinality": "ONE_TO_MANY",
                        "is_optional": False,
                        "description": "A region operates one or more stores.",
                    }
                ]
            }
        )
    )
    client = StubLLMClient(llm_response)
    engine = ConceptualModelEngine(client=client)
    model = engine.generate(MetadataPackage(metadata=meta), None, rels).conceptual_model

    region = next(e for e in model.entities if e.name == "Region")
    store = next(e for e in model.entities if e.name == "Store")

    all_region_store_rels = [
        r for r in region.relationships if r.related_entity == "Store"
    ] + [r for r in store.relationships if r.related_entity == "Region"]
    assert len(all_region_store_rels) == 1, "No duplicate should be created"
    assert all_region_store_rels[0].verb_phrase == "operates"


def test_multiple_omitted_relationships_are_all_restored():
    """Source has multiple FKs and the LLM omits all of them: every one
    must be restored, each mapped to the correct entity pair."""
    meta = _region_store_employee_metadata()
    rels = RelationshipEngine(meta).discover()
    assert len(rels.relationships.relationships) == 2

    llm_response = json.dumps(_conceptual_entities_payload())  # all empty
    client = StubLLMClient(llm_response)
    engine = ConceptualModelEngine(client=client)
    model = engine.generate(MetadataPackage(metadata=meta), None, rels).conceptual_model

    region = next(e for e in model.entities if e.name == "Region")
    store = next(e for e in model.entities if e.name == "Store")

    assert any(r.related_entity == "Store" for r in region.relationships), (
        "Region -> Store relationship must be restored"
    )
    assert any(r.related_entity == "Employee" for r in store.relationships), (
        "Store -> Employee relationship must be restored"
    )

    region_to_store = next(r for r in region.relationships if r.related_entity == "Store")
    store_to_employee = next(r for r in store.relationships if r.related_entity == "Employee")

    assert region_to_store.cardinality == Cardinality.ONE_TO_MANY
    assert region_to_store.is_optional is False  # store.region_id is NOT NULL

    assert store_to_employee.cardinality == Cardinality.ONE_TO_MANY
    assert store_to_employee.is_optional is True  # employee.store_id is nullable


def test_technical_properties_are_corrected_even_when_llm_declares_relationship():
    """When the LLM declares a relationship with wrong cardinality/optionality,
    reconciliation must overwrite the technical fields with the authoritative
    values from RelationshipPackage while preserving the LLM's business
    semantics (verb_phrase, description)."""
    meta = _region_store_employee_metadata()
    rels = RelationshipEngine(meta).discover()

    llm_response = json.dumps(
        _conceptual_entities_payload(
            {
                "Store": [
                    {
                        "related_entity": "Employee",
                        "verb_phrase": "staffs",
                        # Wrong on both counts: source metadata says
                        # ONE_TO_MANY / optional (employee.store_id nullable).
                        "cardinality": "MANY_TO_ONE",
                        "is_optional": False,
                        "description": "A store staffs its employees.",
                    }
                ],
                "Region": [
                    {
                        "related_entity": "Store",
                        "verb_phrase": "operates",
                        "cardinality": "ONE_TO_MANY",
                        "is_optional": False,
                        "description": "A region operates one or more stores.",
                    }
                ],
            }
        )
    )
    client = StubLLMClient(llm_response)
    engine = ConceptualModelEngine(client=client)
    model = engine.generate(MetadataPackage(metadata=meta), None, rels).conceptual_model

    store = next(e for e in model.entities if e.name == "Store")
    store_to_employee = next(r for r in store.relationships if r.related_entity == "Employee")

    # Business semantics preserved
    assert store_to_employee.verb_phrase == "staffs"
    assert store_to_employee.description == "A store staffs its employees."

    # Technical fields corrected to match RelationshipPackage
    assert store_to_employee.cardinality == Cardinality.ONE_TO_MANY
    assert store_to_employee.is_optional is True

    # No duplicate created for the pair that was already correct
    region = next(e for e in model.entities if e.name == "Region")
    all_region_store = [r for r in region.relationships if r.related_entity == "Store"] + [
        r for r in store.relationships if r.related_entity == "Region"
    ]
    assert len(all_region_store) == 1


def test_relationship_declared_from_fk_holder_side_is_not_duplicated():
    """The LLM may declare a relationship from the FK-holder's side (e.g.
    'Store belongs to Region', MANY_TO_ONE) rather than the referenced side.
    Reconciliation must recognise it either way and not add a duplicate."""
    meta = _region_store_employee_metadata()
    rels = RelationshipEngine(meta).discover()

    llm_response = json.dumps(
        _conceptual_entities_payload(
            {
                "Store": [
                    {
                        "related_entity": "Region",
                        "verb_phrase": "belongs to",
                        "cardinality": "MANY_TO_ONE",
                        "is_optional": False,
                        "description": "A store belongs to exactly one region.",
                    }
                ]
            }
        )
    )
    client = StubLLMClient(llm_response)
    engine = ConceptualModelEngine(client=client)
    model = engine.generate(MetadataPackage(metadata=meta), None, rels).conceptual_model

    region = next(e for e in model.entities if e.name == "Region")
    store = next(e for e in model.entities if e.name == "Store")

    all_region_store = [r for r in region.relationships if r.related_entity == "Store"] + [
        r for r in store.relationships if r.related_entity == "Region"
    ]
    assert len(all_region_store) == 1, "Declaring from the FK-holder's side must not duplicate"

    declared = all_region_store[0]
    assert declared.verb_phrase == "belongs to"
    assert declared.cardinality == Cardinality.MANY_TO_ONE
    assert declared.is_optional is False

    # Store -> Employee was omitted entirely and must still be restored.
    assert any(r.related_entity == "Employee" for r in store.relationships)


def test_logical_model_engine_receives_reconciled_relationships():
    """End-to-end: an FK omitted by the LLM survives reconciliation and
    reaches LogicalModelEngine as a real LogicalRelationship, with the
    child's foreign-key attribute carrying the correct optionality."""
    meta = _region_store_employee_metadata()
    rels = RelationshipEngine(meta).discover()

    llm_response = json.dumps(_conceptual_entities_payload())  # all omitted
    client = StubLLMClient(llm_response)
    engine = ConceptualModelEngine(client=client)
    package = engine.generate(MetadataPackage(metadata=meta), None, rels)

    logical = LogicalModelEngine(package).generate().logical_model

    assert len(logical.relationships) == 2

    store_employee = next(
        r
        for r in logical.relationships
        if {r.parent_entity, r.child_entity} == {"Store", "Employee"}
    )
    assert store_employee.parent_entity == "Store"
    assert store_employee.child_entity == "Employee"

    employee_entity = next(e for e in logical.entities if e.name == "Employee")
    fk_attribute = next(a for a in employee_entity.attributes if a.references_entity == "Store")
    # employee.store_id is nullable in the source metadata -> OPTIONAL on the child.
    from migration.logical.models import Optionality

    assert fk_attribute.optionality == Optionality.OPTIONAL


# -- Reproduction: LLM omits BOTH relationships and source_tables ------------
#
# The production failure this covers: the LLM followed the "name entities
# like the business would" instruction but left every entity's
# `source_tables` empty as well as `relationships`. Reconciliation's entity
# lookup was built exclusively from `source_tables`, so with it empty the
# lookup was empty too and every FK was silently skipped - the exact
# "entity.relationships arrays were all empty" failure raised by
# `_require_relationships` after reconciliation had already run.


def _entities_payload_without_source_tables(names: list[str]) -> list[dict]:
    """Entities with matching business names but no source_tables and no
    relationships - the shape a model produces when it omits both fields."""
    descriptions = {
        "Region": "A geographic area.",
        "Store": "A retail location.",
        "Employee": "A person who works at a store.",
    }
    keys = {
        "Region": ["region_id"],
        "Store": ["store_id"],
        "Employee": ["employee_id"],
    }
    return [
        {
            "name": name,
            "description": descriptions[name],
            "business_key": keys[name],
            "attributes": keys[name],
            "source_tables": [],
            "relationships": [],
        }
        for name in names
    ]


def test_reconciliation_restores_relationships_when_source_tables_is_empty():
    """Reproduces the production failure: the LLM leaves `source_tables`
    empty on every entity, in addition to omitting `relationships`.

    Reconciliation must still restore every source FK by falling back to
    matching each entity's business name against the known physical table
    names (Region <-> region, Store <-> store, Employee <-> employee),
    since those names are an unambiguous match here.
    """
    meta = _region_store_employee_metadata()
    rels = RelationshipEngine(meta).discover()
    assert len(rels.relationships.relationships) == 2

    llm_response = json.dumps(
        {
            "database_name": "test",
            "summary": "A retail operation with regions, stores and employees.",
            "domains": [
                {
                    "name": "Operations",
                    "description": "Regions, stores and staffing.",
                    "entities": ["Region", "Store", "Employee"],
                }
            ],
            "entities": _entities_payload_without_source_tables(
                ["Region", "Store", "Employee"]
            ),
            "business_rules": [],
            "assumptions": [],
            "recommendations": [],
        }
    )

    client = StubLLMClient(llm_response)
    engine = ConceptualModelEngine(client=client)
    model = engine.generate(MetadataPackage(metadata=meta), None, rels).conceptual_model

    region = next(e for e in model.entities if e.name == "Region")
    store = next(e for e in model.entities if e.name == "Store")

    assert any(
        r.related_entity == "Store" for r in region.relationships
    ), "Region -> Store must be restored even though source_tables was empty"
    assert any(
        r.related_entity == "Employee" for r in store.relationships
    ), "Store -> Employee must be restored even though source_tables was empty"

    region_to_store = next(r for r in region.relationships if r.related_entity == "Store")
    store_to_employee = next(r for r in store.relationships if r.related_entity == "Employee")
    assert region_to_store.cardinality == Cardinality.ONE_TO_MANY
    assert store_to_employee.cardinality == Cardinality.ONE_TO_MANY
    assert store_to_employee.is_optional is True  # employee.store_id is nullable


def test_full_pipeline_survives_empty_source_tables_and_relationships(tmp_path: Path, monkeypatch):
    """End-to-end reproduction against the real orchestrator inputs (metadata,
    profile, relationships built from a fake connector), mirroring exactly
    the reported failure: Claude returns entities with empty `relationships`
    and empty `source_tables`. The parser must NOT raise
    ConceptualModelParseError - reconciliation restores every relationship
    from the fallback name match before `_require_relationships` runs."""
    config = _config(tmp_path)
    connector = FakeConnector()
    connector.connect()

    try:
        builder = MetadataBuilder(connector=connector, database_name="test", database_type="postgres")
        metadata = builder.build(config.source.schema_)

        profiler = DataProfiler(connector=connector)
        profile = profiler.profile(metadata.metadata)

        engine = RelationshipEngine(
            metadata=metadata.metadata, profile=profile.profile if profile else None
        )
        relationships_pkg = engine.discover()
        assert len(relationships_pkg.relationships.relationships) > 0

        llm_response = json.dumps(
            {
                "database_name": "test",
                "summary": "Test database with customers and orders",
                "domains": [
                    {
                        "name": "Sales",
                        "description": "Customer and order management",
                        "entities": ["Customer", "Order"],
                    }
                ],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "A person who places orders",
                        "business_key": ["customer_id"],
                        "attributes": ["customer_id"],
                        "source_tables": [],
                        "relationships": [],
                    },
                    {
                        "name": "Order",
                        "description": "A purchase order",
                        "business_key": ["order_id"],
                        "attributes": ["order_id", "customer_id"],
                        "source_tables": [],
                        "relationships": [],
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        client = StubLLMClient(llm_response, model="claude-haiku-4-5-20251001")
        conceptual_engine = ConceptualModelEngine(client=client)

        # Must not raise ConceptualModelParseError.
        result = conceptual_engine.generate(metadata, profile, relationships_pkg)
        model = result.conceptual_model

        customer = next(e for e in model.entities if e.name == "Customer")
        assert len(customer.relationships) > 0, (
            "Reconciliation must restore the FK even with empty source_tables"
        )
        assert customer.relationships[0].related_entity == "Order"
    finally:
        connector.disconnect()


def test_fallback_name_match_does_not_guess_when_ambiguous():
    """When two entities normalize to the same table-name variant, the
    fallback must not guess - it leaves that table unmapped rather than
    risking an incorrect attribution. Source_tables (when present) always
    takes priority and is unaffected by this ambiguity guard."""
    from migration.conceptual.reconciler import _build_fallback_entity_lookup
    from migration.conceptual.models import ConceptualEntity, ConceptualModel

    model = ConceptualModel(
        database_name="test",
        summary="Two entities that coincidentally share a normalized name.",
        entities=[
            ConceptualEntity(name="Order", description="An order.", source_tables=[]),
            ConceptualEntity(name="Orders", description="Also an order.", source_tables=[]),
        ],
    )

    lookup = _build_fallback_entity_lookup(model, [("app", "orders")])

    assert "app.orders" not in lookup, "Ambiguous name match must not be resolved"


def test_source_tables_take_priority_over_fallback_name_match():
    """When an entity's declared source_tables already resolves a table,
    the name-based fallback must not override it - even if the fallback
    would have pointed to a different (wrong) entity."""
    meta = _region_store_employee_metadata()
    rels = RelationshipEngine(meta).discover()

    # "Branch" is deliberately not named like the "store" table, but its
    # source_tables correctly says otherwise - that must win.
    llm_response = json.dumps(
        {
            "database_name": "test",
            "summary": "A retail operation with regions, branches and employees.",
            "domains": [],
            "entities": [
                {
                    "name": "Region",
                    "description": "A geographic area.",
                    "business_key": ["region_id"],
                    "attributes": ["region_id"],
                    "source_tables": ["app.region"],
                    "relationships": [],
                },
                {
                    "name": "Branch",
                    "description": "A retail location, called Branch by the business.",
                    "business_key": ["store_id"],
                    "attributes": ["store_id"],
                    "source_tables": ["app.store"],
                    "relationships": [],
                },
                {
                    "name": "Employee",
                    "description": "A person who works at a branch.",
                    "business_key": ["employee_id"],
                    "attributes": ["employee_id"],
                    "source_tables": ["app.employee"],
                    "relationships": [],
                },
            ],
            "business_rules": [],
            "assumptions": [],
            "recommendations": [],
        }
    )

    client = StubLLMClient(llm_response)
    engine = ConceptualModelEngine(client=client)
    model = engine.generate(MetadataPackage(metadata=meta), None, rels).conceptual_model

    region = next(e for e in model.entities if e.name == "Region")
    assert any(
        r.related_entity == "Branch" for r in region.relationships
    ), "Region -> Store FK must resolve to Branch via source_tables, not be lost"
