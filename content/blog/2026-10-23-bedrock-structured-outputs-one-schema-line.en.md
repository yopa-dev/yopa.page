---
title: "Bedrock structured outputs: what one ordinary schema line does to your request"
date: 2026-10-23T10:00:00-04:00
author: Yoonsoo Park
description: "Structured outputs for Claude on Amazon Bedrock guarantee the JSON shape, but only for a subset of JSON Schema. I took nine Pydantic models, each one ordinary line away from a baseline, and checked what each one does on two paths: raw boto3 gets a documented 400, while the Anthropic SDK quietly rewrites the schema. One line fails with no error at all."
categories:
  - AI
  - AWS
tags:
  - amazon-bedrock
  - structured-outputs
  - claude
  - pydantic
  - json-schema
---

Structured outputs for Anthropic's Claude models on Amazon Bedrock were [announced on October 20](https://aws.amazon.com/about-aws/whats-new/2026/10/claude-structured-outputs-bedrock/). You give the model a JSON Schema. Bedrock compiles it into a grammar and constrains decoding, so the reply always parses and always has the required fields. That removes a whole class of retry loops, and it's the feature I'd reach for first in any extraction or classification pipeline.

The catch is in one sentence on the [Bedrock structured outputs page](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html):

> If the schema contains unsupported features, Amazon Bedrock returns a 400 error immediately.

The supported subset is narrower than what most Python code already produces. So I asked a practical question: **if you take a Pydantic model you already have and add one ordinary line, what happens?** The answer depends on which client you use, and one of the three outcomes is silent.

**Short answer:**

- **Raw boto3 gets a 400.** Pydantic's `model_json_schema()` never adds `additionalProperties: false`, so all 9 of my models were outside the documented subset as generated. Six of them had a second problem too: `ge`/`le`, `max_length`, a list `min_length=2`, a recursive model, and `AnyUrl`, which quietly emits `minLength: 1`. Sent through boto3, those are the documented immediate 400. That is loud, and that is good.
- **The Anthropic SDK does not 400.** `AnthropicBedrock().messages.parse()` rewrites the schema before sending. It moves each unsupported constraint into the field's `description` and checks the reply against your Pydantic model afterwards. A reply that breaks the constraint comes back as a Pydantic `ValidationError`, after you have paid for the call.
- **One line fails silently: `dict[str, str]`.** The SDK rewrites a map field to an object with no properties and `additionalProperties: false`. Under that schema the only valid value is `{}`. You get no 400 and no `ValidationError`, just an empty map every time.
- **The first call with a new schema can be slow.** Bedrock compiles the grammar, "which may take up to a few minutes", and caches it. Warm new schemas during deploy, give that first call a long timeout, and lint schemas in CI.

Everything below ran on my machine with no AWS calls. The parts that need Bedrock itself are the cold-call latency, the exact 400 body and whether a missing `additionalProperties` alone is rejected. Those are written up as an owner-run experiment at the end, with its cost.

## The nine lines

Each model is a baseline ticket classifier plus one line you might write without thinking about it. The [code is here](https://github.com/ypark9/yopa-experiments/tree/experiment/bedrock-structured-outputs-one-schema-line-20261023/2026-10-23-bedrock-structured-outputs-one-schema-line).

I linted two versions of each schema against the subset on the Bedrock page:

- **Raw:** what `Model.model_json_schema()` produces, which is what you'd paste into a boto3 call.
- **SDK:** what `anthropic.transform_schema(Model)` produces in `anthropic` 2.2.0, which is what `messages.parse()` sends.

The linter is my reading of the doc, not Bedrock's validator.

| The one line | Raw schema (boto3) | What the SDK sends instead |
|---|---|---|
| none (baseline) | `additionalProperties` missing | adds `additionalProperties: false` |
| `confidence: float = Field(ge=0, le=1)` | + `minimum`, `maximum` | moves `{maximum: 1, minimum: 0}` into `description` |
| `summary: str = Field(max_length=200)` | + `maxLength` | moves it into `description` |
| `order_id: Optional[str] = None` | `additionalProperties` missing only | OK |
| `tags: dict[str, str]` | + `additionalProperties` is a schema | **replaces the map with `{"properties": {}, "additionalProperties": false}`** |
| `steps: list[str] = Field(min_length=2)` | + `minItems: 2` (only 0 and 1 are supported) | moves it into `description` |
| `children: list["Node"]` | + recursive `$ref` | still recursive: **fails either way** |
| `ticket: str = Field(pattern=r"^TCK-\d{6}$")` | `additionalProperties` missing only | moves `pattern` into `description` |
| `link: AnyUrl` | + `minLength: 1` that you never wrote | keeps `format: uri`, moves `minLength` into `description` |

Two rows surprised me:

- **`AnyUrl`:** Pydantic adds `minLength: 1` to the schema without you writing it, and `minLength` is on the unsupported list.
- **`pattern`:** [Anthropic's docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) list simple regex as supported, but this SDK version moves `pattern` into the description anyway. So with the SDK, a pattern you could have had enforced is only suggested.

## What the SDK actually puts on the wire

The `transform_schema` source explains the behavior plainly. After it handles the fields it knows, the code says:

```python
# if there are any propes leftover then they aren't supported, so we add them to the description
# so that the model *might* follow them.
```

For objects, it does this:

```python
json_schema.pop("additionalProperties", None)
strict_schema["additionalProperties"] = False
```

The second snippet is the `dict` problem. A Pydantic `dict[str, str]` becomes `"additionalProperties": {"type": "string"}`. The SDK throws that away and sets `false`, and the object has no listed properties. The grammar is built from what's sent, so the model can't produce any keys.

To see it end to end without calling AWS, I pointed `AnthropicBedrock` at an `httpx2.MockTransport` with dummy keys. Every request was answered locally. The request went to `/model/global.anthropic.claude-haiku-5-5/invoke`, and the schema in `output_config.format` was the transformed one. Then I fed back replies:

| Constraint in the Pydantic model | Reply I fed back | What `messages.parse()` did | Does your code notice? |
|---|---|---|---|
| `confidence` limited to 0–1 (`Field(ge=0, le=1)`) | `{"confidence": 1.4, ...}` | `ValidationError`: "Input should be less than or equal to 1" | Yes, but only after the call is paid for |
| `ticket` must match `^TCK-\d{6}$` (`Field(pattern=...)`) | `{"ticket": "ticket 42"}` | `ValidationError`: "String should match pattern '^TCK-\d{6}$'" | Yes, but only after the call is paid for |
| `tags` as a map (`dict[str, str]`) | `{"tags": {}, ...}` | returned `tags={}` with no error | **No.** An empty map looks like a normal answer |

Takeaway: constraints the SDK moves into `description` turn into exceptions after you pay for the call, and the `dict` field fails silently.

I also checked the map case with `jsonschema`. `{"tags": {"priority": "high"}}` is valid under the original Pydantic schema and invalid under the schema the SDK sends. `{"tags": {}}` is valid under both. So under constrained decoding the model can only produce the empty map, and your code accepts it as a normal answer. Anthropic's own structured-outputs page has `messages.parse()` examples with `data: dict` and `metadata: dict` fields. By this reading of the transform, those fields can only come back empty.

The first two rows are not silent, but they are late. On the raw path, a 400 fails before any tokens are generated. On the SDK path, you pay for the call and then get an exception. If the model follows the description hint most of the time, that becomes an occasional production error rather than a failed deploy.

## Pick the failure you want

| You want | Do this |
|---|---|
| Fail at deploy, not at 3 a.m. | Lint the schema in CI against the documented subset. The repo's `lint.py` is about 30 lines. Treat any finding as a build error |
| Keep Pydantic constraints | Accept that they are post-checks, not guarantees. Catch `ValidationError`, log it, and decide on retry or fallback. Don't assume "structured outputs means no retries" |
| A map or free-form object | Don't use `dict[str, X]`. Use `list[KeyValue]` with `key` and `value` fields, which the grammar can enforce |
| Recursion (trees, nested comments) | Flatten it: a list of nodes with `parent_id`. Neither path accepts a recursive schema |
| No surprises from the SDK | Send `transform_schema(Model)` output yourself, diff it against `model_json_schema()` in a test, and fail on any `description` that gained a `{...}` suffix |

## The slow first call

The Bedrock page also describes the compile step:

- "For new schemas, Amazon Bedrock compiles the grammar, which may take up to a few minutes."
- "Successfully compiled grammars are cached for 24 hours from first access."
- "Identical schemas from the same account use cached grammars."

The [AWS ML blog post](https://aws.amazon.com/blogs/machine-learning/structured-outputs-for-anthropic-claude-models-on-amazon-bedrock/) from October 19 adds which changes count: "changing only the name or description fields leaves the cached grammar intact". Changing the structure does not.

Two sources disagree on one detail. Bedrock says 24 hours "from first access". [Anthropic's page](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) says "cached for 24 hours from last use". If Bedrock means what it says, a schema in steady use still recompiles once a day. That matters if your client timeout is a few seconds. I can't tell which is true without calling the service, so it's in the owner-run list.

How bad can a compile get? A [LiteLLM issue](https://github.com/BerriAI/litellm/issues/34388) reports "Compiled grammar size (410.4MB) exceeds maximum allowed size (300MB)" with 20 to 30 strict tools. In that report, the caller sat until a proxy returned 504 rather than seeing the error promptly. Big tool sets with `strict: true` are where the compile step stops being a footnote.

What I'd do:

- **Warm every new schema version during deploy,** with one cheap call, before traffic hits it.
- **Give that call a long read timeout.** botocore's default is 60 seconds, and "a few minutes" is longer.
- **Version schemas as artifacts,** so a structure change is a deliberate deploy, not a side effect of editing a model class.

## Owner-run experiment (not yet run)

These questions need real Bedrock calls:

- How long is the first call with a new schema?
- Is a description-only change really warm, and is a structure change cold?
- Does a schema whose only problem is a missing `additionalProperties` get a 400?
- What does the 400 body say for `minimum`/`maximum`?

I have not run this. The results below are blank until someone does.

**Estimated cost:**

- **What it calls:** about 11 Claude Haiku 5.5 calls of roughly 150 input and at most 200 output tokens.
- **List price:** Anthropic's [pricing page](https://platform.claude.com/docs/en/about-claude/pricing) lists Claude Haiku 5.5 at $0.10 per million input tokens and $0.50 per million output tokens for global routing. That works out to about $0.001.
- **Confirm the Bedrock price for your Region** on the [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/). Regional endpoints cost more, and the page renders prices client-side, so I could not quote them.
- **Grammar compilation:** I found no price for it in the docs.
- **Total:** treat it as "well under $0.01", not $0. Nothing is created, so nothing keeps billing.

**Steps:**

1. Check the account and role. This is read-only and free:
   `aws sts get-caller-identity --query Arn --output text`
2. Make sure Claude Haiku 5.5 is enabled for the account in the Bedrock console's model access page. That page is read-only unless you request access.
3. Get the code:
   `git clone https://github.com/ypark9/yopa-experiments && cd yopa-experiments && git checkout experiment/bedrock-structured-outputs-one-schema-line-20261023 && cd 2026-10-23-bedrock-structured-outputs-one-schema-line`
   `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
4. Run it. It refuses to start without the flag, makes at most one attempt per call and allows 600 s for the cold call:
   `AWS_REGION=us-east-1 python owner_run.py --i-understand-this-uses-my-aws-account`
5. Expected observations, if the docs hold:
   - call 1 (a new structure) is much slower than calls 2 to 4
   - call 3 (description-only change) is warm
   - call 4 (structure change) is cold again
   - 5b returns HTTP 400, naming `minimum` or `maximum`
   - call 6 returns `"tags": {}`
   - 5a is the open question: does a missing `additionalProperties` alone get a 400?

**Teardown and cost-stop checks:** nothing is created, so there is nothing to delete. Check the next day in Cost Explorer, filtered to Amazon Bedrock, that the charge is in cents or less.

**Results:** _not yet run._

## What I did not measure

- **Bedrock's own validator.** My linter encodes the doc. Bedrock may accept or reject things the doc doesn't list.
- **Real model behavior on description hints.** How often Claude follows `{maximum: 1, minimum: 0}` when it is only a hint is not measured here. The mock replies were chosen to break the constraint.
- **Other SDKs and paths.** TypeScript, Java and Go SDK transforms, and the Converse API's `outputConfig.textFormat` path, were not checked. Converse takes the schema as a JSON string, and boto3 sends whatever you give it.
- **Latency of any kind.** No number in this post is a latency.
