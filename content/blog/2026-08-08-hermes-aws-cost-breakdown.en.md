---
title: "How Much Does It Cost to Run Hermes Agent on AWS?"
date: 2026-08-08
lastmod: 2026-08-28
reviewed_at: 2026-08-28
author: Yoonsoo Park
description: "A measured Cost Explorer breakdown of running a personal Hermes Agent on AWS ECS Fargate for a little over a month, including NAT Gateway, Fargate, EFS throughput, and supporting services."
categories:
  - AWS
  - Agentic AI
  - FinOps
tags:
  - Hermes Agent
  - Amazon ECS
  - Amazon EFS
  - FinOps
  - Self-Hosting
---

When I deployed Hermes Agent on AWS, I initially budgeted for the ECS task and the LLM. After running it for a little over a month, that estimate looked too simple. The always-on NAT Gateway and EFS throughput cost about as much as Fargate for one personal agent.

This article answers a narrow question: how much did it cost to run Hermes on AWS? It is one measured deployment, not a universal price list. Your region, runtime, traffic, storage mode, and model provider will change the result.

> **Review note (2026-08-28):** These are still a historical, pre-credit usage snapshot. Recalculate with current AWS prices and the [current Hermes Docker/configuration guidance](https://hermes-agent.nousresearch.com/docs/user-guide/docker/) before using the numbers for a new deployment; no current release or model-provider bill is inferred from this measurement.

## The measured architecture

The AWS setup contained:

- one ECS Fargate ARM task with 1 vCPU and 2 GiB of memory
- two private subnets and one public NAT Gateway
- encrypted EFS for Hermes state
- Hermes images accumulated in ECR
- three Secrets Manager secrets for Slack, GitHub, and provider credentials
- an S3 knowledge/context bucket and CloudWatch Logs

Hermes used Slack Socket Mode, so it did not have a public inbound endpoint. The private subnets still needed a path to Slack and provider APIs. That path was the NAT Gateway. No public endpoint and no outbound-network cost are two different things.

## The measured usage cost: about $108.9

The measurement period was July 4 through August 8, 2026. Hermes accumulated about 833 runtime hours. The table uses Cost Explorer `Usage` line items before credits and rounds each amount to the nearest cent.

| Component | Usage | Cost |
|---|---:|---:|
| NAT Gateway hours and processing | 833 hours, about 12.3 GB | about $38.04 |
| ECS Fargate ARM | 833 vCPU-hours, 1,664 GB-hours | about $32.92 |
| EFS Elastic Throughput data access | about 730.5 GB | about $31.97 |
| EFS storage | less than 1 GB on average | about $0.14 |
| Public IPv4 for the NAT Gateway | about 833 hours | about $4.17 |
| Secrets Manager | three secrets | about $1.32 |
| ECR storage | accumulated usage during the period | about $0.34 |
| EFS backup | less than 1 GB | about $0.02 |
| **Total** |  | **about $108.9** |

S3 and CloudWatch Logs were effectively rounding errors at this workload size. The table excludes the LLM. Hermes used the OpenAI Codex provider, while AWS Bedrock usage was $0. Mixing an OpenAI subscription or another external provider bill into AWS infrastructure cost would make the comparison less useful.

## Why the cash bill was close to $0

My AWS account had promotional credits during this period. Account-wide Usage was about $113.22 and almost the same amount was covered by credits, so the cash charge was close to $0.

That did not make the architecture free. A more accurate interpretation is that **one personal agent consumed about $109 of AWS credits in a little over a month**. After the credits expire, the same resources become a normal bill. This is why I record pre-credit usage even when an account's current invoice looks harmless.

## The EFS throughput surprise

The file system held only about 924 MB at the final measurement, but EFS Elastic Throughput data access reached about 730 GB. Looking only at stored capacity would miss this difference.

I did not trace every Hermes file operation, so I cannot honestly attribute the total to one SQLite or startup behavior. The bill does show that repeated I/O on a small file system can cost far more than storing the files themselves.

## NAT Gateway charges even with low traffic

Hermes had no public inbound endpoint. The private subnets still needed outbound access to Slack and provider APIs, so the NAT Gateway remained provisioned around the clock. Its hourly charge continued even when traffic was low.

During this period, the fixed hourly charge was much larger than the data-processing charge. For a personal agent, that makes a public-subnet design with appropriate controls, a NAT instance, VPC endpoints, or an already-running home server worth evaluating. The right choice depends on security requirements and how much infrastructure you want to operate.

## What I would estimate first next time

I would calculate these four items before writing the deployment plan:

1. vCPU and memory hours for the always-on task
2. fixed NAT Gateway and public IPv4 cost for private-subnet egress
3. file-system throughput mode and data access, not just stored capacity
4. the pre-credit price after promotional credits disappear

Current rates are available from [AWS VPC pricing](https://aws.amazon.com/vpc/pricing/), [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/), [Amazon EFS pricing](https://aws.amazon.com/efs/pricing/), and [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/). These numbers are one deployment's measured usage in one region, not a fixed price for every Hermes installation.

After measuring this cost, I moved Hermes to Synology and documented the lossless process separately: [Migrating Hermes from AWS ECS to Synology Without Losing Its Memory](/blog/2026-08-08-migrate-hermes-from-aws-to-synology.html).
