"""Tests for migration.conceptual.engine and prompt_builder.

The real API is never called. `StubLLMClient` stands in for the entire AI
surface, which is one method.
"""

from __future__ import annotations

import json

import pytest

from migration.conceptual.engine import ConceptualModelEngine
from migration.conceptual.models import ConceptualModel, ConceptualModelPackage
from migration.conceptual.parser import ConceptualModelParseError
from migration.conceptual.prompt_builder import (
    CONCEPTUAL_MODEL_PROMPT,
    PromptBuilder,
    PromptTemplate,
)
from tests.conceptual_fixtures import (
    FailingLLMClient,
    StubLLMClient,
    sample_packages,
    valid_response_json,
)


def _engine(response: str = None, **kwargs) -> tuple[ConceptualModelEngine, StubLLMClient]:
    client = StubLLMClient(response or valid_response_json())
    return ConceptualModelEngine(client, **kwargs), client


# -- End-to-end ------------------------------------------------------------


def test_generates_a_validated_package():
    engine, _ = _engine()
    meta, prof, rels = sample_packages()

    package = engine.generate(meta, prof, rels)

    assert isinstance(package, ConceptualModelPackage)
    assert isinstance(package.conceptual_model, ConceptualModel)
    assert package.conceptual_model.database_name == "testdb"
    assert len(package.conceptual_model.entities) == 3


def test_records_the_model_that_produced_it():
    engine, _ = _engine()
    meta, prof, rels = sample_packages()

    assert engine.generate(meta, prof, rels).generated_by == "stub-model"


def test_explicit_model_name_overrides_the_client():
    engine, _ = _engine(model_name="claude-opus-5")
    meta, prof, rels = sample_packages()

    assert engine.generate(meta, prof, rels).generated_by == "claude-opus-5"


def test_generates_from_metadata_alone():
    """Profile and relationships are optional inputs."""
    engine, _ = _engine()
    meta, _, _ = sample_packages()

    package = engine.generate(meta)

    assert package.conceptual_model.entities


def test_malformed_response_raises_rather_than_writing_a_partial_model():
    engine, _ = _engine("this is not json")
    meta, prof, rels = sample_packages()

    with pytest.raises(ConceptualModelParseError):
        engine.generate(meta, prof, rels)


def test_client_failure_propagates():
    engine = ConceptualModelEngine(FailingLLMClient())
    meta, prof, rels = sample_packages()

    with pytest.raises(RuntimeError, match="model unavailable"):
        engine.generate(meta, prof, rels)


# -- What the engine sends -------------------------------------------------


def test_client_receives_system_prompt_user_prompt_and_schema():
    engine, client = _engine()
    meta, prof, rels = sample_packages()
    engine.generate(meta, prof, rels)

    assert len(client.calls) == 1
    system_prompt, user_prompt, schema = client.calls[0]

    assert "Senior Enterprise Data Architect" in system_prompt
    assert "testdb" in user_prompt
    assert schema["type"] == "object"
    assert "entities" in schema["properties"]


def test_system_prompt_is_identical_across_databases():
    """The stable half carries no context, so the prompt prefix stays
    cacheable from one run to the next."""
    engine, client = _engine()
    meta, prof, rels = sample_packages()

    engine.generate(meta, prof, rels)
    engine.generate(meta)

    assert client.calls[0][0] == client.calls[1][0]


def test_user_prompt_carries_the_business_context():
    engine, client = _engine()
    meta, prof, rels = sample_packages()
    engine.generate(meta, prof, rels)

    _, user_prompt, _ = client.calls[0]
    payload = json.loads(user_prompt.split("\n\n")[1])

    assert payload["database_name"] == "testdb"
    assert payload["tables"]


def test_build_context_does_not_call_the_model():
    """Callers can inspect and token-count the context before spending."""
    engine, client = _engine()
    meta, prof, rels = sample_packages()

    context = engine.build_context(meta, prof, rels)

    assert context.database_name == "testdb"
    assert client.calls == []


# -- Prompt builder --------------------------------------------------------


def test_system_prompt_contains_role_instructions_and_contract():
    prompt = PromptBuilder().build_system_prompt()

    assert "Senior Enterprise Data Architect" in prompt
    assert "How to approach this:" in prompt
    assert "Out of scope:" in prompt
    assert "Output format:" in prompt


def test_prompt_forbids_physical_modelling_concepts():
    prompt = PromptBuilder().build_system_prompt()

    assert "No SQL, DDL, data types" in prompt


def test_prompt_asks_for_json_only():
    prompt = PromptBuilder().build_system_prompt()

    assert "Return a single JSON object and nothing else" in prompt
    assert "markdown" in prompt.lower()


def test_prompt_never_asks_for_markdown_or_mermaid():
    """Both are generated deterministically in the writer. Asking the model
    for them would spend tokens on layout and allow the diagram to disagree
    with the model."""
    prompt = PromptBuilder().build_system_prompt().lower()

    assert "mermaid" not in prompt
    assert "diagram" not in prompt


def test_prompt_avoids_dated_emphatic_scaffolding():
    """Current models follow instructions closely; shouting causes
    over-triggering and rigid output."""
    prompt = PromptBuilder().build_system_prompt()

    assert "CRITICAL" not in prompt
    assert "YOU MUST" not in prompt
    assert "think step by step" not in prompt.lower()


def test_template_is_swappable_for_future_engines():
    """Only the template and the response model change per engine."""
    template = PromptTemplate(
        role="You are a Business Glossary Curator.",
        objective="Produce glossary terms.",
        instructions=["Define each term in one sentence."],
        output_contract='{"terms": []}',
    )
    prompt = PromptBuilder(template).build_system_prompt()

    assert "Business Glossary Curator" in prompt
    assert "Senior Enterprise Data Architect" not in prompt


def test_response_schema_is_derived_from_the_pydantic_model():
    schema = PromptBuilder.response_json_schema(ConceptualModel)

    assert schema["type"] == "object"
    assert {"database_name", "summary", "entities"} <= set(schema["properties"])
    assert json.dumps(schema)  # JSON-serializable for the API


def test_conceptual_template_is_the_default():
    assert PromptBuilder().template is CONCEPTUAL_MODEL_PROMPT


# -- Structured-output schema contract -------------------------------------


def _walk(node, visit, path="root"):
    if isinstance(node, dict):
        visit(node, path)
        for key, value in node.items():
            _walk(value, visit, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk(value, visit, f"{path}[{index}]")


def test_every_object_declares_additional_properties_false():
    """Structured outputs require it on every object; Pydantic does not emit
    it, and without it the API rejects the schema outright."""
    schema = PromptBuilder.response_json_schema(ConceptualModel)
    offenders: list[str] = []

    def check(node, path):
        if node.get("type") == "object" or "properties" in node:
            if node.get("additionalProperties") is not False:
                offenders.append(path)

    _walk(schema, check)
    assert offenders == []


def test_unsupported_validation_keywords_are_stripped():
    """Numeric and string constraints are not accepted by structured
    outputs. They are still enforced by the parser on the way back."""
    schema = json.dumps(PromptBuilder.response_json_schema(ConceptualModel))

    for keyword in ("minimum", "maximum", "minLength", "maxLength", "pattern", "multipleOf"):
        assert f'"{keyword}"' not in schema


def test_nested_definitions_are_hardened_too():
    schema = PromptBuilder.response_json_schema(ConceptualModel)

    entity = schema["$defs"]["ConceptualEntity"]
    assert entity["additionalProperties"] is False
    assert "name" in entity["properties"]
