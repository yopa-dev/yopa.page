---
title: "Tokenomics on AWS: Attribution Grain, Optimization Levers, and Where Enforcement Belongs"
date: 2026-09-23T09:00:00-04:00
author: Yoonsoo Park
description: "AWS Cloud Financial Management now frames AI cost as tokenomics across four pillars: visibility, optimization, governance, and ROI. Here is how that frame maps onto the attribution mechanisms that already exist on Amazon Bedrock, which optimization levers survive contact with an agent loop, and why an IAM-principal cost report quietly collapses when every caller shares one service role."
categories:
  - AWS
  - FinOps
tags:
  - finops
  - bedrock
  - cost-attribution
  - prompt-caching
  - budgets
---

The FinOps Foundation put a name on AI cost management this year and gave it a foundation: **tokenomics**, announced as a new domain under the Linux Foundation. AWS followed with a Cloud Financial Management blog that maps its existing FinOps pillars (See, Save, Run, Plan) onto AI workloads as Visibility & Attribution, Optimization, Governance, and Value/ROI.

That framing is useful, but a four-pillar diagram is not a decision. Once you start filling it in, the pillars stop being four independent workstreams and collapse into three questions you have to answer before any dashboard is worth building:

1. **Unit of account**: do you manage tokens, requests, or runs?
2. **Attribution key**: what field on the bill tells you who spent it?
3. **Enforcement point**: where a limit is allowed to say "no"?

Everything else in the pillar article is a lever you pull after those three are settled. This post is about the three, using the mechanisms that actually exist on Amazon Bedrock today, and the places they break.

## Pillar 1 is one decision: attribution grain

"Visibility" sounds like a checkbox. It is really a choice of grain, and the available grains are not interchangeable. Four mechanisms ship today, and each answers a different question.

| Mechanism | Grain | What it answers | Cost |
|-----------|-------|-----------------|------|
| IAM principal allocation in CUR 2.0 | Per role / user | "Which caller spent it?" | Free, needs a data-export settings change and a cost-allocation tag |
| Application inference profile | Per workload, per model | "What does this product cost to run?" | Free, but one profile per model |
| Bedrock Projects / Workspaces | Per project, aggregated | "What did this app spend this week?" | Free, no per-request detail |
| Model invocation logs | Per request | "What did this prompt cost?" | Storage + query cost, and per-region setup |

IAM principal allocation is the headline addition. Turn it on in your Amazon Data Exports configuration, activate the matching cost-allocation tag, and Cost Explorer will break Bedrock model inference cost down by the IAM principal that called it. That is a real improvement over the old state of affairs, where the model ID was the only identifier in the cost data.

But "principal" is only as granular as your IAM design. Which brings us to the first trap.

### The shared service role collapse

Most production agents do not call Bedrock as the end user. They call it as a service role: one task role for the runtime, or one execution role for the whole platform. If every agent turn in your organization runs under `arn:aws:iam::…:role/agent-platform-prod`, then per-principal attribution produces exactly one line item, and it is a very large one.

This is the same failure mode I described in [Per-Request Cost Attribution on Amazon Bedrock](/blog/2026-06-01-bedrock-request-level-usage-attribution.html), and the fix has not changed: either give each calling service its own role, or attach per-request metadata in a shared client wrapper so the log line carries a team and feature key. The AWS tokenomics post actually recommends both, in that order: IAM principal allocation first, invocation logs second, and joining the two for token-level attribution per day.

If you want the cheap version, projects and workspaces are a decent default. Set a Project ID once on the client and every Responses or Chat Completions call on the `bedrock-mantle` endpoint is attributed to it; Workspaces do the same for the Anthropic-compatible Messages API. Neither is tied to a model, so you avoid profile sprawl.

The catch is written into the feature: Projects and Workspaces deliver **aggregated spend at per-usage-type-per-day grain**. There is no per-prompt cost, and no way to reconstruct one retroactively. If your ROI question is "what did the new prompt template do to our cost per conversation," aggregated daily grain cannot answer it. You need invocation logs for that.

### What the invocation log actually buys you

Invocation logging records the prompt, the response, token counts, the model, the stop reason, the account, and the IAM role, per call, into S3 or CloudWatch. That record is what makes the "who and how many tokens" join possible: CUR for the dollars, logs for the tokens, one date key.

Two operational notes that bite people:

- **It is a per-region setting.** Calls to models in a region where logging is off simply do not appear in your token dashboard, while the spend still appears on the bill. Put the setting in your account bootstrap, not in a runbook.
- **`amountUsd = 0` still costs you a row.** Zero-token and cached calls still write log records. Budget your log storage for call volume, not just for token volume.

## Pillar 2: which optimization levers survive an agent loop

The traditional FinOps levers do not transfer. Commitments do not work on a service whose prices and model lineup change quarterly. Idle-resource hunting does not work when you are billed by consumption, and an idle agent consumes nothing. What transfers is a smaller set, and the order matters.

**The tool choice dominates everything.** AWS ran the same Haiku 4.5 coding task across tools and got 1 cent on Kiro against 7 cents on Claude Code for the same job. A 7x spread on identical work is bigger than anything prompt engineering will return. Measure the tool before you tune the prompt.

**Input shaping is the cheapest lever.** A conversational prompt ("hey, can you help me with…") ran about 85 tokens; the same task as a structured, directive prompt ran about 38. That is a 55% input reduction for a editing change, and it applies to every call forever. It also compounds with caching.

**Context is the lever people forget to protect.** Every MCP server and skill you install adds to the context window on every call. If you run eight and need three, you pay for five you do not use, and you pay again when the cache expires and the whole thing reloads. A sliding window or progressive summarization does the same for multi-turn conversations, where turn 10 can cost ten times turn 1 for the same question.

**Output tokens are the expensive side.** Output is roughly 3x the price of input per token, so `max_tokens` and a "be concise" instruction are not style preferences. They are the second half of your bill.

**Prompt caching is the biggest single lever, with a TTL-shaped caveat.** Bedrock prompt caching stores repeated context and, at a 5-minute TTL on exact matches, can cut cost by up to 90% and latency by up to 85%. That is genuinely large. It is also exactly where the two levers above interact: a long-lived system prompt shared by many users caches well, whereas content that changes per user or per turn does not, and the reload cost lands on the call after expiry.

**Model right-sizing is a measurement, not a guess.** Bedrock model evaluation exists to answer "is the cheap model good enough for this task" before you move classification and routing traffic to it. Do not skip it, and do not select on the model's reputation.

### The reporting trap in caching

A 90% cost reduction is a demand signal to your finance partner, and it is not one. Cached input tokens are cheaper because work was reused, not because usage fell. If your dashboard only plots dollars, a caching win looks identical to a product that lost traffic. Keep the token counts and the cache behavior next to the cost line so the two stories do not merge.

## Pillar 3: governance is a placement decision

Governance is where AI FinOps stops being reporting and starts being architecture, because a limit has to live somewhere that the request path actually passes through.

The pillar article offers three layers:

- **AWS Budgets** with billing views, to scope a budget to a specific AI workload and alert before you reach 100%.
- **Cost Anomaly Detection**, for the "someone deployed something and forgot it" case.
- **Service Control Policies**, to restrict which models are reachable at the organizational-unit level, which is the right tool for a sandbox: remove frontier models from the OU rather than asking people not to use them.

It also points at gateways for the runtime case: LiteLLM for open-source per-team budgets, Claude Apps Gateway as the AWS-managed path for Claude on Bedrock, and Dogwood, which supports token budget caps and can block runaway agent loops through a policy language on AgentCore Gateway.

The decision underneath all of these is **where enforcement is allowed to say no**. There are only four real placements:

| Placement | Fails how | Right for |
|-----------|-----------|-----------|
| SCP / model access | Hard block at request time | Sandboxes, model allow-lists |
| IAM role / model access | Hard block, per role | Keeping expensive models away from roles that do not need them |
| Budget + anomaly alert | Soft, after the fact | Production teams with a human owner |
| Gateway token cap | Hard block per team / per loop | Agents that can loop |

A dashboard is not an enforcement point, and this is the part that people conflate. So is a cost report. Neither sits on the request path, so neither can stop the runaway loop that runs over a weekend; only the third row can. The corollary from last year's hobby-account exercise still holds: I ran [personal AWS cost guardrails](/blog/2026-03-30-personal-aws-cost-guardrails.html) as three layers precisely because the notify layer and the stop layer fail differently.

### What a gate in front of the model costs you

Two of those rows are cheap and you should just do them. An IAM policy that limits which roles can call which models is the cheapest real control you have: it works before the call, you already manage everything else this way, and it fails closed. Its limit is the same one as attribution: it is only as fine as your roles, and most teams end up with a few shared service roles.

The gateway row is the only one that can stop one specific request because of what it would cost. AWS has a reference design for it, a "cost sentry": a Step Functions workflow runs before each Bedrock call, reads current token usage from CloudWatch metrics, compares it with a per-model budget stored in DynamoDB, and lets the call through or denies it. Two things come with that:

- **The gate is only as fresh as its numbers.** If the usage comes from CloudWatch metrics, a fast loop can run past the limit before the metric catches up. The gate slows a runaway down; it does not stop it at an exact token count.
- **Every call now waits on the gate, and you have to decide what happens when the gate is down.** Fail open: the call goes through and the budget is not enforced for a while. Fail closed: a working feature breaks to protect a budget. Neither is wrong, but it is an availability decision, not a cost one. Write the choice down next to the gate, because teams that skip it find out their answer during an incident.

One more limit: a gate in front of Bedrock only sees Bedrock. If some of your traffic goes to a model provider outside AWS, only a gateway that fronts every provider can hold one limit across all of them.

So the order I would build in: roles that cannot reach the expensive models, then attribution, then a budget and an anomaly alert, and only then a pre-call gate for the one or two workloads where a runaway loop is a real risk.

## Pillar 4: ROI, and why the denominator is the hard part

The pillar article is refreshingly honest about ROI, and it is worth restating the shape rather than the numbers. There are three problems, and only the first is about cost.

- **The numerator is bigger than the token bill.** Engineering time, data preparation, testing, monitoring, plus storage, gateways, orchestration, transfer. A token-cost dashboard that excludes those numbers reads as a 90% cheaper system than it is.
- **The denominator is a measurement you have to design.** "500 dollars per coding bug resolved" is a proxy, and mostly a bad one. The article's list of failure modes is the useful part: saved hours did not become saved dollars because nobody was let go; efficiency rose while profit stayed flat; revenue attribution was never isolable from the other ten things that happened.
- **The target moves.** A model choice that made sense six months ago may be strictly dominated today, which means an ROI model has a shelf life measured in quarters.

The one intervention that survives all three: define the problem and the baseline before the project starts, not after. There is a worked internal example in the post (variance analysis cut from 15 minutes to 1, 14,000 hours saved), and the honest reading is that the numbers only mean something because the baseline existed first.

## What I would actually do first

Pick one pillar and finish it. If I were starting on a Bedrock-heavy account today, in this order:

1. **Turn on IAM principal allocation and the cost-allocation tag**, and check how many distinct principals your Bedrock spend actually has. If it is one, you have found the first real work item, not the first dashboard.
2. **Enable invocation logging in every region you call from**, and put that setting in the account bootstrap. This is the only source of per-request grain.
3. **Set one budget and one anomaly detector** on the AI workload, and be explicit about which of them is allowed to stop anything. If the answer is "neither," you have alerts, not governance.

An agent platform is a cost surface with no shutdown switch: it runs continuously, it calls a model on user input, and each tool call can double the price of one interaction. That is the same reason my own [Hermes Agent cost breakdown](/blog/2026-08-08-hermes-aws-cost-breakdown.html) came out surprising: for an always-on agent, the surrounding infrastructure (NAT gateway, EFS throughput) can cost as much as the compute, and the model spend sits on top of that. Tokenomics is the discipline of knowing which of those lines you can actually move.

## Pitfalls worth writing down

- **Metadata is not forgeable, so do not put anything that must not be forged in it.** An `env=prod` tag in request metadata can be claimed by anyone who can call the model. Use IAM for boundaries.
- **Aggregated grain is a one-way door.** If you pick Projects without invocation logs, the per-prompt question is unanswerable until you turn logs on going forward.
- **A cached-token drop is not a demand drop.** Keep token counts next to dollars.
- **Count all four token types.** CUR has separate line items for input, output, cache read, and cache write tokens. If you only add up input and output, a cache-heavy workload will not match the bill.
- **A new cost allocation tag is not a same-day control.** It can take up to a day for the tag key to show up for activation and up to another day to activate, so plan on one to two days before it appears in cost data.
- **Static thresholds on a growing workload will not hold.** Any fixed dollar rule either drowns the big accounts or ignores the small ones; that is the topic of the companion post on forecast-based detection.
- **Overage and standard rate are separate concepts.** If your internal charge model has an overage rate, make sure the rate is actually applied somewhere, or you are only collecting the flag.

## References

- [Getting started with Tokenomics on AWS](https://aws.amazon.com/blogs/aws-cloud-financial-management/getting-started-with-tokenomics-on-aws/) (AWS Cloud Financial Management Blog)
- [IAM principal cost allocation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/iam-principal-cost-allocation.html)
- [Bedrock cost management: Projects, inference profiles, and workspaces](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-management.html)
- [Bedrock model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html)
- [Bedrock prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)
- [Understanding your Amazon Bedrock CUR data](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-understanding-cur-data.html)
- [Build a proactive AI cost management system for Amazon Bedrock, Part 2](https://aws.amazon.com/blogs/machine-learning/build-a-proactive-ai-cost-management-system-for-amazon-bedrock-part-2/) (the cost sentry)

If you are building the chargeback layer underneath these dashboards, the same question comes back at a lower level: what unit do you bill in, and who is allowed to convert a dollar cost into that unit. That is the design decision the attribution table above is really about.
