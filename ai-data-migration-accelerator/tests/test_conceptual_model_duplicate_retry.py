"""Tests for conceptual model engine duplicate entity name retry behavior.

When the LLM returns duplicate entity names, the engine should retry once
with a focused correction prompt. This file tests that behavior.
"""

from __future__ import annotations

import json

import pytest

from migration.canonical.models import (
    ColumnMetadata,
    DatabaseMetadata,
    MetadataPackage,
    SchemaMetadata,
    TableMetadata,
)
from migration.conceptual.engine import ConceptualModelEngine
from migration.conceptual.parser import ConceptualModelParseError


class MockLLMClient:
    """Mock LLM client that returns predefined responses."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.call_count = 0
        self.prompts = []

    def complete(self, system_prompt: str, user_prompt: str, json_schema: dict | None = None) -> str:
        """Return the next response in the list."""
        self.prompts.append((system_prompt, user_prompt))
        if self.call_count >= len(self.responses):
            raise RuntimeError(f"MockLLMClient ran out of responses (expected {len(self.responses)})")
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


def _minimal_metadata() -> MetadataPackage:
    """Create minimal metadata for testing."""
    db = DatabaseMetadata(
        database_name="test_db",
        source_database_type="postgres",
        schemas=[
            SchemaMetadata(
                schema_name="public",
                tables=[
                    TableMetadata(
                        table_name="customer",
                        table_type="BASE TABLE",
                        columns=[
                            ColumnMetadata(
                                name="id",
                                data_type="INTEGER",
                                nullable=False,
                                ordinal_position=1,
                            ),
                            ColumnMetadata(
                                name="name",
                                data_type="VARCHAR",
                                nullable=False,
                                ordinal_position=2,
                            ),
                        ],
                    ),
                    TableMetadata(
                        table_name="product",
                        table_type="BASE TABLE",
                        columns=[
                            ColumnMetadata(
                                name="id",
                                data_type="INTEGER",
                                nullable=False,
                                ordinal_position=1,
                            ),
                            ColumnMetadata(
                                name="name",
                                data_type="VARCHAR",
                                nullable=False,
                                ordinal_position=2,
                            ),
                        ],
                    ),
                ],
            )
        ],
    )
    return MetadataPackage(metadata=db)


class TestConceptualModelDuplicateRetry:
    """Test retry behavior for duplicate entity names."""

    def test_no_retry_on_valid_response(self):
        """A valid response with no duplicates succeeds on first try."""
        valid_response = json.dumps(
            {
                "database_name": "test_db",
                "summary": "Test database",
                "domains": [
                    {"name": "Sales", "description": "Sales domain", "entities": ["Customer", "Product"]}
                ],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "A customer",
                        "business_key": ["id"],
                        "attributes": ["name"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    },
                    {
                        "name": "Product",
                        "description": "A product",
                        "business_key": ["id"],
                        "attributes": ["name"],
                        "source_tables": ["public.product"],
                        "relationships": [],
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        client = MockLLMClient([valid_response])
        engine = ConceptualModelEngine(client=client)
        metadata = _minimal_metadata()

        result = engine.generate(metadata)

        assert len(result.conceptual_model.entities) == 2
        assert {e.name for e in result.conceptual_model.entities} == {"Customer", "Product"}
        assert client.call_count == 1  # Only called once

    def test_retry_on_duplicate_entity_names(self):
        """When LLM returns duplicates, engine retries with correction prompt."""
        # First response has duplicate "Customer" entity
        duplicate_response = json.dumps(
            {
                "database_name": "test_db",
                "summary": "Test database",
                "domains": [
                    {"name": "Sales", "description": "Sales domain", "entities": ["Customer", "Product"]}
                ],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "A customer (first definition)",
                        "business_key": ["id"],
                        "attributes": ["name"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    },
                    {
                        "name": "Customer",  # Duplicate!
                        "description": "A customer (second definition)",
                        "business_key": ["id"],
                        "attributes": ["email"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    },
                    {
                        "name": "Product",
                        "description": "A product",
                        "business_key": ["id"],
                        "attributes": ["name"],
                        "source_tables": ["public.product"],
                        "relationships": [],
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        # Second response (after retry) has no duplicates
        corrected_response = json.dumps(
            {
                "database_name": "test_db",
                "summary": "Test database",
                "domains": [
                    {"name": "Sales", "description": "Sales domain", "entities": ["Customer", "Product"]}
                ],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "A customer",
                        "business_key": ["id"],
                        "attributes": ["name", "email"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    },
                    {
                        "name": "Product",
                        "description": "A product",
                        "business_key": ["id"],
                        "attributes": ["name"],
                        "source_tables": ["public.product"],
                        "relationships": [],
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        client = MockLLMClient([duplicate_response, corrected_response])
        engine = ConceptualModelEngine(client=client)
        metadata = _minimal_metadata()

        result = engine.generate(metadata)

        assert len(result.conceptual_model.entities) == 2
        assert {e.name for e in result.conceptual_model.entities} == {"Customer", "Product"}
        assert client.call_count == 2  # Called twice (initial + retry)

    def test_second_duplicate_error_fails_hard(self):
        """If the retry also has duplicates, the error is raised."""
        duplicate_response_1 = json.dumps(
            {
                "database_name": "test_db",
                "summary": "Test database",
                "domains": [
                    {"name": "Sales", "description": "Sales domain", "entities": ["Customer", "Product"]}
                ],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "Customer 1",
                        "business_key": ["id"],
                        "attributes": ["name"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    },
                    {
                        "name": "Customer",  # Duplicate!
                        "description": "Customer 2",
                        "business_key": ["id"],
                        "attributes": ["email"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        # Retry also has duplicates (different ones)
        duplicate_response_2 = json.dumps(
            {
                "database_name": "test_db",
                "summary": "Test database",
                "domains": [{"name": "Sales", "description": "Sales domain", "entities": ["Product", "Product"]}],
                "entities": [
                    {
                        "name": "Product",
                        "description": "Product 1",
                        "business_key": ["id"],
                        "attributes": ["name"],
                        "source_tables": ["public.product"],
                        "relationships": [],
                    },
                    {
                        "name": "Product",  # Still a duplicate!
                        "description": "Product 2",
                        "business_key": ["id"],
                        "attributes": ["price"],
                        "source_tables": ["public.product"],
                        "relationships": [],
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        client = MockLLMClient([duplicate_response_1, duplicate_response_2])
        engine = ConceptualModelEngine(client=client)
        metadata = _minimal_metadata()

        with pytest.raises(ConceptualModelParseError) as exc_info:
            engine.generate(metadata)

        assert "duplicate" in str(exc_info.value).lower()
        assert client.call_count == 2  # Still called twice (initial + retry)

    def test_correction_prompt_mentions_duplicates(self):
        """The correction prompt explicitly names the duplicate entities."""
        duplicate_response = json.dumps(
            {
                "database_name": "test_db",
                "summary": "Test database",
                "domains": [{"name": "Sales", "description": "Sales domain", "entities": ["Customer"]}],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "Customer 1",
                        "business_key": ["id"],
                        "attributes": ["name"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    },
                    {
                        "name": "Customer",  # Duplicate!
                        "description": "Customer 2",
                        "business_key": ["id"],
                        "attributes": ["email"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    },
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        corrected_response = json.dumps(
            {
                "database_name": "test_db",
                "summary": "Test database",
                "domains": [{"name": "Sales", "description": "Sales domain", "entities": ["Customer"]}],
                "entities": [
                    {
                        "name": "Customer",
                        "description": "A customer",
                        "business_key": ["id"],
                        "attributes": ["name", "email"],
                        "source_tables": ["public.customer"],
                        "relationships": [],
                    }
                ],
                "business_rules": [],
                "assumptions": [],
                "recommendations": [],
            }
        )

        client = MockLLMClient([duplicate_response, corrected_response])
        engine = ConceptualModelEngine(client=client)
        metadata = _minimal_metadata()

        result = engine.generate(metadata)

        # Check that the correction prompt was called
        assert client.call_count == 2
        system_prompt, user_prompt_1 = client.prompts[0]
        system_prompt, user_prompt_2 = client.prompts[1]

        # The second prompt (retry) should be a correction prompt mentioning duplicates
        assert "duplicate entity names" in user_prompt_2.lower() or "Customer" in user_prompt_2
        assert "consolidate" in user_prompt_2.lower()

    def test_duplicate_property_extracts_names(self):
        """The ConceptualModelParseError.duplicate_entity_names property works."""
        error = ConceptualModelParseError("Response defined duplicate entity names: Customer, Product")
        duplicates = error.duplicate_entity_names
        assert duplicates == ["Customer", "Product"]

    def test_duplicate_property_returns_none_for_non_duplicate_errors(self):
        """The duplicate_entity_names property returns None for other errors."""
        error = ConceptualModelParseError("Some other validation error")
        assert error.duplicate_entity_names is None
