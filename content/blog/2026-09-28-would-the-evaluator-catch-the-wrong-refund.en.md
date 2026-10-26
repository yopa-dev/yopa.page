---
title: "Would the evaluator catch the $40 refund? I ran AWS's own example"
date: 2026-09-28T09:00:00-04:00
author: Yoonsoo Park
description: "AWS's launch essay for CloudWatch Omni opens with a refund agent that says $40 when the policy says $140. I built that agent and scored 30 runs with the AgentCore built-in evaluators. Without ground truth, every evaluator gave the wrong answer a perfect score. Here is why, what does catch it, and one more gap I did not expect."
categories:
  - AI Agents
  - AWS
tags:
  - evaluations
  - amazon-bedrock-agentcore
  - observability
  - ai-agents
  - measured
aliases:
  - /blog/2026-09-24-agent-observability-correctness-not-uptime.html
---

AWS launched [Amazon CloudWatch Omni](https://aws.amazon.com/cloudwatch/omni/) last week, and the essay that came with it, [Wrong, not broken](https://aws.amazon.com/blogs/aws-insights/wrong-not-broken/) by Matt Wood, opens with a good example. A refund agent answers in 600 ms with zero errors and tells a customer they are owed $40. The policy says $140. The agent pulled last quarter's version of the document. Every dashboard is green, and the answer is wrong.

The essay's point is that agent correctness has to be measured per run, in production, and Omni ships 17 built-in evaluators to do it. That is a fair point. But the example made me want to ask a narrower question, one the essay does not answer:

**If you point the built-in evaluators at that exact run, do they catch it?**

So I built the agent and scored it. Short answer: without ground truth, no. Not once in 10 tries. Every evaluator I tried gave the $40 answer a passing score, most of them a perfect one.

## The setup

A small [Strands](https://strandsagents.com) agent on Claude Haiku 4.5, with one tool, `search_policy_docs`. The customer asks: "I'm on the Pro plan and I cancelled 10 days after my renewal. How much refund am I owed?"

Three conditions, 10 runs each:

| Condition | What the tool returns | What the agent should say |
|---|---|---|
| stale | the Q2 policy: "$40 refund" (the essay's case) | $140, but it cannot know that |
| fresh | the Q3 policy: "$140 refund" | $140 |
| fee (control) | the Q3 policy, and the system prompt adds "deduct a $20 processing fee" | an answer that contradicts the document |

I captured each run's spans in memory, converted them with the AgentCore SDK's Strands converter, and sent them to the AgentCore `Evaluate` API. Omni lists the AgentCore built-in evaluators as one of its evaluator options, so these are those judges. Nothing went to CloudWatch. I used four evaluators with no ground truth, which is what online evaluation of production traffic looks like, plus two with ground truth.

The code and all 30 raw results are in [yopa-experiments](https://github.com/ypark9/yopa-experiments/tree/main/2026-09-28-would-the-evaluator-catch-the-wrong-refund).

## The results

The agent was very consistent: $40 in all 10 stale runs, $140 in all 10 fresh runs, $120 in all 10 fee runs. The scores, with "pass" meaning a score of 0.7 or higher:

| Evaluator | Ground truth | stale ($40, wrong) | fresh ($140, right) | fee ($120, contradicts doc) |
|---|---|---|---|---|
| `Builtin.Correctness` | none | **1.00, 10/10 pass** | 1.00, 10/10 | 0.50, 0/10 |
| `Builtin.Faithfulness` | none | **1.00, 10/10 pass** | 1.00, 10/10 | 0.35, 2/10 |
| `Builtin.Helpfulness` | none | **0.86, 10/10 pass** | 0.92, 10/10 | 0.17, 0/10 |
| `Builtin.GoalSuccessRate` | none | **1.00, 10/10 pass** | 1.00, 10/10 | 0.00, 0/10 |
| `Builtin.Correctness` | expected response "$140" | 0.00, 0/10 | 1.00, 10/10 | 0.00, 0/10 |
| `Builtin.GoalSuccessRate` | assertion "told them $140" | 0.00, 0/10 | 1.00, 10/10 | 0.00, 0/10 |

The wrong answer and the right answer are indistinguishable until you give the judge the answer. The control shows the evaluators are not rubber stamps: when the response contradicts the document in front of them, all four mark it down. Three fail it every time, and Faithfulness fails it 8 times out of 10.

## Why: without ground truth, "correct" means "matches the tool output"

The judges explain their scores, and the explanations make the mechanism plain. Here is `Builtin.Correctness` on a stale run, with no ground truth:

> The tool output states: 'Pro plan: if you cancel within 30 days of renewal, you get a refund of $40.' ... The candidate response correctly identifies ... the refund amount is $40 ... All factual claims ... Perfectly Correct.

All 40 no-ground-truth explanations on stale runs cite the tool output or the policy. None of them question it. The document said "version 2026-Q2, effective 2026-04-01" in plain text, and not one explanation mentioned the version or the date.

That is not a bug in the judge. Without a reference, the only thing it can check the answer against is what is in the trace. A stale document is invisible from inside the run, because inside the run it is the truth. The AgentCore docs say as much: custom evaluators that use ground truth "cannot be used in online evaluation configurations, because online evaluations monitor live production traffic where ground truth values are not available."

So the essay's opening example is exactly the kind of wrong that online evaluation, by itself, cannot see.

## What does catch it

Only ground truth did: `Builtin.Correctness` with an expected response, or `Builtin.GoalSuccessRate` with an assertion. Both scored 0 on every stale run. But you do not have ground truth for live traffic. You have it for a dataset. So in practice:

- **Offline, with a golden set.** Keep a set of questions with known answers ("Pro plan, 10 days after renewal: $140") and score every deploy against it. When the policy changes, the golden set has to change too, or it will now fail the correct agent.
- **Check the source, not the answer.** The failure happened at retrieval. A check that the retrieved document is the current version (an effective date, a version field, a "superseded by" flag) catches this before the model ever sees it. That is a data check, not an evaluator.
- **Turn bad runs into test cases.** Omni's pitch here is right: a bad production run can become a dataset entry. But notice the order. Someone has to find the bad run first, and on this evidence the online scores will not point to it.

Pro: online evaluators do catch an agent that contradicts its own sources, like the fee control, or goes off topic.
Con: they cannot catch an agent that faithfully repeats a wrong source, and that is the failure the launch essay led with.

## One more gap: the judge never saw the system prompt

The fee control had a second surprise. The $20 fee came from my system prompt, a stand-in for a business rule. The judges called it "fabricated" in 52 of 60 explanations, and none of them mentioned an instruction or a system prompt.

So I checked what reached the judge. The raw spans from Strands contain the system prompt. The ADOT (AWS Distro for OpenTelemetry) documents produced by the SDK's `convert_strands_to_adot`, which is what I sent to `Evaluate`, do not. The rule was dropped in the conversion, so the judge scored the answer against the tool output alone.

In this experiment the rule was made up and "fabricated" is a fair reading. But if your real business rules live in the system prompt ("never refund more than $500 without approval"), an evaluator on this path will not know they exist. It will mark rule-following answers as unsupported. I only tested the in-memory path. Spans that go through CloudWatch may carry more, so check what your own path sends before you trust a faithfulness score.

## Limits

- One task, one model, 10 runs per condition. The agent answered the same way every time, so more runs would not change the split, but other tasks might.
- These are the AgentCore built-in evaluators through the `Evaluate` API. Omni also lets you plug in Braintrust, DeepEval, Ragas, or your own judge. A custom judge that knows your policy calendar could do better. That is the point: someone has to give it that knowledge.
- I did not test Omni's own console or online evaluation configuration, only the same evaluators on the same spans.

## What to take from it

The essay is right that error rate is not a quality metric. But a quality score from an online evaluator is not a correctness guarantee either. Without ground truth it measures whether the answer matches the context, and stale context produces answers that match perfectly.

If a wrong answer costs you more than a slow one, you need three things, not one: a golden set with known answers, a freshness check on what retrieval returns, and online scores for the failures they can actually see. For the plumbing underneath, how spans and scores flow through CloudWatch and the pitfalls that break it, see [Observing Bedrock AgentCore evaluations](/blog/2026-09-12-observing-bedrock-agentcore-evaluations.html). For where the agent's boundaries should sit in the first place, see [the AgentCore service map](/blog/2026-08-01-agentcore-service-map-and-production-boundaries.html).

## References

- [Wrong, not broken](https://aws.amazon.com/blogs/aws-insights/wrong-not-broken/) (AWS Insights, Matt Wood, 2026-09-23)
- [Introducing Amazon CloudWatch Omni](https://aws.amazon.com/blogs/aws/introducing-amazon-cloudwatch-omni-ai-powered-observability-for-generative-ai-and-agentic-workloads/) (AWS News Blog)
- [AgentCore ground truth evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html)
- [Getting started with on-demand evaluation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-on-demand.html)
- Experiment code and raw results: [yopa-experiments](https://github.com/ypark9/yopa-experiments/tree/main/2026-09-28-would-the-evaluator-catch-the-wrong-refund)
