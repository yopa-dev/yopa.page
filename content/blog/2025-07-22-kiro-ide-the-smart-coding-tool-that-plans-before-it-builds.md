---
title: "Kiro After General Availability: Specs, Agents, CLI, and Web"
date: 2025-07-22
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "A current guide to choosing Kiro specs, agentic chat, CLI, Web, steering, hooks, MCP, checkpoints, and evaluation without relying on stale preview limits."
categories:
  - Development Tools
  - AI Coding
tags:
  - Kiro
  - AI-Assisted Development
  - Spec-Driven Development
  - AI Evaluation
  - Security
---

> **Review note (2026-10-21):** Kiro Web is no longer a preview. It became [generally available on September 1, 2026](https://kiro.dev/changelog/web/kiro-web-is-now-generally-available/). The preview wording is removed and the verification date updated. The rest of the guidance is unchanged.

Kiro launched in preview in July 2025 and reached general availability in November 2025. It is no longer just a preview IDE with “vibe” and “spec” modes. The product now spans IDE and CLI workflows, team features, property-based testing, checkpoints, remote MCP, global steering, custom and parallel agents, and Kiro Web, which became generally available on September 1, 2026. Availability, models, credit accounting, and prices change, so use the live product and pricing pages for purchasing decisions.

## Choose the interaction by task

Use **specs** when the work needs explicit requirements, design, tasks, and traceability. They help when a feature crosses components or when a team needs to review intent before implementation. A spec is not proof that the requirement is correct; review acceptance criteria, data, security, migration, and non-goals.

Use **agentic chat** for bounded exploration, diagnosis, and small edits where a full spec would add ceremony. Ask it to inspect current repository facts first and require changed-file and validation evidence.

Use **Kiro CLI** when terminal context, scripts, or remote environments matter. Use **Kiro Web** for asynchronous repository work and pull-request creation when its connected-repository permissions fit the task. GA changes the support status, not the review requirement. Keep branch protection and human review; a generated PR is not an approval.

## Persistent project context

Steering files capture durable conventions: architecture boundaries, build/test commands, naming, privacy, and release rules. Keep them short and version-controlled. Do not put secrets, customer data, personal preferences unrelated to the project, or frequently changing status in steering.

Hooks automate actions around events. They consume credits and can amplify mistakes, so start with read-only checks or formatting/tests. Avoid hooks that deploy, publish, delete, or broadly rewrite without an explicit approval boundary.

MCP connects tools and external context. Treat MCP servers as privileged software: review origin, permissions, data sent, authentication, and tool schemas. Remote content can contain prompt injection.

## A reliable workflow

1. Open the intended repository/branch and inspect its instructions and dirty state.
2. Write a small task brief with goal, non-goals, constraints, acceptance tests, and rollback.
3. Use a spec for cross-cutting work; otherwise begin with a plan and targeted reads.
4. Keep edits small and review checkpoints before high-impact steps.
5. Run deterministic format, type, unit, integration, and build checks.
6. Inspect the diff and test negative/security cases.
7. Commit to a branch and use normal CI/review/release controls.

Property-based testing can derive general properties from specs and generate many cases, which is valuable for input spaces. It complements example tests; it does not replace integration, security, usability, or production acceptance.

## Tradeoffs and evaluation

Specs improve alignment but can become stale or produce false confidence. Chat is fast but may drift across a large task. Parallel agents can reduce elapsed time when file ownership is disjoint, but increase conflicts and inconsistent assumptions. More tool access increases capability and risk.

Evaluate Kiro on representative repository tasks: success rate, escaped defects, reviewer edit distance, latency, credit/cost, security violations, and ability to recover. Compare against the team's current workflow. Do not choose based only on a polished greenfield demo.

## Migration from the preview-era workflow

- Remove waitlist and fixed preview-limit claims; link live pricing.
- Move durable repository guidance into reviewed steering files.
- Convert reusable high-risk hooks to manual commands or approval-gated automation.
- Review MCP servers and custom-agent permissions.
- Add checkpoints, deterministic validation, and branch/PR review.
- Re-evaluate IDE, CLI, and Web separately for data and repository access.
- Re-run a small benchmark when models or credit policies change.

Verified on **2026-10-21**.

## Primary sources

- [Kiro general availability](https://kiro.dev/blog/general-availability/)
- [Kiro documentation](https://kiro.dev/docs/)
- [Kiro Web](https://kiro.dev/blog/introducing-kiro-web/) and [Kiro Web general availability](https://kiro.dev/changelog/web/kiro-web-is-now-generally-available/)
- [Kiro pricing](https://kiro.dev/pricing/)
