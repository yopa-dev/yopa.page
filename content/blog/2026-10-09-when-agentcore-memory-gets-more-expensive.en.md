---
title: "AgentCore Memory's New Pricing Only Costs More When You Read What the Model Can't Use"
date: 2026-10-09T09:00:00-04:00
author: Yoonsoo Park
description: "AgentCore short-term memory moved from per-event to per-GB pricing on October 6. Each event now gets about 99 re-reads (14 for large events) before it costs more than before. I put the memory bill next to the LLM tokens for the same history. The new price only passed the old one when the history no longer fit a 1M-token context, or after about 200 turns of tiny events, and next to Claude Sonnet 5.5 memory was under 1% of the cost."
categories:
  - AI Agents
  - AWS
tags:
  - Amazon Bedrock AgentCore
  - AI Agents
  - Memory
  - Cost Optimization
  - Pricing
---

On October 2, my AWS account received a Health notice. Amazon Bedrock AgentCore short-term memory was changing its pricing. The old rate was a flat **$0.25 per 1,000 new events**, and reads were included. Starting **October 6, 2026**, it bills three things separately:

| Dimension | New price | How size is counted |
|---|---|---|
| Ingestion | $1.00 per GB | Each event clamped to 12 KB min, 64 KB max |
| Retrieval | $0.20 per GB | Each event clamped to 12 KB min, 64 KB max |
| Storage | $0.10 per GB-month | Actual size, prorated hourly over the event's TTL |

AWS says more than 95% of customers will pay less, and names the exceptions: large payloads, extended TTL, and frequent retrieval. Credits cover any increase through December 31, 2026.

"Frequent retrieval" was the part I could not size from the notice. My first draft of this post answered it with turn counts: reload the full history every turn and you pass the old price at turn 30 with 64 KB events. That was true in my model and mostly useless. At turn 30 that history would be about 1.5 million tokens, and no model would take it.

So this version asks the question that matters for a design: **next to what the agent already spends on tokens, when does the new memory price change anything?**

## Short answer

- **Each event has a re-read budget.** A 12 KB-or-smaller event can be read back about **99 times**, and a 64 KB event about **14 times**, before it costs more than the old $0.00025 flat fee.
- **You run out of context before you run out of budget.** In my sweep, every case where the new price passed the old one, except 1 KB events after about 200 turns, needed a history over **1M tokens** on that turn. The agent would be paying to read events the model cannot take.
- **Next to tokens, memory is small.** For 50-turn sessions sent to Claude Sonnet 5.5 at the full input price, memory was **0.01% to 0.62%** of memory plus history tokens in every setup I modeled.
- **It is not small for tiny events on cheap tokens.** With 1 KB messages, Claude Haiku 5.5, and cache reads, memory reached **42%** of that total. The 12 KB minimum bills a 1 KB message as 12 KB, and the tokens do not. Even there, the new price was below the old one.

This is a cost model, not a bill. I made no AWS or model calls. The code and raw output are in [yopa-experiments](https://github.com/ypark9/yopa-experiments/tree/experiment/when-agentcore-memory-gets-more-expensive-20261009/2026-10-09-when-agentcore-memory-gets-more-expensive) (commit [`fb7ffcd`](https://github.com/ypark9/yopa-experiments/commit/fb7ffcd73ef4faf5d629f28075222f359c0ab6f6)).

## The re-read budget

The old price charged per write. The new one charges per byte written, per byte read, and per hour kept. For one event, the break-even is simple arithmetic:

| Event size | Write (new) | Each read (new) | Reads before it passes $0.00025 |
|---|---|---|---|
| 1 KB or 12 KB | $0.000012 | $0.0000024 | about 99 |
| 64 KB or more | $0.000064 | $0.0000128 | about 14 |

That budget is the number to carry around. An agent that reloads the whole session every turn reads the event written on turn 1 once on every later turn. That is where the old turn counts came from: an event at the start of a session runs out its 99 reads around turn 100, and the session average passes the old price around turn 200.

Two assumptions sit under this, and both are mine:

- **Retrieval is billed per event returned, with the 12 KB minimum.** The pricing page applies the clamp "per event" to retrieval. I did not confirm how list and pagination calls are metered. If the minimum does not apply to reads, small events get a much larger budget.
- **One read per turn.** My model reads the session once per turn. An agent that lists history before every model call inside a turn (tool loops) spends the budget faster.

As a sanity check, the model reproduces the AWS pricing example: $1.20 ingestion, $0.24 retrieval, and $0.0296 storage against AWS's $0.03 (hourly proration over a 730-hour month, decimal units).

## What the SDK actually reads

Whether your agent reloads every turn is not a guess. It is in the code. I read the Strands integration that ships in the AgentCore SDK:

- The session manager's `list_messages` asks for `MAX_FETCH_ALL_RESULTS = 10000` events when no limit is given ([session_manager.py L49, L783](https://github.com/aws/bedrock-agentcore-sdk-python/blob/99663b02a9227dcc87e85529d456685b77995561/src/bedrock_agentcore/memory/integrations/strands/session_manager.py#L783)). There is no default window.
- Strands calls it without a limit when an agent is initialized, and restores the whole list into `agent.messages` ([repository_session_manager.py L274-L292](https://github.com/strands-agents/sdk-python/blob/afc3e059b1ff932fb8f86be2d444846aa3e2a06e/strands-py/src/strands/session/repository_session_manager.py#L274-L292)). After that, new messages are only written, not read back ([L97](https://github.com/strands-agents/sdk-python/blob/afc3e059b1ff932fb8f86be2d444846aa3e2a06e/strands-py/src/strands/session/repository_session_manager.py#L97)).

So the read pattern depends on one line in your handler. **If you build a new `Agent` per request, you read the whole session every turn.** If the agent object lives for the session, you read it once per session. Same library, same feature, very different retrieval line.

One more detail from the same code: `batch_size` defaults to 1, which writes one event per message ([config.py L94](https://github.com/aws/bedrock-agentcore-sdk-python/blob/99663b02a9227dcc87e85529d456685b77995561/src/bedrock_agentcore/memory/integrations/strands/config.py#L94)). Every short message is billed as 12 KB. Setting it higher combines buffered messages into one `create_event` call, which is the lever against the minimum.

## Memory next to the tokens of the same history

The reload has two bills: memory charges to read the history, and the model charges to take it as input. I modeled 50-turn sessions with 2 events per turn and a 30-day TTL, at 100,000 sessions a month. Token rates are from the [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) on October 9 (Global cross-region, US East selected): Claude Sonnet 5.5 at $2.00 per million input tokens, and Claude Haiku 5.5 at $0.10. I used 2.5 bytes per token, from Anthropic's models overview. I ignored output tokens and the system prompt, so the token side is a floor and the memory share is a ceiling.

Fresh agent per request, full history every turn:

| Event size | Memory, new | Memory, old | History tokens, Sonnet 5.5 | History tokens, Haiku 5.5 | Largest call |
|---|---|---|---|---|---|
| 1 KB | $709/mo | $2,500/mo | $196,000/mo | $9,800/mo | 39K tokens |
| 12 KB | $720/mo | $2,500/mo | $2.35M/mo | $117,600/mo | 470K tokens |
| 64 KB | $3,839/mo | $2,500/mo | (over context) | (over context) | 2.5M tokens |

The only row where memory costs more than before is the one no model can run. At 12 KB, the memory line went from $2,500 to $720 a month while the tokens for the same history were $2.35 million with Sonnet 5.5. If that session is a cost problem, the memory pricing is not the reason.

Where memory does show up is the other end. With 1 KB messages on Haiku 5.5, memory was 6.75% of the total at the full input price, and 42% if every history token were a cache read ($0.01 per million). A last-10 window does the same thing: it cuts the tokens more than it cuts the memory reads, so memory's share goes up while the total goes down. In all of those cases the new memory price was still under a third of the old one.

## Storage is the one that does not need reads

Write-only, no readback. New cost divided by old:

| Event size | 30-day TTL | 365-day TTL |
|---|---|---|
| 12 KB | 0.05 | 0.11 |
| 64 KB | 0.28 | 0.56 |
| 256 KB | 0.36 | **1.49** |

Storage bills actual size, not the 64 KB cap. A 256 KB event kept for a year costs about 1.5 times the old flat fee, read or not, and the TTL cannot be changed after the event is written. I did not check the maximum event size, so treat the 256 KB row as a bound, not a common case. The SDK sends messages of 100,000 characters or more as blob events, so large payloads are not hypothetical. In [AgentCore Memory events, strategies, and isolation](/blog/2026-08-01-agentcore-memory-events-strategies-and-isolation.html) I said to define an event expiry for privacy reasons. That choice now has a price too.

## Limits

- **Model, not invoice.** Published rates and my assumptions, not a Cost Explorer line. I did not measure real event sizes, because reading them would itself make billed calls.
- **Token side is a floor.** No output tokens, system prompt, or tool definitions, so real memory share is lower than shown.
- **Not modeled:** long-term memory, the storage exemption for events created before October 6, and the credits.

## What to do

1. **Check how your handler builds the agent.** A new `Agent` per request means a full-history read per turn. That is the pattern that spends the re-read budget.
2. **Fix the tokens first.** If you reload full history, the model input is the bill, not memory. The sliding window and summarization advice in [Tokenomics on AWS](/blog/2026-09-23-tokenomics-on-aws-attribution-decisions.html) cuts both lines at once.
3. **If your messages are tiny, batch them.** A `batch_size` above 1 stops paying the 12 KB minimum on every short message.
4. **Keep large payloads out of short-term events,** especially with a long TTL. Store them in S3 and write a reference.
5. **Look at the AgentCore Memory usage types in Cost Explorer before December 31,** when the credits stop hiding any increase.

For the rest of an always-on agent's bill, where the infrastructure around the model can matter as much as the model, see [How much does it cost to run Hermes Agent on AWS?](/blog/2026-08-08-hermes-aws-cost-breakdown.html)

## References

- [Amazon Bedrock AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [Amazon Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) (Anthropic model rates, read 2026-10-09)
- [Anthropic models overview](https://docs.anthropic.com/en/docs/about-claude/models/overview) (context window and characters per token)
- [aws/bedrock-agentcore-sdk-python](https://github.com/aws/bedrock-agentcore-sdk-python/tree/99663b02a9227dcc87e85529d456685b77995561/src/bedrock_agentcore/memory/integrations/strands) (Strands session manager)
- [strands-agents/sdk-python](https://github.com/strands-agents/sdk-python/blob/afc3e059b1ff932fb8f86be2d444846aa3e2a06e/strands-py/src/strands/session/repository_session_manager.py)
- AWS Health notice for AgentCore short-term memory pricing changes, received October 2, 2026
- [Experiment code and raw output (yopa-experiments)](https://github.com/ypark9/yopa-experiments/tree/experiment/when-agentcore-memory-gets-more-expensive-20261009/2026-10-09-when-agentcore-memory-gets-more-expensive)
