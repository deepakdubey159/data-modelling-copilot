"""
Prompt Builder

A reusable prompt template plus the conceptual-model instance of it.

Future AI-assisted engines (glossary, catalog, logical model, migration
assessment) reuse `PromptTemplate` and `PromptBuilder` unchanged and supply
their own `PromptTemplate` constant. Only the template and the response
model differ per engine — the assembly, the context serialization and the
output contract mechanics are shared.

Prompt style
------------
Written for current-generation models, which follow instructions closely and
literally. That means: no `CRITICAL:`/`MUST`/`NEVER` shouting, no
step-by-step choreography for what is a judgment task, and no
"think step by step" — thinking is a request parameter, not prose. Emphatic
scaffolding written for older models causes over-triggering and rigid output
on current ones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from migration.conceptual.context_builder import ContextBuilder
from migration.conceptual.models import BusinessContext


@dataclass(frozen=True)
class PromptTemplate:
    """A reusable prompt shape. One constant per AI-assisted engine."""

    role: str
    """Who the model should be while answering."""

    objective: str
    """What to produce, in one paragraph."""

    instructions: list[str] = field(default_factory=list)
    """What to do. Positive statements of intent."""

    exclusions: list[str] = field(default_factory=list)
    """What is explicitly out of scope. Kept short — a long prohibition list
    reads as anxiety and can anchor the model toward the very things it
    enumerates."""

    output_contract: str = ""
    """Description of the required JSON shape."""


CONCEPTUAL_MODEL_PROMPT = PromptTemplate(
    role=(
        "You are a Senior Enterprise Data Architect. You have been handed the "
        "structural analysis of a database you have never seen before and asked "
        "to explain what business it supports."
    ),
    objective=(
        "Infer the conceptual data model: the business domains, the business "
        "entities, how those entities relate in business terms, and the rules the "
        "structure implies. Work at the level a business stakeholder would "
        "recognise, not the level a DBA would."
    ),
    instructions=[
        "Name entities as the business would name them, not as the tables are named. "
        "A table called 'cust_mstr' is a Customer.",
        "Group entities into business domains. A domain is a subject area a team "
        "could own, such as Sales, Fulfilment or Human Resources.",
        "Describe each relationship with a verb phrase that reads as a sentence: "
        "'a Customer places Orders', 'an Employee reports to a Manager'.",
        "A pure link table is usually not a business entity - it expresses a "
        "many-to-many relationship between two entities that are. A link table that "
        "carries its own attributes usually IS an entity in its own right.",
        "Give each entity a business key: how a person in the business identifies "
        "one in the real world. This is often not the physical primary key.",
        "State the business rules the structure and value distributions imply. A "
        "mandatory reference implies a rule; a small set of repeated values implies "
        "a controlled vocabulary.",
        "Record every interpretation you made as an assumption. If a name is "
        "ambiguous, say which reading you chose and why.",
        "Where the analysis marks a relationship as inferred rather than declared, "
        "treat it as a hypothesis and note it in assumptions if you rely on it.",
        "If part of the schema was omitted from the context, say so in assumptions "
        "rather than inferring what it might have contained.",
    ],
    exclusions=[
        "No SQL, DDL, data types, lengths, indexes, or constraint syntax.",
        "No table or column names as entity or attribute names - translate them.",
        "No implementation or migration advice; recommendations should be about the "
        "business model, such as missing entities or unclear ownership.",
    ],
    output_contract=(
        "Return a single JSON object and nothing else. No markdown, no code fences, "
        "no commentary before or after.\n\n"
        "{\n"
        '  "database_name": string,\n'
        '  "summary": string,\n'
        '  "domains": [{ "name": string, "description": string, "entities": [string] }],\n'
        '  "entities": [{\n'
        '     "name": string,\n'
        '     "description": string,\n'
        '     "business_key": [string],\n'
        '     "attributes": [string],\n'
        '     "source_tables": [string],\n'
        '     "relationships": [{\n'
        '        "related_entity": string,\n'
        '        "verb_phrase": string,\n'
        '        "cardinality": "ONE_TO_ONE"|"ONE_TO_MANY"|"MANY_TO_ONE"|'
        '"MANY_TO_MANY"|"UNKNOWN",\n'
        '        "is_optional": boolean,\n'
        '        "description": string\n'
        "     }]\n"
        "  }],\n"
        '  "business_rules": [string],\n'
        '  "assumptions": [string],\n'
        '  "recommendations": [string]\n'
        "}\n\n"
        "Every name in domains[].entities must match an entity name exactly. Every "
        "relationships[].related_entity must match an entity name exactly. "
        "source_tables must use the qualified schema.table names from the context."
    ),
)


class PromptBuilder:
    """Assembles a system prompt and a user prompt from a template."""

    def __init__(self, template: PromptTemplate = CONCEPTUAL_MODEL_PROMPT):
        self.template = template

    def build_system_prompt(self) -> str:
        """The stable half of the prompt.

        Kept free of any context data so it is byte-identical across runs and
        across databases — the prefix stays cacheable, and the cost of a
        second run drops accordingly.
        """
        sections = [self.template.role, "", self.template.objective, ""]

        if self.template.instructions:
            sections.append("How to approach this:")
            sections.extend(f"- {line}" for line in self.template.instructions)
            sections.append("")

        if self.template.exclusions:
            sections.append("Out of scope:")
            sections.extend(f"- {line}" for line in self.template.exclusions)
            sections.append("")

        if self.template.output_contract:
            sections.append("Output format:")
            sections.append(self.template.output_contract)

        return "\n".join(sections).strip()

    def build_user_prompt(self, context: BusinessContext) -> str:
        """The variable half: the business context for this database."""
        return (
            "Here is the structural analysis of the database.\n\n"
            f"{ContextBuilder.to_prompt_json(context)}\n\n"
            "Produce the conceptual data model as JSON."
        )

    @staticmethod
    def response_json_schema(model_class) -> dict:
        """JSON Schema for a Pydantic response model.

        Passed to the API as a structured-output constraint so the response
        is guaranteed parseable. The parser still validates independently —
        a client that cannot enforce schemas must not be able to write an
        invalid artifact.

        The schema is hardened before it leaves: structured outputs require
        `additionalProperties: false` on every object, and Pydantic does not
        emit it. Without this the API rejects the schema outright.
        """
        return _harden_schema(json.loads(json.dumps(model_class.model_json_schema())))


def _harden_schema(node):
    """Recursively add `additionalProperties: false` to every object schema.

    Also strips validation keywords that structured outputs do not accept
    (numeric bounds, string lengths). Pydantic emits them from `Field(...)`
    constraints, and leaving them in causes the schema to be rejected —
    those constraints are still enforced by the parser on the way back.
    """
    unsupported = (
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "pattern",
    )

    if isinstance(node, dict):
        cleaned = {
            key: _harden_schema(value)
            for key, value in node.items()
            if key not in unsupported
        }
        if cleaned.get("type") == "object" or "properties" in cleaned:
            cleaned.setdefault("additionalProperties", False)
        return cleaned

    if isinstance(node, list):
        return [_harden_schema(item) for item in node]

    return node
