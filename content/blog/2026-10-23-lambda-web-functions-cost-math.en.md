---
title: "Lambda Web Functions vs Event Functions: the three assumptions inside AWS's price examples"
date: 2026-10-23T11:00:00-04:00
author: Yoonsoo Park
description: "Lambda Web Functions bill active CPU plus memory for each environment's lifetime. AWS's four pricing examples all assume one environment running at all times, and the obvious comparison with Event Functions quietly gives a small Event function a full vCPU. I repriced all four on Arm and x86, with and without those assumptions, and measured how much CPU a streaming proxy burns per request on my machine."
categories:
  - AWS
  - FinOps
tags:
  - aws-lambda
  - lambda-web-functions
  - serverless
  - cost-modeling
  - graviton
---

Lambda Web Functions price compute differently from the Lambda you know. The [pricing page](https://aws.amazon.com/lambda/pricing/) says you pay for "the CPU time your code actively uses, and the memory consumed by each execution environment for as long as it runs." On Arm in us-east-1:

| | Web Functions (Arm only) | Event Functions, Arm | Event Functions, x86 |
|---|---|---|---|
| Compute | $0.0000276944 per active vCPU-second | $0.0000133334 per GB-second of wall time | $0.0000166667 per GB-second |
| Memory | $0.0000036667 per GB-second, for the environment's whole life | (included above) | (included above) |
| Requests | $0.30 per million | $0.20 per million | $0.20 per million |

The page also has four worked examples, priced as Web Functions only: server-side rendering, an I/O-heavy API, an authorizer and LLM streaming. Roman Ceresnak already [repriced them as Arm Event Functions](https://builder.aws.com/content/3KVvIb9GOBUUwLwDHQiiLSgkPZo/you-dont-pay-for-the-wait-lambda-web-functions-for-ai) and found Event cheaper in three of the four. That's a good start, so I won't repeat it. My question is narrower: **which assumptions decide the answer, and how far does each one move it?**

**Short answer:**

- **Event CPU depends on memory size.** "At 1,769 MB, a function has the equivalent of one vCPU." A 0.49 GB Event function gets about a quarter of one. If the 40 ms of CPU in AWS's SSR example is real single-threaded work, it takes about 141 ms on that function. With that one correction, SSR flips: Event Arm costs $27.60 and Web $25.77. The I/O-heavy API goes from Event being half the price to within 1.4% of Web.
- **The request fee is a floor that CPU can't beat.** Web charges $0.10 per million more per request. At 512 MB on Arm, an Event request shorter than 15 ms costs less in total than that difference alone. Short, high-volume handlers stay Event territory. In the authorizer example, $30.00 of the $64.56 Web bill is the request fee.
- **"Exactly one environment at all times" is a choice AWS made for the math, not one you get to make.** Each extra always-on environment adds about $9.50 per GB per month. With three environments, SSR on Web goes from $25.77 to $35.09.
- **x86 makes the switch both more attractive and more work.** Event on x86 costs 25% more per GB-second than Arm, so the gap to Web is bigger. But Web Functions run only on Graviton, so every native module has to be rebuilt for Arm64 first.
- **Streaming is where Web clearly wins: $33.95 against $101.00** on Arm Event. My local measurement suggests a thin streaming proxy burns far less than the 200 ms of CPU per request in AWS's example, and less per request at higher concurrency. That is a ballpark from an x86 box, not a Lambda measurement.

Everything below is desk math from the public price list plus one local measurement. Nothing ran on AWS. How to check it against a real bill is at the end, with its cost.

## Reproducing the four examples

The [cost model](https://github.com/ypark9/yopa-experiments/tree/experiment/lambda-web-functions-cost-math-20261023/2026-10-23-lambda-web-functions-cost-math) uses:

- **Web prices:** quoted in the page's worked examples.
- **Event prices:** from the public price map the same page loads (`Lambda Duration-ARM` 0.0000133334, `Lambda Duration` 0.0000166667, `Lambda Requests` 0.0000002).
- **AWS's own assumptions:** a 30-day month (2,592,000 seconds), one environment, no free tier.

My Web totals match AWS's to within a cent. AWS rounds each line before adding, so SSR comes out at $25.77 in my model against $25.78 on the page.

| Example | Requests | End to end | Active CPU | Memory | Web (AWS's assumption) | Event Arm, same duration | Event x86, same duration |
|---|---|---|---|---|---|---|---|
| 1 SSR web app | 15 M | 150 ms | 40 ms | 0.49 GB | $25.77 | $17.70 | $21.38 |
| 2 I/O-heavy API | 10 M | 200 ms | 50 ms | 0.29 GB | $19.60 | $9.73 | $11.67 |
| 3 Auth middleware | 100 M | 50 ms | 12 ms | 0.14 GB | $64.56 | $29.33 | $31.67 |
| 4 LLM streaming | 5 M | 3,000 ms | 200 ms | 0.50 GB | $33.95 | $101.00 | $126.00 |

The Arm Event column matches Ceresnak's numbers. So far this says Event wins unless you stream. Now change the assumptions one at a time.

## Assumption 1: the Event function is as fast as the Web environment

The same-duration column assumes a 0.49 GB Event function finishes the request in 150 ms, the same as a Web environment, which has 2 vCPUs per the [scaling docs](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-scaling.html). But Event CPU is proportional to memory. The [memory docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html) say "At 1,769 MB, a function has the equivalent of one vCPU." At 0.49 GB that is 28% of a vCPU.

If the 40 ms of active CPU is single-threaded work that would run at full speed on one vCPU, the Event function stretches it to about 141 ms. The request then takes about 251 ms. Applying that to the CPU part of each example:

| Example | Web | Event Arm, CPU scaled | Event x86, CPU scaled | Stretched duration |
|---|---|---|---|---|
| 1 SSR | $25.77 | **$27.60** | $33.75 | 251 ms |
| 2 I/O API | $19.60 | $19.32 | $23.65 | 448 ms |
| 3 Authorizer | $64.56 | $54.73 | $63.42 | 186 ms |
| 4 Streaming | $33.95 | $117.37 | $146.46 | 3,491 ms |

SSR flips to Web. The I/O API becomes a near tie on Arm, and on x86 Web wins. Only the authorizer stays on the Event side, because of the request fee (next section).

This is an upper bound on the effect, not a prediction. If the "active CPU" in your workload is spread across threads, or is mostly the runtime idling, it won't stretch this way. You can also buy back speed by giving the Event function 1,769 MB, but then you pay for 3.5 times the memory. Either way, the honest comparison is between your measured Event duration at the memory you actually configure and your measured Web CPU. Two equal duration numbers prove nothing.

## Assumption 2: the request fee doesn't matter

Web's request fee is $0.30 per million, against $0.20 for Event. That extra $0.10 per million is paid before any compute. An Event request costs less in total than that gap alone when its duration is below:

| Event memory | Arm | x86 |
|---|---|---|
| 128 MB | 58.6 ms | 46.9 ms |
| 512 MB | 15.0 ms | 12.0 ms |
| 1 GB | 7.5 ms | 6.0 ms |

Below those durations, Web can't win no matter how little CPU it uses. The authorizer shows the effect: 100 million requests at 50 ms, and the request fee alone is $30.00 of the $64.56 Web bill. Authorizers, webhooks and small fan-out workers are high volume and short, and they belong on Event.

## Assumption 3: exactly one environment, all the time

AWS states this assumption plainly: "requests arrive often enough that exactly one execution environment is running at all times and serves all of the traffic." It keeps the math simple. It is also the cheapest possible memory line, because one environment is the least memory you can pay for while serving traffic. The memory line in the examples is small: $4.66 for SSR.

But you don't choose the environment count. The [scaling docs](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-scaling.html) say:

- Lambda "automatically scales up execution environments ahead of demand to maintain spare capacity (headroom)".
- `maxConcurrencyPerEnvironment` caps requests per environment from 1 to 128, with a default of 64.
- "There is no minimum or reserved-environment setting."

Each always-on environment costs this much in memory per month:

| Memory per environment | Per month |
|---|---|
| 0.25 GB | $2.38 |
| 0.5 GB | $4.75 |
| 1 GB | $9.50 |
| 2 GB | $19.01 |

Three environments instead of one moves SSR from $25.77 to $35.09, and streaming from $33.95 to $43.45. The other side cuts the other way. Environments scale to zero, so a spiky service with long idle gaps can pay less memory than the always-on example assumes. The free `EnvironmentActiveTime` and `EndpointActiveEnvironments` metrics in the [monitoring docs](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-monitoring-metrics.html) are how you find out which case you are in.

## Streaming: how much CPU does a proxy really burn?

The streaming example is where Web pays off, and its biggest line is CPU: 200 ms per request, $27.69 of $33.95. I wanted a feel for that number, so I wrote a local stand-in:

- **The handler:** a Node HTTP handler that reads a fake upstream model emitting 300 JSON chunks 10 ms apart (about 3 seconds, like AWS's example) and re-emits each chunk as an SSE event.
- **The measurement:** `process.cpuUsage()` around batches of requests, at three concurrency levels.

| Concurrency | Requests | CPU per request |
|---|---|---|
| 1 | 10 | 75.8 ms |
| 8 | 24 | 17.6 ms |
| 64 | 192 | 8.7 ms |

Read this carefully:

- **It is not a Lambda number.** It is Node 20 on an x86 Xeon, not Graviton. There is no TLS and no Web Functions runtime, and the load client shares the process, which over-counts.
- **What it does show** is the shape. Most of the CPU in a thin proxy is waking up for each chunk, and that cost spreads out as more streams share one event loop. At 64 concurrent streams it was a ninth of the single-stream figure.
- **Priced at Web's CPU rate,** 5 M requests at 8.7 to 75.8 ms is $1.20 to $10.50 a month, against the $27.69 AWS assumed.

A real proxy that signs requests, terminates TLS and parses tool calls will burn more. But the direction holds: on Web, concurrency per environment lowers the CPU line, not just the memory line. On Event, every stream pays for 3 full seconds.

## When I'd pick which

| Workload | Pick | Why |
|---|---|---|
| Streams or long waits on an LLM or a slow API | Web | You don't pay for the wait. Concurrency shares memory and, by my local measurement, CPU |
| SSR or APIs with real CPU per request, low or steady traffic, Node.js | Web, after measuring | The equal-duration comparison flatters Event. Measure your Event duration at the memory you'd actually set |
| Authorizers, webhooks, anything under ~15 ms at 512 MB | Event | The request-fee gap is bigger than Event's whole compute charge |
| Not Node.js, or native x86 modules you can't rebuild | Event | Web Functions are Node.js only and Arm64 only |
| Spiky traffic with long idle periods | Either, then check `EnvironmentActiveTime` | Scale to zero cuts the memory line; headroom raises it |

For where Lambda fits against containers and sandboxes for agent workloads, see [Where to run agent-generated code](/blog/2026-07-02-where-to-run-agent-generated-code.html).

## Owner-run experiment (not yet run)

The desk math has two unknowns that only a real Web Function answers:

- What does `EnvironmentCPUTime` per request look like on Graviton, and does it drop with concurrency the way my local run did?
- How many environments does Lambda keep for a modest load?

I have not run this. The results below are blank until someone does.

**Estimated cost:**

- **What it uses:** the AWS CLI starter Web Function (a small Node.js server) and 4,000 requests in two batches.
- **Prices (us-east-1, 2026-10-23, [pricing page](https://aws.amazon.com/lambda/pricing/)):**
  - requests: 4,000 × $0.30 per million ≈ $0.0012
  - CPU at a generous 50 ms per request: 200 vCPU-seconds × $0.0000276944 ≈ $0.006
  - memory, even at 0.5 GB for 3 environment-hours: ≈ $0.02
- **Extras:**
  - CloudWatch Logs ingestion for a few hundred KB
  - a few small objects in a versioned S3 bucket
  - a handful of CloudWatch metric reads
  - the metrics themselves are free per the [monitoring docs](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-monitoring.html)
- **Total:** a few cents at most. This is an estimate, not a billing guarantee.

**Steps:**

1. Check the account, role and CLI support. All read-only and free:
   - `aws sts get-caller-identity --query Arn --output text`
   - `aws lambda-web help` must work. If it doesn't, update AWS CLI v2.
2. Deploy the starter. This creates a Web Function, a `dev` endpoint, an IAM role `awscli-lambdaweb-yopa-web-cost` and an S3 bucket `awscli-lambdaweb-<account>-<region>-an`, per the [create guide](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-create.html):
   `AWS_REGION=us-east-1 aws lambda-web deploy --name yopa-web-cost --hello-world`
   Copy the endpoint URL from the output. **The starter endpoint accepts unauthenticated requests, so don't share the URL, and delete everything when you are done.**
3. Send load with the repo's `load.mjs`, which refuses more than 5,000 requests:
   - `git clone https://github.com/ypark9/yopa-experiments && cd yopa-experiments && git checkout experiment/lambda-web-functions-cost-math-20261023 && cd 2026-10-23-lambda-web-functions-cost-math`
   - `node load.mjs "$URL" 2000 1`
   - wait 15 minutes, so the environments can scale down
   - `node load.mjs "$URL" 2000 32`
4. After 10 minutes, read the free metrics for each batch's window. Use the `started_utc` value printed by `load.mjs`, and repeat for `EnvironmentActiveTime` and `ExecutedRequests` (both `Sum`) and `EnvironmentMaxMemoryUsage` (`Maximum`):
   `aws cloudwatch get-metric-statistics --namespace AWS/Lambda/Web --metric-name EnvironmentCPUTime --dimensions Name=FunctionName,Value=yopa-web-cost --start-time <start> --end-time <start+15m> --period 900 --statistics Sum`
   For the environment count:
   `aws cloudwatch get-metric-statistics --namespace AWS/Lambda/Web/Usage --metric-name EndpointActiveEnvironments --dimensions Name=FunctionName,Value=yopa-web-cost Name=EndpointName,Value=dev Name=ExecutionRegion,Value=us-east-1 --start-time <start> --end-time <start+15m> --period 60 --statistics Maximum`
5. Turn the numbers into a bill, locally:
   `python3 bill_from_metrics.py <ExecutedRequests> <EnvironmentCPUTime> <EnvironmentActiveTime> <EnvironmentMaxMemoryUsage>`
6. Expected observations, if the local shape holds:
   - CPU per request is lower in the concurrency-32 batch than the concurrency-1 batch
   - `EndpointActiveEnvironments` stays at 1 or 2 for this load
   - the memory line is an upper bound, because the helper uses peak memory

**Teardown and cost-stop checks.** The delete command does not remove the role, the bucket objects or the logs, per the [create guide](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-create.html).

1. Delete the Web Function, which also removes its endpoints and revisions:
   `aws lambda-web delete-web-function --function-name yopa-web-cost`
2. Delete the role:
   - `aws iam list-role-policies --role-name awscli-lambdaweb-yopa-web-cost`
   - `aws iam delete-role-policy --role-name awscli-lambdaweb-yopa-web-cost --policy-name <each name>`
   - `aws iam delete-role --role-name awscli-lambdaweb-yopa-web-cost`
3. Delete the logs:
   - `aws logs delete-log-group --log-group-name /aws/lambda/web/yopa-web-cost`
   - `aws logs delete-log-group --log-group-name /aws/lambda/web/yopa-web-cost.local`
4. Delete only this function's objects from the shared, versioned bucket. A plain `s3 rm` leaves old versions behind:
   - `aws s3api list-object-versions --bucket <bucket> --prefix lambda-web/yopa-web-cost/ --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' > v.json && aws s3api delete-objects --bucket <bucket> --delete file://v.json`
   - repeat with `DeleteMarkers` in place of `Versions`
5. Check that the URL now fails: `curl -sS "$URL"`. Check Cost Explorer the next day.

**Results:** _not yet run._

## What I did not measure

- **No Web Function ran.** All dollar figures are list-price arithmetic on AWS's own workload numbers, plus my assumptions, each named above.
- **CPU scaling is a bound, not a measurement.** It assumes single-threaded CPU work that would run at full speed on one vCPU.
- **The local CPU probe is a shape, not a figure.** x86, no TLS, client in the same process.
- **Not included:** cold starts, data transfer, the Event free tier (1 M requests and 400,000 GB-seconds per month), the higher-volume Event price tiers, and Savings Plans. I found no free tier stated for Web Functions on the pricing page.
