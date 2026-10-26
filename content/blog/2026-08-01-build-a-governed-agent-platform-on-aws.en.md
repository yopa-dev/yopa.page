---
title: "Build a Governed Agent Platform on AWS"
date: 2025-12-20
lastmod: 2026-08-01
reviewed_at: 2026-08-01
maintenance_status: replacement
replaces_url: "/blog/2025-12-20-building-agent-factory-with-agentcore.html"
aliases:
  - /blog/2025-12-10-agent-factory-scaling-ai-employee-creation.html
author: Yoonsoo Park
description: "Turn agent creation into a reviewed platform workflow with declarative templates, least privilege, signed artifacts, evaluations, approval, observability, and rollback."
categories:
  - AWS
  - Platform Engineering
tags:
  - Amazon Bedrock AgentCore
  - AI Agents
  - Platform Engineering
  - Security
  - Observability
  - AWS IAM
atlas:
  region: cloud
  object: field-note
  journeys:
    - safe-agent-operations
  evidence: documented
  era: current
---

An “agent factory” should not mean giving a model broad IAM permissions and asking it to create roles, repositories, images, and runtimes directly. Natural language can propose an agent, but production infrastructure needs a deterministic, reviewable control plane.

The safer pattern is a governed internal platform: an agent specification becomes a pull request or signed request, policy and evaluation gates produce evidence, and a deployment service—not the agent being built—applies an approved template.

## Define the product contract

```yaml
name: order-status-assistant
owner: commerce-platform
protocol: HTTP
model_policy: approved-low-risk
tools:
  - get_order_status
data_classification: internal
memory:
  enabled: false
network:
  internet_egress: false
human_gate:
  required_for_write_tools: true
budgets:
  max_runtime_seconds: 120
  max_tool_calls: 8
```

Validate this schema and reject unknown fields. Resolve tool names through an approved catalog whose entries include owner, input/output schema, authorization model, data class, availability, and test endpoint. A prompt cannot request an arbitrary role ARN or container image.

## Separate planes and identities

The **platform control plane** validates specs, synthesizes CDK/CloudFormation/Terraform, runs policy checks, builds images, creates an immutable release, and deploys AgentCore resources. Its privileged actions run under a tightly controlled CI/deployment role with approvals and audit.

The **agent data plane** handles invocations with a per-agent execution role. It cannot create IAM roles, alter its runtime, publish images, or grant itself tools. AgentCore Identity/Gateway may provide outbound credentials and tool access, but each target still authorizes the actual action.

Use separate roles for source checkout, image build, infrastructure deployment, runtime execution, and break-glass recovery. External CI should assume roles through OIDC. Never use `aws configure` or a developer's static key in automation.

## Supply-chain controls

Build from a pinned base image and lock dependencies. Generate an SBOM, scan dependencies and image, sign the image, store it in private ECR with immutable tags, and deploy by digest. Record source commit, build identity, evaluation result, policy version, image digest, model configuration, and infrastructure plan in release provenance.

Templates should provide secure defaults: log redaction, encryption, private networking where needed, bounded egress, resource tags, deletion/retention, lifecycle settings, alarms, and budgets. Exceptions require an owner, rationale, expiry, and additional test.

## Evaluation gates

Run deterministic application tests before model evaluation. Then test representative and adversarial cases for task success, tool argument validity, authorization, prompt injection, unsafe actions, data leakage, refusal/escalation, latency, and cost. Compare against a simple baseline; do not approve a multi-agent topology if it adds expense without improving outcomes.

Write tools need sandbox or draft-mode tests and idempotency. Cross-tenant systems require negative isolation tests. Browser or code execution requires network and artifact controls. A human reviewer approves risk-sensitive releases with the evidence attached, not a generated summary alone.

## Deployment and operations

Promote the same immutable artifact from development to staging and production with environment-specific configuration. Start with shadow/read-only traffic, then a small canary. Monitor task success, human correction, tool denials, runtime errors, latency, token/tool cost, queue/backlog if applicable, and anomalous identity use.

Rollback switches traffic to the previous compatible artifact and configuration. Memory/schema/tool-contract changes need forward/backward compatibility or an explicit migration restore plan. Provide a kill switch that revokes invocation or tool authority independently of a full deployment.

## Tradeoffs

A platform accelerates many teams and centralizes controls, but it can become a bottleneck or lowest-common-denominator abstraction. Start with two or three repeated agent patterns, not a universal factory. Direct team-owned deployment may be better for an early experiment; require the same identity, test, and cost boundaries before granting production authority.

## Migration checklist

- Remove infrastructure mutation permission from builder agents.
- Convert desired behavior to a versioned, validated spec.
- Create approved runtime and tool templates with narrow roles.
- Build/sign/scan immutable artifacts in CI and review the infrastructure plan.
- Add deterministic, model, security, isolation, cost, and recovery gates.
- Separate release approval from runtime identity.
- Add canary, provenance, alarms, budgets, kill switch, and rollback.
- Pilot one low-risk agent and measure platform lead time and escaped defects.

Verified on **2026-08-01**.

## Primary sources

- [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html)
- [Amazon ECR image tag immutability](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html)
- [AWS Signer container image signing](https://docs.aws.amazon.com/signer/latest/developerguide/Welcome.html)
- [NIST Secure Software Development Framework](https://csrc.nist.gov/Projects/ssdf)
