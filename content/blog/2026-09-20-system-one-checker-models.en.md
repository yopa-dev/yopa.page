---
title: "A Model That Only Judges: Where Calibrated Yes/No Actually Pays Off"
date: 2026-09-20T09:00:00-04:00
author: Yoonsoo Park
description: "TypeSafe shipped Jev, a model that generates no text and returns calibrated yes/no probabilities instead. The interesting part is not the type-safe output. It is that a calibrated probability is the first number your code can actually put an if statement on. Here is the mental model and one concrete place it earns its keep: the relevance gate in a RAG pipeline."
categories:
  - AI
  - Architecture
tags:
  - ai-agents
  - rag
  - calibration
  - retrieval
  - llm-architecture
---

TypeSafe AI shipped a model called Jev in September 2026. It does not write sentences. You hand it a block of program state and a set of typed questions, and it returns choices, scores, and probabilities in one parallel pass. They call the class "System One," after Kahneman's fast, intuitive judgment engine.

When I first read the announcement I made the same mistake most people make. I thought the point was type safety: a model whose output slots cleanly into the next piece of software without the usual "please respond only with valid JSON" ceremony. That is real, but it is a side effect. It is not why this matters.

The reason it matters took me a second read to see, and once I saw it I could not un-see it. So let me try to save you the second read.

## What the model actually returns

Three primitives.

- **Noul**: a yes/no question answered as a single probability between 0 and 1. Not "yes" plus a separate confidence field. The number itself is the belief.
- **Choice**: pick one of N labeled options, with a confidence.
- **Score**: a number in a range, with a confidence.

One important constraint: the questions cannot see each other's answers. If a decision depends on three factors, you ask about each factor separately and you combine them in your own code. That sounds like a limitation. It is actually the whole design philosophy, and I will come back to it.

## The part that is easy to miss

Here is the claim that reframed the whole thing for me:

**A calibrated probability is the first number your code can actually put an `if` statement on.**

Think about what happens when you ask a normal chat model "on a scale of 0 to 10, how confident are you?" It writes a number. That number is not calibrated. When the model says "9 out of 10," it is not actually right nine times out of ten. It just wrote the digit 9. So you cannot threshold on it. You end up either sending everything to a human, or paying to run the big model on everything, because you have no trustworthy signal to branch on.

TypeSafe trained Jev with a method they call RLCD, reinforcement learning for calibrated decisions. The goal is that when it says 0.9, it is right about nine times out of ten. Like a good weather forecast: if it rains on roughly 70 out of every 100 days you called at 70 percent, the forecast is calibrated.

If that holds, then for the first time this works and means something:

```python
if answer.noul > 0.98:
    auto_act()            # no human, no bigger model
elif answer.noul < 0.05:
    auto_reject()
else:
    escalate()            # send to a human or a slower reasoning model
```

Those five lines are the product. Automate the confident majority, escalate the ambiguous minority. Without calibration the code is standing on a lie. With it, the code is standing on something real.

## Why one example never convinces you

When I tried to think of a killer use case, nothing came. And I think that is because the value does not live in any single judgment. It lives in the volume of judgments.

The company named the model after William Jevons, the economist who noticed that when steam engines got more efficient, England burned more coal, not less. Make a thing cheap enough and you use vastly more of it. When a judgment costs a fraction of a cent and comes back in under half a second, you start putting judgments in places you never would have paid for before. A yes/no on every log line. A risk score on every commit. A relevance check on every retrieved chunk. Those were all too slow and too expensive to run through a full language model, so nobody did them. Now you can.

So instead of hunting for the one magic case, look at the shape of the problem: is it a narrow, repeated, atomic judgment that some code downstream wants to branch on? If yes, it is a candidate.

## One concrete place it earns its keep: the RAG relevance gate

If you have read my [architectural decision guide for vector databases in RAG](/blog/2025-05-25-aws-vector-databases-rag-applications-complete-architectural-decision-guide.html), you know I care a lot about what actually ends up in the context window. This is a new tool for exactly that problem.

A typical retrieval pipeline looks like this:

```
query -> embedding search (top 50) -> reranker (top 8) -> stuff into the LLM
```

The embedding search and the cross-encoder reranker both answer one question: *is this chunk semantically close to the query?* But "close" is not the same as "actually answers the question." A chunk can be embedding-close and still contain no answer. That gap is a leading cause of RAG getting things wrong, because the junk chunk goes into the context and the model dutifully tries to use it.

A checker model sits after the reranker, not instead of it, and asks the questions the reranker cannot:

```python
for chunk in reranked_chunks:               # the reranker's top 8, not the raw 50
    r = client.system_one(
        state={"query": user_query, "chunk": chunk.text},
        questions={
            "answers":   noul("This chunk contains information that directly answers the query"),
            "on_topic":  noul("This chunk is about the same entity as the query"),
            "relevance": score("How useful is this chunk for answering the query", min=0, max=10),
            "stale":     noul("This chunk looks outdated or superseded"),
        },
    )
    chunk.judgment = r
```

Then your own code, not a prompt, decides what survives:

```python
keep = [c for c in reranked_chunks
        if c.judgment.nouls["answers"].noul > 0.7
        and c.judgment.nouls["stale"].noul < 0.6]

keep.sort(key=lambda c: c.judgment.scores["relevance"].score, reverse=True)
context = keep[:5]
```

Three things fall out of this that I like.

First, the cut is on "does this answer the question," not on "is this close." Because the `answers` probability is calibrated, `> 0.7` means something stable across queries. A raw reranker score does not give you that; 0.8 from one reranker is not 0.8 from another.

Second, you stop padding the context with garbage. If only two chunks clear the bar, you send two, not a top-five where three seats are filled with near-misses. Fewer distractors in the context is one of the cheapest wins in RAG quality.

Third, the policy lives in code you can read and test. The threshold, the staleness rule, the entity check: those are `if` statements with unit tests, not sentences buried in a prompt you tune by feel.

### Where the checker is the wrong tool

It is not a ranker. It scores each chunk independently, because the questions cannot see each other. So it cannot tell you that chunk A is a better answer than chunk B; it can only tell you that each one, on its own, is or is not an answer. Keep the cross-encoder for fine ordering. Use the checker for the pass/fail gate and a rough usefulness score. They are different jobs and they compose.

And the calls fan out per chunk, so gate on the reranker's shortlist, not the raw top-50. Cheap is not free.

## The maker/checker split

Step back and the pattern is bigger than retrieval. This model cannot be the maker. It cannot write the answer, draft the code, or compose the summary. It is shaped like a checker. So the useful architecture is a loop with two roles that already existed, where only the checker changes class: your language model still generates, and a fast calibrated judge decides whether the output is good enough to ship, needs a rewrite, or needs a human. A claim is not a proof. The checker is where you turn a claim into a decision your code can act on.

## What I would actually do

Do not migrate anything this week. The model is days old and the eye-popping numbers (near-zero structured-output errors, hundreds of times cheaper and faster) are the vendor's own, self-run and not yet reproduced by anyone else.

Shadow it. Pin the version, keep your existing path warm, and run the checker's judgments in parallel without letting them gate anything. Log what it would have done. After a few days, look at whether the chunks it wanted to drop were in fact never used in a good answer, and whether the candidates it wanted to auto-approve were actually right. If the calibration holds up against your own data, then promote it to a real gate. If it does not, you have lost nothing but some log storage.

The idea is sound even if this particular model turns out to be early. A cheap, calibrated, text-free judge is a genuinely new building block, and the place it goes is on the boundary: between the model that generates and the code that decides. That boundary has been the soft spot in every agent system I have built. It is nice to finally have a part shaped to fit it.
