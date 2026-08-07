# AI Service Layer — Placement

**Status:** Identified, not implemented. No AI provider is integrated and no
API key is required to run anything in this repository today.

This note records *where* the AI layer belongs and *what contract* it should
have, so that the first engine to need it does not invent an ad-hoc one.

---

## The governing rule

> **AI never replaces a deterministic engine. AI only consumes the structured
> output that deterministic engines produce.**

Every engine built so far obeys this by construction: metadata, profiling and
relationship discovery are all pure functions over typed models, with no
model calls anywhere. That must remain true. If an AI service ever becomes
required for an artifact to be produced *at all*, the boundary has been
violated.

---

## Where it goes

```
migration/llm/          <- already reserved and empty
    client.py           provider-agnostic chat/completion wrapper
    service.py          AIService - prompt in, validated Pydantic model out
    prompts/            versioned prompt templates, one file per use case
```

`migration/llm/` already exists as an empty package, alongside the other
reserved module directories.

### Why a service layer rather than direct SDK calls

The same three problems recur in every AI-consuming engine, and none of them
belong in an engine:

1. **Provider abstraction.** `LLMConfig` already models `provider`, `model`
   and `temperature` (`models/config.py:102-107`), with `LLMProvider`
   supporting both OpenAI and Anthropic. A single client keeps that promise
   real; scattered SDK calls would quietly hardcode one vendor.
2. **Structured output.** Engines must receive validated Pydantic models, not
   free text. Schema enforcement, parse-failure retries and validation belong
   in one place.
3. **Operational concerns.** Retries, timeouts, token accounting, response
   caching and prompt versioning are identical for every caller.

### Contract

```
AIService.generate(prompt_name: str, context: BaseModel, response_model: type[T]) -> T
```

Typed model in, typed model out. An engine never sees a raw string, and never
constructs a prompt inline.

---

## First consumer: the Conceptual Model Generator

The Conceptual Model Generator is the right first consumer because its inputs
are already fully deterministic and its output is inherently interpretive.

**Deterministic inputs, already produced:**

- `metadata.json` — tables, columns, keys
- `profile.json` — value distributions, detected formats
- `relationships.json` — the relationship graph, with evidence and confidence

**What only AI can add:**

| Task | Why it is not deterministic |
|---|---|
| Business entity naming | `product_promotion` is a junction table, not a business entity. Deciding it represents "Promotional Campaign Membership" requires domain reading. |
| Relationship verb phrases | "A Customer **places** an Order" cannot be derived from a foreign key. |
| Semantic alias resolution | `orders.sales_rep_id → employee` is a role name. No naming rule or statistic can recover it — explicitly out of scope for Module 3. |
| Subject-area grouping | Clustering 10,000 tables into business domains. |
| Adjudicating inferred relationships | Reviewing `MEDIUM`/`LOW` confidence candidates against their evidence. |

### How Module 3 was built to support this

Module 3 was designed as AI *input*, not only as machine input:

- **`evidence[]`** — every relationship carries ordered, plain-language
  rationale, including signals that argued against it. The model receives
  reasoning to evaluate, not a bare number to trust.
- **`discovery_method` + `confidence_band`** — a prompt can instruct the model
  to treat `DECLARED` as ground truth and reason only about the inferred
  remainder. It never has to guess what is a real constraint.
- **Stable `id`** — deterministic and readable
  (`bronze.orders(customer_id)->bronze.customer(customer_id)`). A model can
  return `{"id": ..., "verdict": ..., "reason": ...}` instead of restating the
  relationship, which is cheaper and immune to paraphrase drift when merging
  results back.
- **Compact size** — the 19-table reference graph serializes to 34 KB.
  `summary` and `dependency_order` alone form a much smaller schema overview
  for cases where the full graph will not fit in a context window.

---

## Deliberately deferred

- **No provider SDK dependency** in `requirements.txt` until an engine needs it.
- **No prompt files** until the Conceptual Model Generator defines its first.
- **No agent framework.** Future AI agents orchestrate these engines by calling
  them; the engines do not call agents. That direction of dependency must not
  invert.

---

## One thing to decide before building it

Inference produces *candidates*, not truth. Once a human — or an AI reviewer —
accepts or rejects an inferred relationship, that decision must survive the
next run, or every execution re-proposes the same rejected candidates forever.

That needs a small persisted overrides file (accepted/rejected keyed by
relationship `id`), read by the engine and merged into its output. It is not
built, and it is not part of Module 3. It should be settled before the AI
layer starts producing review verdicts at volume, because otherwise those
verdicts have nowhere to live.
