---
title: "A Team of Bots on AgentCore: Start With 20 Resources, Budget for Tokens"
date: 2026-11-22T09:00:00-05:00
author: Yoonsoo Park
description: "How to build a Grok Bot-style team of bots on Amazon Bedrock AgentCore, where a lead bot hands tasks to specialist bots. The starter stack is 20 AWS resources. Six days of my prototype cost about $2.60 to $2.98, and 98.6% of that was model tokens. Also: four defaults to fix on day one, and what to add before production."
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

Grok Bot, xAI's teammate-style assistant, shows your bots as a roster, and the bots work together as a team. I wanted the same thing on AWS, so I built a prototype on Amazon Bedrock AgentCore, AWS's service for running AI agents. It has a **lead bot** that can create other bots, hand them tasks, collect their reports, and ask me when it needs a decision.

This is the guide I wanted before I started. It answers three questions:

1. **What is the smallest stack that works?**
2. **What does a team of bots cost to run?**
3. **What do you add before other people use it?**

## Short answer

- **A bot is a row in a table, not a deployment.** One AgentCore Runtime runs every bot. Adding a bot is one DynamoDB write.
- **Start with 20 resources:** one table, one AgentCore Memory, one runtime with its role, one Lambda, and one REST API with a Cognito sign-in. I synthesized this stack (built the CloudFormation template on my machine). I did not deploy it.
- **The lead runs specialists inside its own process.** Asking another bot is a function call that builds a second agent in memory, not a network call between services.
- **Budget for tokens, not infrastructure.** Six days of my prototype, 32 agent runs and about 395,000 tokens, cost **$2.60 to $2.98**, and **98.6%** of it was model tokens. The runtime and memory together were about **4 cents**. One request that went lead → 3 specialists took 121 seconds and cost **$0.62 to $0.68**.
- **Fix four defaults on day one:** a 60-second Lambda timeout, a 4,096-token output cap, one shared session per specialist, and failed runs that leave no record.
- **Production is a list of additions, not a rewrite:** real sign-in, approvals, trusted run records, cost limits, logs and traces, customer isolation, private networking, data retention, safe deploys. The checklist at the end says when each one starts to matter.

Code and output: [yopa-experiments `experiment/agentcore-bot-team-start-to-production-20261122`](https://github.com/ypark9/yopa-experiments/tree/experiment/agentcore-bot-team-start-to-production-20261122/2026-11-22-agentcore-bot-team-start-to-production) (commit [`8a2f96b`](https://github.com/ypark9/yopa-experiments/commit/8a2f96be85077f3ffc83d89e776c4b147eb9d152)).

## Terms

| Term | Meaning here |
|---|---|
| AgentCore Runtime | AWS's managed host for agent code. It starts a small virtual machine (a microVM) per conversation and calls your HTTP server inside it. |
| AgentCore Memory | AWS's store for conversation events. "Short-term" memory is the raw turns the model reads back on the next turn. |
| Session | One conversation. The runtime keeps one microVM per session ID. |
| SSE | Server-sent events: a response that arrives as many small `data:` lines instead of one body, so the answer shows up while it is being written. |
| Lead bot, specialist | The bot you talk to, and the bots it hands work to. All of them are the same kind of agent with a different prompt and different tools. |
| Inference profile | A Bedrock model ID that also picks where calls run. `us.anthropic.claude-opus-5-5` routes within US regions. |
| CDK synth | Turning CDK code into a CloudFormation template on your machine. It creates nothing in AWS. |

## 1. How one question travels

Say you ask the lead bot "find yesterday's failed runs." Here is every step, the resource it needs, and what breaks without it.

| Step | What happens | Resource | Without it |
|---|---|---|---|
| 1 | The browser sends the question with a sign-in token | Cognito + API Gateway | You don't know who asked, and a browser can't call AWS APIs directly |
| 2 | API Gateway passes it to a Lambda | Lambda | Nothing calls the runtime |
| 3 | The Lambda calls `InvokeAgentRuntime` with a session ID, the prompt, the bot ID, and a header with the user | `bedrock-agentcore:InvokeAgentRuntime` on the Lambda's role | Access denied |
| 4 | AgentCore starts (or reuses) the session's microVM and sends `POST /invocations` to port 8080 | AgentCore Runtime | No place to run. Without the header allowlist, your code never sees the user |
| 5 | The code reads the lead's row and its tools' rows | DynamoDB table | The lead has no prompt and no tools |
| 6 | It reads the conversation so far | AgentCore Memory | The bot forgets the last turn |
| 7 | The lead calls the model | Bedrock permissions on the runtime's role | No answer |
| 8 | The lead calls `delegate_task`. A second agent is built **in the same process** with the specialist's prompt and tools | none | — |
| 9 | The answer streams back as SSE through the Lambda and API Gateway | 15-minute timeouts on both | Anything longer than a minute stops on screen with no error (this happened to me) |

**Takeaway:** step 8 is why the resource count stays flat. Ten bots or a hundred, the AWS side does not change.

## 2. The starter stack: 20 resources

The whole stack is [`cdk/app.mjs`](https://github.com/ypark9/yopa-experiments/blob/8a2f96be85077f3ffc83d89e776c4b147eb9d152/2026-11-22-agentcore-bot-team-start-to-production/cdk/app.mjs), about 100 lines. The part that matters most is the runtime:

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
- `usingPublicNetwork()` skips the VPC. You need one later only if a bot must reach private systems (see the production checklist).
- `idleRuntimeSessionTimeout` keeps a conversation's microVM warm for 15 minutes after the last message.
- `allowlistedHeaders` is the setting people miss. The [AgentCore docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html) describe this list as what forwards custom headers to your code (up to 20 headers, 10 KB each). Put every header you pass on it, including the user.

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

**Takeaway:** synth proves the template builds. It does not prove the runtime starts, that the public network reaches Bedrock, or that a 15-minute stream survives API Gateway with a Cognito authorizer. My prototype ran the runtime and 15-minute streams, but not from this exact template. Deploy it to a test account before you trust it.

## 3. The runtime server in 50 lines

AgentCore Runtime calls one HTTP server inside the microVM. [`runtime/index.js`](https://github.com/ypark9/yopa-experiments/blob/8a2f96be85077f3ffc83d89e776c4b147eb9d152/2026-11-22-agentcore-bot-team-start-to-production/runtime/index.js) is the smallest server I could write that follows the contract, with Node's built-in `http` module only. A real one calls a model where this one echoes the prompt:

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

## 4. The team is code, not infrastructure

The lead gets three tools, and each is a few lines over the table and the model:

- **`find_bots`**: a query on the table's index for every bot.
- **`add_bots`**: one conditional write per bot (`attribute_not_exists(PK)`, so an existing bot is never overwritten). The tool needs approval, and I approve the whole proposed team once.
- **`delegate_task`**: loads the specialist's row and tools, builds a second agent in the same process with the specialist's prompt, gives it its own Memory session, runs the task, and returns the reply with a status line: `finished`, `stuck` or `need_input`.

The rows look like this:

```
bot   PK = BOT#<botId>    SK = META   GSI1PK = BOTS    GSI1SK = <botId>
      name, prompt, modelId (an inference profile ID), toolIds, status
tool  PK = TOOL#<toolId>  SK = META   GSI1PK = TOOLS   GSI1SK = <toolId>
      type, reference (find_bots, delegate_task, ...), description, needsApproval
```

Two rules keep the team from going wrong. Specialists do not get tools that need approval, because nobody is there to approve inside a task. And specialists do not get the team tools, so a specialist cannot start its own chain of bots.

## 5. Four defaults to fix on day one

My prototype hit all four. The bots found the last two themselves, by reading their own run records.

| What I saw | Why | What to set |
|---|---|---|
| Any answer longer than a minute stopped on screen, with no error | API Gateway waited 15 minutes, but the Lambda kept the 60-second default | 15 minutes on both, plus an idle check in the UI |
| Specialists failed with "Model reached maximum token limit" | No one set `maxTokens`, so Bedrock's default of 4,096 output tokens applied | Set it yourself (I used 16,000 for specialists) |
| When the lead gave one specialist two tasks at once, the second disappeared from history | The specialist's session ID came from (lead session, bot ID), so both tasks shared one session | Add the tool call's ID to the session ID, or give a bot one task at a time |
| Run history said 0 failures while two runs had failed | Runs were recorded only on success; a run that failed and was retried left nothing | Write the run record in a `finally` block, with the status and the error |

## 6. What it costs

I read six days of my prototype's usage (2026-11-17 to 2026-11-22): token counts from the runtime's trace spans in its log group, CPU and memory from the CloudWatch metrics `CPUUsed-vCPUHours` and `MemoryUsed-GBHours`, and the Memory event count from `list-events`.

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

One request, lead → 3 specialists, all on Opus 5.5:

| Bot | Tokens in / out | Cost |
|---|---|---|
| Lead | 21,194 / 2,945 | $0.14 to $0.16 |
| Monitor (finds suspicious runs) | 9,267 / 4,185 | $0.12 to $0.13 |
| Root cause 1 (reads one session) | 22,976 / 4,363 | $0.18 to $0.20 |
| Root cause 2 (reads another session) | 21,245 / 4,556 | $0.18 to $0.19 |
| **Total, 121 seconds** | **74,682 / 16,049** | **$0.62 to $0.68** |

The runtime's share of that request is about $0.002: the six days' runtime cost spread over 15 sessions.

**Takeaways:**

- **Cost follows questions, not bots.** A bot nobody talks to has no session, so it costs nothing to run, and the table is on-demand.
- **The bots that read are the expensive ones.** Each root-cause bot read a session's history, and that made 21,000 to 23,000 input tokens.
- **The lead's context grows with every report.** Short reports are the cheapest optimization.
- **For scale (arithmetic, not measured):** 20 of those requests a day is about $12.40 to $13.60 a day.

To measure your own, all read-only:

1. **Tokens:** with OpenTelemetry on in the runtime, its log group `/aws/bedrock-agentcore/runtimes/<name>-DEFAULT` holds one span per agent run (`gen_ai.operation.name` = `invoke_agent`) and per model call (`chat`), each with `gen_ai.usage.*` token counts. `aws logs filter-log-events --filter-pattern gen_ai` collects them.
2. **Runtime:** `aws cloudwatch get-metric-statistics --namespace AWS/Bedrock-AgentCore --metric-name CPUUsed-vCPUHours` (and `MemoryUsed-GBHours`) with `--statistics Sum`.
3. **Memory:** `aws bedrock-agentcore list-sessions` and `list-events` for each actor.

Cost of this post by environment: local, my laptop's CPU for the checks and the synth. CI, the `identifier-check` job in yopa-experiments and this repo's pull request checks. Cloud, no new AWS calls; the usage above was already spent by the prototype. Billing, list-price arithmetic, not an invoice.

## 7. Going to production

The starter stack is enough for a demo with you as the only user. Before other people use it, these are the additions I would plan, roughly in the order they start to matter. None of them changes how the bots work. They change who can use the bots, what you can see, and what happens when something goes wrong.

| Add | Why | On AWS | When |
|---|---|---|---|
| Real sign-in and rate limits | Other people will hit your API, on purpose or not | Your identity provider behind Cognito (OIDC or SAML); API Gateway usage plans or AWS WAF rate rules | Before the first outside user |
| Approvals and an audit trail | A bot that changes data should not act on a guess | Tools that pause for approval (`add_bots` already does); store who approved what, and when | Before any bot gets a tool that writes |
| Run records you can trust | Without them you cannot answer "what happened?" | One record per run, written in `finally`: bot, user, status, error, tokens, time; an alarm on failures | Before the bots do real work |
| Cost limits | Tokens are the bill | `maxTokens` per bot, short reports, token totals per bot and per user, AWS Budgets alerts, prompt caching for long shared prompts | As soon as a second person uses it |
| Logs and traces | A chain of four agents is slow to debug from text alone | AgentCore observability: logs to CloudWatch Logs and traces to X-Ray for the runtime and memory | When a chain fails and you cannot tell which bot failed |
| Customer isolation | One customer must never see another's bots or history | A customer ID at the front of every key (`T#<customer>#BOT#...`), credentials scoped to one customer (for example an IAM condition on DynamoDB leading keys), Memory actor IDs that include the customer | Before the second customer |
| Private networking | Some tools reach systems that are not on the internet | `RuntimeNetworkConfiguration.usingVpc(...)` and VPC endpoints for Bedrock and DynamoDB | When a tool needs a private system |
| Data retention | Conversations can hold personal data | Memory event expiry (`expirationDuration`, 90 days by default) and a way to delete one user's data | Before you store real user data |
| Model choice per bot | Different bots need different price and quality | A model ID on each bot's row and an allowlist of models; check which AWS account owns each inference profile, because that account gets the token bill | When you add a second model |
| Safe deploys | One runtime runs every bot, so one bad change hits all of them | CI/CD with a test stage, a second runtime endpoint to switch over, prompt regression tests before changing a bot's prompt | Before people depend on it |
| Recovery | Losing the bots table loses every bot | Point-in-time recovery on the table; a second region only if you need it, after checking AgentCore runs there | When the bots hold work you cannot recreate |

**Takeaway:** expect the stack to grow to a few times its starter size. Log delivery alone adds three resources per log type (a source, a destination and a delivery). That is fine, as long as each addition answers a "why" in this table.

## What this does not show

- **The starter stack was not deployed.** Public networking, the streaming API with Cognito, and the placeholder Lambda were not run.
- **The usage is one prototype, one user, six days**, mostly on Opus. It is not a load test.
- **The production checklist is a plan, not a measured build.** I have not built every row.
- **Whether a team answers better than one agent with all the tools** is a different question. I have a test plan for it, not a result.
- **Lambda, API Gateway, DynamoDB and log storage costs were not measured.** At this volume they should be small, but that is a guess.
- **CloudWatch's daily data points were one day off from the log timestamps,** so I used only the six-day totals.
- **Prices change.** All prices are from 2026-11-22.

## Who should check what

- **Starting out:** build the 20-resource stack, deploy it to a test account, and set the four defaults before your first demo. Every one of them failed silently or looked like success.
- **Budgeting:** plan for tokens, not infrastructure, and record tokens per bot from the first day.
- **Going to production:** work down the checklist. The first four rows come before anyone else uses it.

For how AgentCore Memory's per-GB pricing behaves next to token costs, see [When AgentCore Memory's New Pricing Costs More](/blog/2026-10-09-when-agentcore-memory-gets-more-expensive.html). For where AgentCore's services fit in production, see [the AgentCore service map](/blog/2026-08-01-agentcore-service-map-and-production-boundaries.html).
