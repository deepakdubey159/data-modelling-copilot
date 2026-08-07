"""Shared fixtures for the conceptual model engine tests.

No API key, no network, no `anthropic` import. `StubLLMClient` returns a
canned response, which is the entire AI surface the engine depends on.
"""

from __future__ import annotations

import json

from migration.canonical.models import MetadataPackage
from migration.profiler.models import ProfilePackage
from migration.relationship.engine import RelationshipEngine
from migration.relationship.models import RelationshipPackage
from tests.relationship_fixtures import (
    column_profile,
    profile,
    sample_metadata,
    table_profile,
)


class StubLLMClient:
    """Records what it was asked and returns a canned response."""

    def __init__(self, response: str, model: str = "stub-model"):
        self.response = response
        self.model = model
        self.calls: list[tuple[str, str, dict | None]] = []

    def complete(
        self, system_prompt: str, user_prompt: str, json_schema: dict | None = None
    ) -> str:
        self.calls.append((system_prompt, user_prompt, json_schema))
        return self.response


class FailingLLMClient:
    """Raises, to prove failures surface rather than producing a partial artifact."""

    model = "failing-model"

    def complete(self, system_prompt, user_prompt, json_schema=None):
        raise RuntimeError("model unavailable")


VALID_RESPONSE: dict = {
    "database_name": "testdb",
    "summary": "A retail operation covering customers, orders and products.",
    "domains": [
        {
            "name": "Sales",
            "description": "Customer demand and its fulfilment.",
            "entities": ["Customer", "Order"],
        },
        {
            "name": "Product Management",
            "description": "The catalogue of sellable goods.",
            "entities": ["Product"],
        },
    ],
    "entities": [
        {
            "name": "Customer",
            "description": "A person or organisation that buys from the business.",
            "business_key": ["Customer Number"],
            "attributes": ["Customer Name", "City"],
            "source_tables": ["app.customer"],
            "relationships": [
                {
                    "related_entity": "Order",
                    "verb_phrase": "places",
                    "cardinality": "ONE_TO_MANY",
                    "is_optional": True,
                    "description": "A customer may place many orders.",
                }
            ],
        },
        {
            "name": "Order",
            "description": "A request from a customer for goods.",
            "business_key": ["Order Number"],
            "attributes": ["Order Date"],
            "source_tables": ["app.orders"],
            "relationships": [
                {
                    "related_entity": "Product",
                    "verb_phrase": "contains",
                    "cardinality": "MANY_TO_MANY",
                    "is_optional": False,
                    "description": "An order contains products.",
                }
            ],
        },
        {
            "name": "Product",
            "description": "A sellable item.",
            "business_key": ["Product Code"],
            "attributes": ["Product Name"],
            "source_tables": ["app.product"],
            "relationships": [],
        },
    ],
    "business_rules": ["Every order must belong to exactly one customer."],
    "assumptions": ["The 'orders' table was read as customer orders."],
    "recommendations": ["Confirm whether returns are modelled elsewhere."],
}


def valid_response_json() -> str:
    return json.dumps(VALID_RESPONSE)


def response_with(**overrides) -> str:
    payload = json.loads(json.dumps(VALID_RESPONSE))
    payload.update(overrides)
    return json.dumps(payload)


def sample_packages() -> tuple[MetadataPackage, ProfilePackage, RelationshipPackage]:
    """The three deterministic inputs, built from the relationship fixtures."""
    meta = sample_metadata()
    prof = profile(
        [
            table_profile(
                "customer",
                500,
                [
                    column_profile("customer_id", distinct_count=500),
                    column_profile("city_id", distinct_count=40),
                ],
            ),
            table_profile(
                "orders",
                4000,
                [
                    column_profile("order_id", distinct_count=4000),
                    column_profile("customer_id", distinct_count=480),
                ],
            ),
        ]
    )
    relationships = RelationshipEngine(meta, prof).discover()
    return (
        MetadataPackage(metadata=meta),
        ProfilePackage(profile=prof),
        relationships,
    )
