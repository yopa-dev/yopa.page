---
title: "AWS Strands vs LangGraph on Bedrock AgentCore: Lessons from Building an Agentic Platform"
date: 2026-02-28
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "Comparing AWS Strands and LangGraph for agentic workflows on Amazon Bedrock AgentCore through hands-on PoC experience. Covers cold start gotchas, a three-tier tool architecture pattern, async tool limitations, and honest trade-offs from building a multi-tool agent on a financial SaaS platform."
categories:
  - AWS
  - AI Architecture
  - Agentic AI
tags:
  - AWS Strands
  - LangGraph
  - Bedrock AgentCore
---

> Comparing AWS Strands and LangGraph through hands-on PoC experience on Amazon Bedrock AgentCore — real cold start numbers, a three-tier tool architecture pattern, and the async tool gap that caught us off guard.

[AWS Strands Agents SDK](https://strandsagents.com/docs/user-guide/quickstart/) |
[LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/overview) |
[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)

> **Review note (2026-08-28):** The measurements and deployment observations below are a February 2026 PoC snapshot. Strands, LangGraph, and AgentCore release independently; re-check the linked documentation and package versions before copying the code into a new deployment.

> **Review note (2026-10-21):** The February PoC ran on Claude Sonnet 4 (`claude-sonnet-4-20250514`), which was retired on the Claude API on June 15, 2026 ([model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations)). The code sample was moved to Sonnet 4.6 in the August review, and the diagram label no longer names a specific version. Bedrock publishes its own model lifecycle dates, so check them in the Bedrock console or documentation. The Strands quickstart link was also updated (the old `/quickstart/python/` URL returns 404).

Most framework comparisons stop at "hello world." You read them, nod along, then hit a wall that the blog never mentioned. This post is the opposite of that. I want to share what actually happened when we ran both AWS Strands and LangGraph through PoCs on a financial SaaS platform, picked one, and started building a real multi-tool agent with it. Spoiler: we found a gap that made us rethink our confidence level.

## The Setup: Why We Needed an Agent Framework

Our platform is 100% AWS-native. The primary execution environment is **Amazon Bedrock AgentCore** — think of it as a managed runtime for AI agents with built-in memory, tool routing, and IAM-based auth. We needed to build agentic workflows that could handle 51 backend actions (knowledge base search, document extraction, custom AI actions, etc.) for financial domain customers.

Two candidates made the shortlist:

- **LangGraph** (LangChain ecosystem) — explicit state machines, large community, mature docs
- **AWS Strands** (AWS-native) — autonomous agent loop, `@tool` decorators, minimal boilerplate

We PoC'd both, picked Strands, and started building a real agent with 25+ tools on it. The story isn't as simple as "X is better." It's more like "X works great until you hit *this* wall."

## What Killed LangGraph in Our PoC

I want to be clear: LangGraph is a solid framework. The state machine model gives you explicit control over every step — when the LLM gets called, when tools execute, how results route. For complex multi-step workflows, that's powerful. But in our environment, it never got the chance to show that.

### The 30-Second Observation (Historical)

During this PoC we observed a **30-second initialization problem** when native dependencies were installed during startup. That observation should not be copied as a universal AgentCore contract: current AgentCore documentation exposes configurable runtime lifecycle settings and does not document a blanket 30-second initialization limit. LangGraph still relies on packages such as `numpy` and `pydantic-core`, so build and measure the image for your selected architecture rather than installing native wheels during a cold start.

The workaround exists: use Docker-based Lambda build containers (`public.ecr.aws/sam/build-python3.11`), pre-compile ARM64 wheels, bundle them into your CDK code assets before deployment. It works. But it also means every code change goes through a Docker build step that kills your iteration speed. For a PoC where you're experimenting rapidly, that friction adds up fast. Trust me, we tried to make it work for a while before moving on.

We confirmed this wasn't a one-time issue in our PoC — native dependency installation remained the fundamental constraint for that build. **LangGraph remained blocked for our use case at that snapshot**, unless we moved compilation into the image build or changed the dependency footprint. Re-test this conclusion against the current runtime and package versions.

### The Ecosystem Advantage is Real Though

I want to acknowledge something: LangGraph has significantly better documentation and community support. It launched earlier, so there are more reference implementations, more Stack Overflow answers, more patterns to copy. When we hit issues with Strands, the answer was often "read the Bedrock docs and figure it out." With LangGraph, someone had usually already solved it. That gap matters during the learning curve. It just didn't outweigh the deployment blocker for us.

## Strands in Practice: What We Actually Built

Here's our agent entry point. The whole thing:

```python
# agent.py — 26 lines total
from strands import Agent
from strands.models import BedrockModel

model = BedrockModel(
    model_id="global.anthropic.claude-sonnet-4-6",
    temperature=0.1,
    streaming=True,
)

agent = Agent(model=model, tools=tools, system_prompt=prompt)
result = agent(user_input)  # Autonomous loop handles everything
```

That's it. No state machine definition, no node compilation, no conditional edge routing. The agent loop decides when to call tools, when to respond, when to ask for clarification. You hand it tools and a prompt, it figures out the rest.

For comparison, the LangGraph equivalent would need roughly 80-100 lines: state class definition, chatbot node, tools node, conditional edge routing function, graph compilation, and invocation boilerplate.

**Cold starts in this PoC?** Under 500ms. We used UV bytecode compilation (`UV_COMPILE_BYTECODE=1` in our Dockerfile) and measured a prebuilt image with no native dependency compilation. Treat that number as a dated workload measurement, not an AgentCore guarantee.

### The Three-Tier Tool Architecture

This is the pattern we landed on through our PoC iterations. It wasn't planned upfront — it emerged from hitting real constraints around latency, security, and multi-tenant isolation:

```
┌─────────────────────────────────────────────┐
│        Strands Agent (Claude Sonnet)        │
└──────────────────┬──────────────────────────┘
                   │
     ┌─────────────┼─────────────────┐
     ▼             ▼                 ▼
┌─────────┐  ┌──────────┐  ┌──────────────┐
│ Direct  │  │ Gateway  │  │    Tool      │
│ Tools   │  │ Tools    │  │   Wrappers   │
│ (15×)   │  │ (10×)    │  │              │
└─────────┘  └──────────┘  └──────────────┘
│ @tool      │ MCP proto  │ Auto-inject
│ decorator  │ Lambda     │ tenant_id
│ In-process │ backends   │ Hidden from
│ execution  │ IAM auth   │ LLM context
└────────────┴────────────┴───────────────
```

**Why three tiers?**

**Direct Tools** run inside the agent container. They're simple functions decorated with `@tool` — Strands auto-extracts the JSON schema from the function signature and docstring. No manual schema definition needed. We have 15 of these for low-latency, same-tenant operations. Average: ~24 lines per tool including docstring and serialization.

Here's what a direct tool looks like (simplified from our actual implementation):

```python
@tool
def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """Search the knowledge base for relevant documents."""
    client = boto3.client("bedrock-agent-runtime")
    response = client.retrieve(
        knowledgeBaseId=os.environ["KB_ID"],
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": max_results}
        },
    )
    results = [
        {"text": r["content"]["text"], "score": r["score"]}
        for r in response["retrievalResults"]
    ]
    return json.dumps({"results": results, "count": len(results)})
```

~16 lines. In LangGraph, the same tool needs a state TypedDict, a node function, graph wiring, and compilation — roughly 40-50 lines. Multiply that by 15 tools and the difference is significant.

**Gateway Tools** go through MCP (Model Context Protocol) to Lambda backends with SigV4 authentication. These handle cross-tenant operations or operations that need their own execution context. We define them in CDK and the MCP client discovers them at runtime.

**Tool Wrappers** solve a subtle but important problem: tenant isolation. The LLM should never see or manipulate `tenant_id` directly — that's a security boundary. Wrappers auto-inject the tenant ID into tool calls before they hit the backend, keeping it invisible to the model:

```python
# Simplified wrapper pattern
def wrap_tool_with_tenant(tool_fn, tenant_id):
    @wraps(tool_fn)
    def wrapped(**kwargs):
        kwargs["tenant_id"] = tenant_id  # Injected, never from LLM
        return tool_fn(**kwargs)
    return wrapped
```

This pattern was born from a real security review, not from upfront design. The LLM was occasionally hallucinating tenant IDs in early testing — yeah, it just made up tenant IDs that looked plausible. In a financial platform, that's a nightmare. Wrappers killed that problem entirely.

## The Bedrock Memory Integration

One thing that "just worked" was Bedrock Memory. Our configuration:

- **Semantic indexing**: Auto-retrieve relevant context from past conversations
- **Summarization**: Compress long conversation histories so the context window stays manageable
- **Retention**: 90 days
- **Last K turns**: Load the 10 most recent turns on agent initialization

We use a `HookProvider` pattern (more on hooks below) to load memory on session start. The agent gets conversation context without any explicit retrieval code — Bedrock handles the vector search and summarization behind the scenes.

This is one of Strands' strongest selling points compared to LangGraph: the managed infrastructure handles memory, auth, and tool routing. With LangGraph, you'd wire each of these manually.

## The Gotchas Nobody Tells You About

Building a real agent teaches you things that docs don't.

### Container Tool Caching (High Impact)

After deploying a new Gateway Lambda function, the running AgentCore container still has **stale tool definitions**. The MCP client caches tool schemas at container startup. Your only option: wait 60-90 seconds for the container idle timeout to trigger a restart.

This sounds minor. It isn't. When you're iterating on a Gateway tool — deploy, test, see wrong behavior, realize it's stale, wait, test again — you lose 2-3 minutes per cycle. Over a day of active development, that adds up.

### Response Format Quirk

`agent.result.message` returns a dict, not a string:

```python
# What you might expect
result.message  # "Here's the extracted text..."

# What you actually get
result.message  # {"role": "assistant", "content": [{"text": "Here's the extracted text..."}]}
```

Every caller has to extract `content[*].text` blocks. It's a small thing, but when you're debugging at midnight wondering why your response is empty... you remember this one. Wish the SDK just handled it.

### boto3 and SDK compatibility

The Strands and AgentCore SDK surfaces move independently. Keep `boto3`/`botocore` and the Strands packages on versions supported by the current AgentCore deployment guide; do not preserve the old `boto3 >= 1.42.54` pin from this PoC as a universal requirement. If another service pins an older SDK, isolate the environments and run the current compatibility checks before deployment.

## The Hard Part: The Async Tool Gap

Now for the finding that changed my confidence level from "high" to "medium." This is where Strands' simplicity becomes a real limitation.

### The Problem

Our platform has dozens of backend actions. Roughly half are synchronous. **The other half are asynchronous** — things like Textract document extraction (2-5 minutes for large PDFs), async LLM inference, document intelligence processing. The async ones use a robust infrastructure: job tracking, Step Functions for polling, EventBridge for completion events.

But Strands' autonomous loop completes in a single conversation turn. When a tool returns `{"status": "pending"}`, the agent receives it, tells the user "processing...", and the conversation ends. There's no built-in mechanism to poll, wait, or resume.

Here's what actually happens in practice:

```
User: "Extract text from this document"
Agent: calls extract_document("file_id_123")
  → returns {"status": "pending", "job_id": "abc-def-..."}
Agent: "Text extraction is in progress. Please check back later."
[Agent loop ends — no mechanism to retry or wait]

User: "Is it done yet?"
Agent: calls check_job_status("abc-def-...")
  → returns {"status": "pending"}
Agent: "Still processing..."

User: [waits another minute, asks again]
Agent: calls check_job_status("abc-def-...")
  → returns {"status": "succeeded", "output": "..."}
Agent: "Here's the extracted text!"
```

The user has to manually poll. That's not a great experience.

### Why This Matters More Than It Seems

During the early PoC, this felt like a minor issue — we mostly exposed sync tools first. But looking at our actual backend, roughly half of our actions are asynchronous. Things like document processing via Textract, async LLM inference, batch data operations — these are all long-running jobs that return `pending` and complete later.

Most of these aren't exposed to the Strands agent yet. But as we expand the tool surface toward production, this architectural gap becomes central.

### The Architecture Disconnect

Our backend already has great async infrastructure. The pattern is common in AWS: when a tool kicks off a long-running job (e.g., Textract, async inference), it returns immediately with `{"status": "pending"}` and a job ID. A Step Functions state machine then polls for completion, updates the job status, and stores the result.

```
Tool invocation
  │
  ├─ Sync job? → execute → status: "succeeded" → return
  │
  └─ Async job? → validate → status: "pending"
                       │
                       ▼
                 Step Functions
                 ├─ Poll every N seconds
                 ├─ Update status: pending → running → succeeded
                 └─ Store result
```

The problem is that **Strands doesn't know about any of this**. The agent calls the tool, gets back `{"status": "pending"}`, and moves on. Step Functions completes the job in the background, but the agent is long gone.

```
┌─────────────────────────────────┐
│  Strands Agent                  │
│  call tool()                    │
│  → {"status": "pending"}        │
│  → tells user "processing..."   │
│  → loop ends ← HERE             │
└────────────────┬────────────────┘
                 │ (disconnected)
┌────────────────▼────────────────┐
│  Backend Async Infrastructure   │
│  Step Functions polling          │
│  Job: pending → succeeded        │
│  (agent is already gone)         │
└─────────────────────────────────┘
```

### Where LangGraph Would Shine

This is, honestly, where LangGraph's state machine model is genuinely superior. You can define a polling loop as a conditional edge:

```python
workflow.add_conditional_edges("poll_status", route_by_status, {
    "check_again": "poll_status",  # ← loops back
    "completed": "summarize",
    "timeout": END,
})
```

The state machine maintains `job_id`, `retries`, `status` across iterations. One user request, one final result. No manual polling.

### Our Workaround Strategy

We're not switching frameworks over this. Instead, we're taking a phased approach:

**Right now**: Accept manual polling for the few async tools we've exposed. Not ideal, but the frequency is low enough that users tolerate it.

**Next quarter**: Implement EventBridge + Bedrock Memory integration. When an async job completes, an EventBridge rule triggers a Lambda that writes the result to Bedrock Memory with a tagged key. When the user asks again, the agent checks Memory first — one follow-up instead of repeated polling.

```python
@tool
def extract_document_text(file_id: str) -> str:
    """Start async extraction. Results stored in memory on completion."""
    job_id = start_textract_async(file_id)
    # EventBridge: Textract complete → Lambda → save to Memory
    return json.dumps({
        "status": "processing",
        "message": "Extraction started. Ask me again in a minute for results."
    })

@tool
def check_extraction_result(job_id: str) -> str:
    """Check if extraction completed (reads from Memory first)."""
    result = memory_client.search(tag=f"extraction_{job_id}")
    if result:
        return json.dumps({"status": "completed", "text": result["text"]})
    return json.dumps({"status": check_job_status(job_id)})
```

**Before production**: If async tool usage looks like it'll exceed 60-70% of traffic, we'll re-evaluate LangGraph. By then, the runtime and framework versions may have changed, so repeat the image-build and lifecycle measurements instead of relying on the historical 30-second observation.

## The Numbers

Here's where the metrics stood in the February 2026 PoC:

| Metric | Value |
|--------|-------|
| Agent setup code | 26 lines (agent.py) + 79 lines (main.py) |
| Lines per tool (avg) | ~24 lines with `@tool` decorator |
| Tools implemented | 25 (15 direct + 10 Gateway) |
| Cold start | < 500ms |
| Full CDK deploy | ~8-12 min |
| Container tool refresh | ~60-90 sec after Gateway update |
| Code reduction vs LangGraph | ~3× for tool definitions |

These are workload-specific measurements, not current service-level objectives. Re-run them after changing the runtime image, region, model, or framework version.

## So, Which One Should You Pick?

If you're deploying on Bedrock AgentCore with mostly synchronous tools, **Strands is the clear winner**. The developer experience is outstanding — 26 lines for an agent, sub-500ms cold starts, and `@tool` decorator that eliminates boilerplate. The managed infrastructure (memory, auth, tool routing) saves weeks of wiring.

If your workload is async-heavy — lots of long-running jobs, polling, multi-step workflows with state — **LangGraph's state machine model is architecturally better suited**. But you'll need to solve the AgentCore deployment friction first (Docker pre-compilation, dependency bundling).

If you're somewhere in the middle like us — mostly sync today, growing async tomorrow — **start with Strands and plan your async workarounds early**. Don't wait until half your tools are async to discover the gap like we did.

The honest answer is that there's no perfect framework yet for this space. Strands trades control for simplicity. LangGraph trades simplicity for control. Both trade-offs have consequences that only show up after you've been building with them for a while.

If you're building agentic workflows on AWS and have questions about any of this, feel free to reach out. I'm still learning too, and the landscape is changing fast. Hopefully this post saves you some of that discovery time we had to go through the hard way.
