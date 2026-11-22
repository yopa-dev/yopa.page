---
title: "A Team of Bots on AgentCore: 20 Resources, and Tokens Are 98% of the Bill"
date: 2026-11-22T09:00:00-05:00
author: Yoonsoo Park
description: "I built a Grok Bot-style team of bots on Amazon Bedrock AgentCore at work: a boss bot that hands tasks to specialist bots. The minimal version synthesizes to 20 AWS resources, against 72 in the company stack it ran on. Over six days the prototype made 32 agent runs for about $2.60 to $2.98, and 98.6% of that was model tokens."
categories:
  - AI Agents
  - AWS
  - Architecture
tags:
  - Amazon Bedrock AgentCore
  - AI Agents
  - Multi-Agent
  - Cost Optimization
  - Pricing
  - measured
---

Grok Bot, xAI's teammate-style assistant, shows your bots as a roster, and the bots work together as a team. I liked that enough to build the same idea at work on Amazon Bedrock AgentCore, AWS's service for running AI agents. My prototype has a **boss bot** that can create other bots, hand them tasks, collect their reports, and ask me when it needs a decision.

Two questions came up every time I showed it:

1. **What do you actually need to build this** if you are not sitting on a big company's platform?
2. **Is a team of bots expensive?**

The company stack the prototype ran on had 72 AWS resources. Most of them are there for reasons that have nothing to do with bots: many customers, disaster recovery, a private network, central logging. So I wrote down the smallest set that still does the job, built it as a CDK stack, and priced six days of the prototype's real usage.

## Short answer

- **A bot is a row in a table, not a deployment.** One AgentCore Runtime runs every bot. Adding a bot is one DynamoDB write.
- **The minimal stack is 20 resources:** one table, one AgentCore Memory, one runtime with its role, one Lambda, and one REST API with a Cognito sign-in. I synthesized it (built the CloudFormation template on my machine). I did not deploy it.
- **The boss runs specialists inside its own process.** Asking another bot is a function call that builds a second agent in memory, not a network call between services.
- **The money is the model.** Six days, 32 agent runs, about 395,000 tokens: **$2.60 to $2.98**, and **98.6%** of it was model tokens. The runtime and memory together were about **4 cents**. One request that went boss → 3 specialists took 121 seconds and cost **$0.62 to $0.68**.
- **Four defaults broke things:** a 60-second Lambda timeout, a 4,096-token output cap, one shared session per specialist, and failed runs that left no record.

Code and output: [yopa-experiments `experiment/agentcore-bot-team-minimal-stack-20261122`](https://github.com/ypark9/yopa-experiments/tree/experiment/agentcore-bot-team-minimal-stack-20261122/2026-11-22-agentcore-bot-team-minimal-stack) (commit [`3b43f32`](https://github.com/ypark9/yopa-experiments/commit/3b43f3204055b05ce59998ea8af7ecdf21940ec0)).

## Terms

| Term | Meaning here |
|---|---|
| AgentCore Runtime | AWS's managed host for agent code. It starts a small virtual machine (a microVM) per conversation and calls your HTTP server inside it. |
| AgentCore Memory | AWS's store for conversation events. "Short-term" memory is the raw turns the model reads back on the next turn. |
| Session | One conversation. The runtime keeps one microVM per session ID. |
| SSE | Server-sent events: a response that arrives as many small `data:` lines instead of one body, so the answer shows up while it is being written. |
| Boss bot, specialist | The bot you talk to, and the bots it hands work to. All of them are the same kind of agent with a different prompt and different tools. |
| Inference profile | A Bedrock model ID that also picks where calls run. `us.anthropic.claude-opus-5-5` routes within US regions. |
| CDK synth | Turning CDK code into a CloudFormation template on your machine. It creates nothing in AWS. |

## How one question travels

Say you ask the boss bot "find yesterday's failed runs." Here is every step, the resource it needs, and what breaks without it.

| Step | What happens | Resource | Without it |
|---|---|---|---|
| 1 | The browser sends the question with a sign-in token | Cognito + API Gateway | You don't know who asked, and a browser can't call AWS APIs directly |
| 2 | API Gateway passes it to a Lambda | Lambda | Nothing calls the runtime |
| 3 | The Lambda calls `InvokeAgentRuntime` with a session ID, the prompt, the bot ID, and a header with the user | `bedrock-agentcore:InvokeAgentRuntime` on the Lambda's role | Access denied |
| 4 | AgentCore starts (or reuses) the session's microVM and sends `POST /invocations` to port 8080 | AgentCore Runtime | No place to run. Without the header allowlist, your code never sees the user |
| 5 | The code reads the boss's row and its tools' rows | DynamoDB table | The boss has no prompt and no tools |
| 6 | It reads the conversation so far | AgentCore Memory | The bot forgets the last turn |
| 7 | The boss calls the model | Bedrock permissions on the runtime's role | No answer |
| 8 | The boss calls `ask_bot`. A second agent is built **in the same process** with the specialist's prompt and tools | none | — |
| 9 | The answer streams back as SSE through the Lambda and API Gateway | 15-minute timeouts on both | Anything longer than a minute stops on screen with no error (this happened to me) |

**Takeaway:** step 8 is why the resource count stays flat. Ten bots or a hundred, the AWS side does not change.

## The minimal stack: 20 resources

The whole stack is [`cdk/app.mjs`](https://github.com/ypark9/yopa-experiments/blob/3b43f3204055b05ce59998ea8af7ecdf21940ec0/2026-11-22-agentcore-bot-team-minimal-stack/cdk/app.mjs), about 100 lines. The part that matters most is the runtime:

```js
const runtime = new Runtime(stack, 'BotRuntime', {
  runtimeName: 'bot_team_runtime',
  agentRuntimeArtifact: AgentRuntimeArtifact.fromCodeAsset({
    path: path.join(here, '..', 'runtime'),
    runtime: AgentCoreRuntime.NODE_22,
    entrypoint: ['index.js']
  }),
  executionRole: role,
  networkConfiguration: RuntimeNetworkConfiguration.usingPublicNetwork(),
  lifecycleConfiguration: { idleRuntimeSessionTimeout: Duration.minutes(15) },
  requestHeaderConfiguration: { allowlistedHeaders: ['X-Amzn-Bedrock-AgentCore-Runtime-Custom-user'] },
  environmentVariables: { TABLE_NAME: table.tableName, MEMORY_ID: memory.memoryId }
});
```

In plain words:

- `fromCodeAsset` uploads a folder of JavaScript instead of a container image. No ECR repository needed.
- `usingPublicNetwork()` skips the VPC. Company accounts often must use one; a bot team does not need it.
- `idleRuntimeSessionTimeout` keeps a conversation's microVM warm for 15 minutes after the last message.
- `allowlistedHeaders` is the one setting people miss. The [AgentCore docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html) describe this list as what forwards custom headers to your code (up to 20 headers, 10 KB each). The company stack lists every header it passes, including the user.

The front door needs two 15-minute settings, one on the Lambda (`timeout: Duration.minutes(15)`) and one on the API Gateway integration:

```js
defaultIntegration: new apigw.LambdaIntegration(api, {
  responseTransferMode: apigw.ResponseTransferMode.STREAM,
  timeout: Duration.minutes(15)
}),
```

`npm run synth` with aws-cdk-lib 2.275.0 produced this template:

| Group | What is in it | Resources |
|---|---|---|
| Bots and history | DynamoDB table (with one index to list bots), AgentCore Memory | 2 |
| Agent host | AgentCore Runtime, its execution role and policy, and a service role the Memory construct creates | 4 |
| Front door | Lambda, its role and policy, and two invoke permissions (one for the API, one for the console's test button) | 5 |
| HTTPS and sign-in | REST API, two paths (`/v1`, `/v1/{proxy+}`), one method, a deployment, a stage, a Cognito authorizer, a user pool, and its client | 9 |
| **Total** | | **20** |

Two CDK defaults would have added resources that are not about bots. `TableV2` synthesizes as a `AWS::DynamoDB::GlobalTable` even with one region, so I used `Table`. And a `RestApi` creates an account-wide API Gateway logging role unless you pass `cloudWatchRole: false`; that is 2 resources for a setting that belongs to the whole AWS account, not this app.

**Takeaway:** synth proves the template builds. It does not prove the runtime starts, that the public network reaches Bedrock, or that a 15-minute stream survives API Gateway with a Cognito authorizer. The company stack did run the runtime and 15-minute streams through API Gateway, but inside a VPC and with a different authorizer.

## What the company stack added

The prototype ran on a shared agent platform at work. Its six CloudFormation stacks held 72 resources (not counting CDK's metadata). I counted them by type and asked of each one: would a bot team break without it?

| What was added | Resources | Why a company platform has it | For a bot team |
|---|---|---|---|
| Log delivery: a source, a destination and a delivery for 7 log types across the runtime, memory and an MCP gateway | 21, plus 4 log groups | Central logs and traces | Skip it. The runtime's stdout already lands in `/aws/bedrock-agentcore/runtimes/<name>-DEFAULT`, which is where I read every token count below |
| A shared IAM stack | 9 | Company-wide permission plumbing | Not needed |
| A private network: a VPC lookup plus a custom resource that picks subnets in the zones AgentCore supports | 6 (1 custom resource, 2 Lambdas, 2 roles, 1 log group) | Company accounts must run inside a VPC | `usingPublicNetwork()` |
| A second role the runtime assumes for each customer | 1 role and its policy | Credentials limited to one customer | One customer, one role |
| An MCP gateway and its role | 2 | Tools added later | The agent code never called it |
| Blue/green API stages | 2 stages, 2 deployments | Deploys with no downtime | One stage |

Some of the platform does not show up in that count because it lives in other services: a central registry that decides which models a product may call, a separate service that stores run metrics and session lists, and table replicas in other regions for production. For a bot team, put the inference profile ID on the bot's row, write your own run record, and use one region.

**Takeaway:** most of the difference is log delivery (21), the shared IAM stack (9) and private networking (6). None of it decides whether the bots work.

## The runtime contract in 50 lines

AgentCore Runtime calls one HTTP server inside the microVM. [`runtime/index.js`](https://github.com/ypark9/yopa-experiments/blob/3b43f3204055b05ce59998ea8af7ecdf21940ec0/2026-11-22-agentcore-bot-team-minimal-stack/runtime/index.js) is the smallest server I could write that follows the contract, with Node's built-in `http` module only. A real one calls a model where this one echoes the prompt:

```js
const SESSION_HEADER = 'x-amzn-bedrock-agentcore-runtime-session-id';
const REQUEST_HEADER = 'x-amzn-bedrock-agentcore-runtime-request-id';
// Custom headers reach this code only if the runtime allowlists them.
const USER_HEADER = 'x-amzn-bedrock-agentcore-runtime-custom-user';

// ... inside the request handler, for POST /invocations:
const sessionId = req.headers[SESSION_HEADER];
if (!sessionId) {
  return json(res, 400, { error: `missing header ${SESSION_HEADER}` });
}
const requestId = req.headers[REQUEST_HEADER] ?? randomUUID();
// ...
res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
const send = (event) => res.write(`data: ${JSON.stringify(event)}\n\n`);
```

`check.sh` starts it on a local port and sends four requests. What came back:

| Request | What came back | What it means |
|---|---|---|
| `GET /ping` | 200, `{"status":"Healthy"}` | AgentCore's health check would pass |
| `POST /invocations` with a session header and `...-Custom-user: user-1` | 200, `text/event-stream`: a start event with `"user":"user-1"`, five text events, an end event | The stream works and the custom header arrived |
| `POST /invocations` with no session header | 400, `missing header x-amzn-bedrock-agentcore-runtime-session-id` | AgentCore always sends it, so its absence means a bad caller |
| `POST /invocations` with a body that is not JSON | 400, `body must be JSON` | Bad input fails loudly instead of sending an empty prompt to the model |

One thing the local check cannot show, which I learned on the prototype: **one session is one microVM**, so anything your code keeps in module scope belongs to one conversation. That makes it safe to build the agent once per process and reuse it for every turn of that conversation.

## The team is code, not infrastructure

The boss gets three tools, and each is a few lines over the table and the model:

- **`list_bots`**: a query on the table's index for every bot in the environment.
- **`create_bots`**: one conditional write per bot (`attribute_not_exists(PK)`, so an existing bot is never overwritten). The tool needs approval, and I approve the whole proposed team once.
- **`ask_bot`**: loads the specialist's row and tools, builds a second agent in the same process with the specialist's prompt, gives it its own Memory session, runs the task, and returns the reply with a status line: `done`, `blocked` or `needs_user`.

The rows look like this (simplified):

```
bot   PK = BOT#<botId>    SK = META   GSI1PK = BOTS    GSI1SK = <botId>
      name, prompt, modelId (an inference profile ID), toolIds, status
tool  PK = TOOL#<toolId>  SK = META   GSI1PK = TOOLS   GSI1SK = <toolId>
      type, reference (list_bots, ask_bot, ...), description, needsApproval
```

Two rules kept the team from going wrong. Specialists do not get tools that need approval, because nobody is there to approve inside a task. And specialists do not get the team tools, so a specialist cannot start its own chain of bots.

## Four defaults that broke

The bots found the last two themselves, by reading their own run records.

| What I saw | Why | What to set |
|---|---|---|
| Any answer longer than a minute stopped on screen, with no error | API Gateway waited 15 minutes, but the Lambda kept the 60-second default | 15 minutes on both, plus an idle check in the UI |
| Specialists failed with "Model reached maximum token limit" | No one set `maxTokens`, so Bedrock's default of 4,096 output tokens applied | Set it yourself (I used 16,000 for specialists) |
| When the boss gave one specialist two tasks at once, the second disappeared from history | The specialist's session ID came from (boss session, bot ID), so both tasks shared one session | Add the tool call's ID to the session ID, or give a bot one task at a time |
| Run history said 0 failures while two runs had failed | Runs were recorded only on success; a run that failed and was retried left nothing | Write the run record in a `finally` block, with the status and the error |

## Where the money goes

I read six days of the prototype's usage (2026-11-17 to 2026-11-22): token counts from the runtime's trace spans in its log group, CPU and memory from the CloudWatch metrics `CPUUsed-vCPUHours` and `MemoryUsed-GBHours`, and the Memory event count from `list-events`.

| What | Measured over six days |
|---|---|
| Agent runs | 32 (57 model calls: 50 to Claude Opus 5.5, 7 to Claude Sonnet 5.5) |
| Tokens | 326,029 in, 68,813 out, no cache hits |
| Runtime CPU | 0.048827 vCPU-hours |
| Runtime memory | 3.31473 GB-hours |
| Memory events written | 112 |

Prices on 2026-11-22: Claude Opus 5.5 is $4 per million input tokens and $20 per million output tokens, Claude Sonnet 5.5 is $2 and $10 ([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)), and Bedrock's regional endpoints such as `us.` cost 10% more than global ones (same page). AgentCore Runtime on the v1 platform is $0.0895 per vCPU-hour and $0.00945 per GB-hour, with no CPU charge while the code waits on the model; Memory is $1 per GB written, each event counted as 12 KB to 64 KB ([AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)).

| Part | Six days | Share of the total |
|---|---|---|
| Model tokens | $2.57 to $2.94 | **98.6%** |
| AgentCore Runtime | $0.036 (0.048827 × $0.0895 + 3.31473 × $0.00945) | about 1.2% to 1.4% |
| AgentCore Memory | $0.001 to $0.007 | under 0.3% |
| **Total** | **$2.60 to $2.98** | |

The range has two causes. The low end is list price on the 57 model calls. The high end adds the 10% regional premium and 4,440 input and 4,427 output tokens that the agent-run records counted but the model-call records did not, priced as Opus.

One request, boss → 3 specialists, all on Opus 5.5:

| Bot | Tokens in / out | Cost |
|---|---|---|
| Boss | 21,194 / 2,945 | $0.14 to $0.16 |
| Monitor (finds suspicious runs) | 9,267 / 4,185 | $0.12 to $0.13 |
| Root cause 1 (reads one session) | 22,976 / 4,363 | $0.18 to $0.20 |
| Root cause 2 (reads another session) | 21,245 / 4,556 | $0.18 to $0.19 |
| **Total, 121 seconds** | **74,682 / 16,049** | **$0.62 to $0.68** |

The runtime's share of that request is about $0.002: the six days' runtime cost spread over 15 sessions.

**Takeaways:**

- **Cost follows questions, not bots.** A bot nobody talks to has no session, so it costs nothing to run, and the table is on-demand.
- **The bots that read are the expensive ones.** Each root-cause bot read a session's history, and that made 21,000 to 23,000 input tokens.
- **The boss's context grows with every report.** Short reports are the cheapest optimization.
- **Check which account pays for the model.** The prototype called models through inference profiles owned by a different AWS account than the runtime. So 98.6% of the cost landed in that account, and the runtime's account looked almost free.
- **For scale (arithmetic, not measured):** 20 of those requests a day is about $12.40 to $13.60 a day.

Cost of this post by environment: local, my laptop's CPU for the checks and the synth. CI, the `identifier-check` job in yopa-experiments and this repo's pull request checks. Cloud, no new AWS calls; the usage above was already spent by the prototype. Billing, list-price arithmetic, not an invoice.

## What this does not show

- **The minimal stack was not deployed.** Public networking, the streaming API with Cognito, and the placeholder Lambda were not run.
- **The usage is one prototype, one user, six days**, mostly on Opus. It is not a load test.
- **Whether a team answers better than one agent with all the tools** is a different question. I have a test plan for it, not a result.
- **Lambda, API Gateway, DynamoDB and log storage costs were not measured.** At this volume they should be small, but that is a guess.
- **CloudWatch's daily data points were one day off from the log timestamps,** so I used only the six-day totals.
- **Prices change.** All prices are from 2026-11-22.

## Who should check what

- **Planning a multi-agent product on AgentCore:** budget for tokens, not infrastructure, and record tokens per bot from the first day.
- **Inheriting a company agent platform:** count which resources serve the bots and which serve the company. Mine had 72; the bot-critical part fit in a 20-resource stack.
- **Before the first demo:** set the four defaults in the table above. Every one of them failed silently or looked like success.

For how AgentCore Memory's per-GB pricing behaves next to token costs, see [When AgentCore Memory's New Pricing Costs More](/blog/2026-10-09-when-agentcore-memory-gets-more-expensive.html). For where AgentCore's services fit in production, see [the AgentCore service map](/blog/2026-08-01-agentcore-service-map-and-production-boundaries.html).
