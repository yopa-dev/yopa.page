---
title: "AgentCore Gateway model fallback: what the circuit breaker does to latency, cost and output shape"
date: 2026-10-23T15:00:00-04:00
author: Yoonsoo Park
description: "AgentCore Gateway can now take Bedrock InvokeModel calls on /inference and fall back through an ordered chain of models with a built-in circuit breaker. By design the caller can't see which model answered. I turned the documented rules into a local mock with the unpublished breaker numbers as explicit assumptions, ran seven failure stories through it, and wrote an owner-run script that measures the numbers AWS doesn't publish."
categories:
  - AWS
  - AI
tags:
  - agentcore
  - bedrock
  - model-fallback
  - circuit-breaker
  - resilience
---

On October 22, 2026, AWS [announced](https://aws.amazon.com/about-aws/whats-new/2026/10/agentcore-gateway-invokemodel-fallback/) two features together for AgentCore Gateway:

- **InvokeModel on `/inference`.** The gateway's inference endpoint now accepts InvokeModel and InvokeModelWithResponseStream. You point a stock `bedrock-runtime` client at it with `endpoint_url`.
- **Model fallback.** "The gateway automatically routes a request to an alternative model or provider when the primary destination is throttled, out of capacity, or unreachable." A built-in circuit breaker skips destinations that are failing. "You send one request and receive one response, regardless of the internal trial and error on a given request."

The [release notes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html) describe it as a gateway rule with `matchModels` and an ordered chain on `routeToTarget`, a "per-destination first-byte timeout", and a "service-owned circuit breaker, which is toggled on by default". The [fallback guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-rules-fallback.html) has the details, and its last sentence matters most to me: **"The gateway adds no caller-facing indicator of which destination was used."**

That's the feature working as designed, and it's also the risk. So my question is: **when does fallback fire, what opens and closes the breaker, what does falling back cost in latency and money, and how do you notice when a different model answered?**

**Short answer:**

- **Fallback fires only on the triggers you list.** Those are HTTP 4xx/5xx codes or classes, plus up to three connection-level conditions: `CONNECTION_ERROR`, `FIRST_BYTE_TIMEOUT` and `UNROUTABLE`. "2xx and 3xx responses are never fallback-eligible." So a 200 with a bad answer never falls back. When every destination fails, "the caller receives the last error."
- **The breaker matters most for stalls, not throttles.** In my mock, a primary returning 429 in 60 ms costs a request almost nothing before falling back, and the breaker cut p95 latency only from 1,743 ms to 1,686 ms. A primary that stalls costs every request the full first-byte timeout. There the breaker cut p95 from 6,683 ms to 1,697 ms.
- **The breaker's thresholds aren't published or configurable.** The local botocore 1.43.118 model accepts only `circuitBreaker.mode` (`ENABLED`/`DISABLED`), and anything else is rejected client-side. How many failures open it, how long it stays open and how big the half-open "small portion" is are not documented. Recovery time depends on them. Across 12 assumed combinations, 13 to 144 requests (3 to 29 seconds at 5 requests/s) were still served off the primary after it recovered.
- **The breaker can cost more when the primary is the cheap one.** The guide says so itself: you might turn it off "to keep using a cheaper primary rather than failing fast to a costlier secondary." In my flapping-primary story (30% 503s, fallback 4× the price), model spend was 56% higher with the breaker on: 817.5 vs 525 units.
- **Silent model switching is the failure mode to design for.** When both same-model destinations failed, 655 of 1,500 requests in my mock got HTTP 200 from the degraded model with zero caller errors, and every one of them had a different output shape. Only a client-side check catches that.
- **SDK retries multiply gateway attempts.** The Bedrock SDK retries throttling, and each retry walks the whole chain again. With everything throttled for two minutes and standard retry mode's 3 attempts, the gateway made 6,272 billed attempts for 1,500 requests with the breaker off, and 2,718 with it on. About 590 requests failed either way.

## What the docs actually say

Here's the rule set I encoded. Quotes are from the [fallback guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-rules-fallback.html) unless I name another source.

| Rule | Quote or source | Why it matters |
|---|---|---|
| Chain length | `targetFallback` is "an ordered list of 1 to 2 alternative destinations" | At most 3 tries per request |
| One try each | "attempts the destination once" | No per-destination retry inside the gateway |
| Exhausted chain | "the caller receives the last error" | The error you see comes from the last fallback, not the primary |
| Streaming | "Once a streaming response has started, the gateway can no longer fall back" | Mid-stream failures go to the caller as a partial response plus an error |
| `UNROUTABLE` | advances the chain "but does not feed the circuit breaker" | A misconfigured primary never trips the breaker |
| Breaker states | Closed, Open, Half-open; half-open lets "a small portion of requests through" | The thresholds are not given |
| Billing | "Each outbound attempt the gateway makes counts as a gateway invocation"; a skipped primary is not billed | Fallback multiplies gateway invocations. The gateway rate is [$0.005 per 1,000](https://aws.amazon.com/bedrock/agentcore/pricing/) |
| Model cost | billed "separately by Amazon Bedrock or the model provider" per attempt | An abandoned attempt may still cost tokens (not documented either way) |
| Visibility | "no caller-facing indicator"; routing logs "attribute the destination that actually served each request" | Logs are the only documented signal |
| Payloads | the gateway "does not convert one payload schema into another" ([InvokeModel guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-inference-invokemodel.html)) | An Anthropic Messages body can only fall back to a model that takes Messages |
| Guardrails | on a translated route, a Bedrock guardrail returns `400 ValidationException` instead of being dropped (same guide) | Cross-provider fallback and Bedrock guardrails don't mix; AWS points you to AgentCore Policy |

I checked the request shapes against the botocore 1.43.118 service model on my machine, with no AWS calls:

- `firstByteTimeoutMilliseconds` accepts 50 to 900,000.
- The fallback fields first appear in 1.43.118. Releases 1.43.115 through 1.43.117 have `CreateGatewayRule` but no `circuitBreaker`.
- Client-side validation does **not** catch a third fallback entry or an error name outside the enum. Those fail, or don't, on the server.

## The mock: seven stories, cause and effect

[`gateway_mock.py`](https://github.com/ypark9/yopa-experiments/tree/experiment/agentcore-gateway-model-fallback-20261023/2026-10-23-agentcore-gateway-model-fallback) is a stdlib Python simulation with no network access. Each request walks the chain the way the guide describes. Every number AWS doesn't publish sits in one `ASSUMED` dictionary:

- the breaker opens at 50% failures over the last 20 attempts, once it has at least 10
- it stays open 30 s
- half-open lets 10% through
- 3 probe successes close it
- an abandoned attempt bills 30% of a request's model cost
- the response body names the served model

Each story runs 1,500 requests at 5 per second, with an incident from t = 60 s to t = 180 s. Model costs are relative units, not dollars.

The default chain is a "big" model on `bedrock`, then the same model on `openai`, then a "small" model on `bedrock` at a quarter of the price. That is the shape of AWS's own example, which degrades `gpt-5.5` to `gpt-5.4` only "if neither can serve the request".

### Story A: primary throttled

The primary returns 429 for two minutes. Here's the breaker timeline from the mock:

| t (s) | Transition | Cause |
|---|---|---|
| 61.8 | closed → open | 10 of the last 20 attempts failed (429) |
| 91.8 | open → half-open | 30 s open timer elapsed |
| 92.4 | half-open → open | probe failed (429) |
| 122.4 / 123.2 | half-open → open again | timer, then a failed probe |
| 153.4 / 154.0 | same again | timer, then a failed probe |
| 184.0 | open → half-open | timer (the primary recovered at 180) |
| 189.8 | half-open → closed | 3 probe successes |

| | Breaker on | Breaker off |
|---|---|---|
| Caller errors | 0 | 0 |
| Gateway invocations billed | 1,513 | 2,100 |
| Primary attempts skipped | 634 | 0 |
| p50 / p95 latency | 1,303 / 1,686 ms | 1,319 / 1,743 ms |
| Served off the primary after recovery | 47 | 0 |

The breaker saved 587 gateway invocations, about $0.003 at $0.005 per 1,000. A fast 429 is cheap to try, so the latency gain is small. What it costs is the tail: the primary was healthy from t = 180 s, but 47 requests went to the fallback before the breaker closed.

### Story B: primary stalls

Now the primary accepts the connection and never sends a byte. Every attempt costs the full `firstByteTimeoutMilliseconds`.

| | Breaker on | Breaker off, 5,000 ms timeout | Breaker off, 1,000 ms timeout |
|---|---|---|---|
| p95 latency | 1,697 ms | 6,683 ms | 2,683 ms |
| Model cost units | 1,503.9 | 1,680.0 | 1,680.0 |

This is where the breaker earns its keep. With the breaker on, the worst request (6,730 ms) was a half-open probe that hit the stall. The model-cost row depends on my assumption that an abandoned attempt still bills input tokens. AWS doesn't say, and the owner-run measures it.

### Story C: silent degrade

Both same-model destinations fail: the primary with 429, the same model on the other provider with 503. Everything lands on the small model.

- Caller errors: **0**.
- 655 of 1,500 responses came from the small model, and 7 from the second provider before its breaker opened.
- All 655 had a different output shape. In this toy, the big model returns `{"label": ..., "confidence": ...}` and the small one returns fenced JSON without `confidence`. The rate is 100% by construction; the point is that HTTP status said 200 every time.
- Model spend fell to 1,008.75 units. A cost dashboard would show this incident as a good day.

If you depend on structured outputs, remember that the fallback model may not take the same schema features. Check your output contract against every model in the chain, not only the primary.

### Story D: everything throttled, plus SDK retries

A shared quota or a regional event throttles all three destinations. The client is boto3 in standard retry mode with `max_attempts` 3. botocore 1.43.118 still defaults to `legacy` mode, which allows up to 5 attempts, so an untuned client multiplies even more. The [InvokeModel guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-inference-invokemodel.html) confirms the SDK "retries throttling and transient server errors".

| | Breaker on | Breaker off |
|---|---|---|
| Caller errors | 592 | 590 |
| Gateway invocations billed | 2,718 | 6,272 |
| Served by the small model | 48 | 2 |

With the breaker off, every request walks three destinations, up to three times. The breaker cuts that 2.3×, but it doesn't fix availability: the errors are the same. My mock also has to decide what happens when **every** destination is open. I assumed it tries the last one anyway, which is where the 48 small-model answers come from. The guide doesn't say.

### Story E: cheap, flapping primary

The primary is the small model, failing 30% of requests with 503 during the incident. The only fallback is the big model at 4× the price.

| | Breaker on | Breaker off |
|---|---|---|
| Model cost units | 817.5 | 525.0 |
| Served by the 4× fallback | 590 | 200 |
| p50 latency | 821 ms | 740 ms |
| Caller errors | 0 | 0 |

With the breaker on, each opening sends *all* traffic to the expensive model for the whole open period, including the 70% the primary would have served. Across all 12 assumed combinations of open duration (5–60 s) and probe fraction (5–25%), spend with the breaker on stayed between 729 and 871.5 units. It was never close to 525. This is the case where AWS suggests `DISABLED`.

### Story F: misconfigured primary

The primary target doesn't serve the request's API path, so every attempt is `UNROUTABLE`. Since that "does not feed the circuit breaker", the breaker never opens:

- 1,500 of 1,500 requests were served by the fallback
- 0 caller errors, 0 breaker transitions

Nothing goes red. Only the routing logs, or a check on which model served each response, tell you the primary has never been used.

### Story G: failure mid-stream

The primary starts streaming and dies partway through. No fallback happens: 600 of 1,500 requests got a partial response and an error, and the tokens already streamed are paid for. The retry is up to your client.

## What I'd configure

1. **Order the chain by what you can accept, not just by availability.**
   - The same model on another provider is a real fallback.
   - A different model is a *degrade*. Put it last, and only if your output contract holds for it.
   - Match payload schemas. An Anthropic Messages body can't fall back to a Chat Completions model.
2. **List triggers narrowly.**
   - `429`, `5XX`, `CONNECTION_ERROR` and `FIRST_BYTE_TIMEOUT` are the failures that move with the destination.
   - Going by the trigger rules as written, adding broad `4XX` would also walk the chain on a 400 that every destination will reject. Each bad request then costs up to three attempts and still fails.
   - Leave `UNROUTABLE` out unless you watch for it, or Story F becomes permanent and quiet.
3. **Always set `firstByteTimeoutMilliseconds`.**
   - Stalls are where fallback and the breaker pay off (Story B).
   - Pick a value above your normal time to first byte. The default isn't documented, so I wouldn't rely on it.
4. **Decide the breaker mode per route.**
   - If the fallback costs about the same or less, keep it on.
   - If the primary is much cheaper and its failures are partial, try `DISABLED` and compare (Story E).
5. **Lower client retries on fallback routes.** The gateway already tries up to three destinations, so `max_attempts` 3 means up to nine attempts per request (Story D).
6. **Make the switch visible.**
   - Log the served model on every response. Whether the InvokeModel body's `model` field shows the served model or echoes the requested one is the first thing the owner-run checks.
   - Validate output shape on the client.
   - Watch the Bedrock per-model `Invocations` metric for each model in the chain. A fallback model that suddenly has traffic is your incident signal. For per-request cost, the [request-level attribution post](/blog/2026-06-01-bedrock-request-level-usage-attribution.html) covers the metadata side.

## Owner-run experiment (not yet run)

Nothing below has been run. It needs an AWS account and costs money.

**What it measures** (`owner_run.py` in the [experiment folder](https://github.com/ypark9/yopa-experiments/tree/experiment/agentcore-gateway-model-fallback-20261023/2026-10-23-agentcore-gateway-model-fallback)):

1. whether the InvokeModel response body names the model that actually served the request
2. whether primary attempts stop reaching Bedrock once the breaker opens, read from the per-model `Invocations` metric
3. whether a primary attempt abandoned by `FIRST_BYTE_TIMEOUT` still shows input tokens
4. how long traffic takes to return to the primary after it recovers

**Estimated cost:** well under one cent at list price; billing is unconfirmed until your bill shows it.

| Item | Count | List price | Estimate |
|---|---|---|---|
| IAM role, gateway, target, rule | 1 each, minutes | no charge listed for the resources themselves | $0 |
| Gateway invocations | ≤ 240 attempts (120 requests × ≤ 2) | $0.005 per 1,000 ([pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)) | ~$0.0012 |
| Model tokens | ≤ 240 attempts × ~20 input and ≤ 16 output tokens | your two models' Bedrock prices | well under $0.01 |
| CloudWatch `GetMetricData` | 6 metrics, once | per-metric charge on CloudWatch pricing | a fraction of a cent |

**Steps:**

1. Run the read-only checks first. Each one changes nothing.
   ```bash
   aws --version                                    # CLI v2
   python3 -c "import botocore; print(botocore.__version__)"   # need >= 1.43.118
   aws sts get-caller-identity --query Arn --output text       # confirms credentials; don't paste the output anywhere
   export AWS_REGION=us-east-1
   aws bedrock list-inference-profiles --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic')].inferenceProfileId"
   ```
   Pick two **different** Anthropic models from that list, so both take the same Messages payload. A small, cheap model is fine for both.
2. Get the code and dry-check it. `run.sh` is free and local; `validate_shapes.py` confirms your botocore accepts the request shapes.
   ```bash
   git clone https://github.com/ypark9/yopa-experiments.git && cd yopa-experiments
   git checkout experiment/agentcore-gateway-model-fallback-20261023
   cd 2026-10-23-agentcore-gateway-model-fallback && ./run.sh
   ```
3. Run it.
   ```bash
   export PRIMARY_MODEL=<first id> FALLBACK_MODEL=<second id>
   python3 owner_run.py --i-understand-this-uses-my-aws-account
   ```
   The script does the following:
   - creates a role `yopa-agw-fallback-<random>` that allows `bedrock:InvokeModel*` and `bedrock:List*`
   - creates a gateway with `AWS_IAM` inbound auth, a `bedrock-runtime` connector target and one rule (primary → fallback, breaker `ENABLED`, a 50 ms first-byte timeout to force the primary to fail)
   - sends 40 calls, 1.5 s apart
   - raises the timeout to 30 s and sends 80 more
   - deletes everything in a `finally` block
   - waits 3 minutes and reads the per-model Bedrock metrics into `results/owner-run-<random>.json`
4. Look for these things. They are expectations, not results.
   - **Phase 1:** calls succeed. If `body_model` shows the fallback model, the body is a usable signal. If every call shows the primary, either the rule didn't match an InvokeModel `modelId`, or 50 ms wasn't short enough. Note which.
   - **Metrics:** the primary's `Invocations` in phase 1, compared with 40, shows how many attempts the breaker skipped. Primary `InputTokenCount` above zero means abandoned attempts were billed.
   - **Phase 2:** the index of the first call served by the primary again, times 1.5 s, roughly measures open plus half-open time. Metric buckets are 1 minute, so the calls are the finer signal.

**Teardown and cost-stop checks.** Run these after the script, and also if it crashed:

```bash
aws bedrock-agentcore-control list-gateways --query "items[?starts_with(name,'yopa-agw-fallback')].[gatewayId,name]"   # expect []
aws iam list-roles --query "Roles[?starts_with(RoleName,'yopa-agw-fallback')].RoleName"                               # expect []
# if anything is left (gateway id G, target id T, rule id R, role N):
aws bedrock-agentcore-control list-gateway-rules --gateway-identifier G
aws bedrock-agentcore-control delete-gateway-rule --gateway-identifier G --rule-id R
aws bedrock-agentcore-control delete-gateway-target --gateway-identifier G --target-id T
aws bedrock-agentcore-control delete-gateway --gateway-identifier G
aws iam delete-role-policy --role-name N --policy-name invoke && aws iam delete-role --role-name N
```

The gateway, target and rule have no idle charge I could find on the pricing page, so once traffic stops, so does spend. The checks above exist so nothing sits around.

**Results:** (owner to fill in)

| Question | Result |
|---|---|
| Body `model` names the served model? | |
| Primary `Invocations` during phase 1 (of 40) | |
| Primary input tokens on abandoned attempts | |
| Calls until traffic returned to the primary | |

## What I did not measure

- **Any real gateway behavior.** Every number in the stories comes from the mock under my assumptions. The documented rules are encoded as written; the thresholds are guesses I swept, not AWS's.
- **Routing logs.** The guide says the gateway vends routing logs that name the serving destination and breaker skips. I haven't seen their format or how delivery is set up.
- **Weighted routes.** Each leg gets its own fallback, and "the circuit breaker is per destination and independent of the weights." I didn't model it.
- **Session stickiness, Policy denials and token-based rate limiting.** These interact with routing too (a rate-limit rejection is "a throttling error"). Whether a gateway-side throttle triggers fallback is not covered here.
- **Real model quality differences.** The output-shape drift in Story C is a toy. The real gap between two models on your task is something to evaluate, not assume.
