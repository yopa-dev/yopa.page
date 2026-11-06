---
title: "AgentCore CLI 1.0 Will Not Migrate a Project That Still Looks Like a Guess"
date: 2026-11-06T09:00:00-05:00
author: Yoonsoo Park
description: "Amazon Bedrock AgentCore CLI 1.0 (@aws/agentcore 1.0.1) ships agentcore migrate and a long breaking-changes page. I installed the binary, built 20-plus v0-style agentcore.json fixtures, and ran migrate with no AWS credentials. Some shapes die on Unrecognized key before a plan exists. Others write a plan and then refuse on git, CDK, and aws-targets.json. Knowledge-base add is gone. Here is the decision table."
categories:
  - AWS
  - AI Agents
tags:
  - Amazon Bedrock AgentCore
  - CLI
  - migration
  - measured
  - Developer Tools
---

On 2026-10-28 AWS [announced AgentCore CLI 1.0](https://aws.amazon.com/about-aws/whats-new/2026/10/amazon-bedrock-agentcore-cli-version-1-0-available/) as the npm package `@aws/agentcore`. The release note highlights a `migrate` command for existing projects. The [breaking-changes developer guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-cli-migration-breaking-changes.html) is the long remap: `create` switches to `--template`, `add agent` becomes `add runtime`, harness flags become JSON objects, `status` drops filters, and knowledge bases are no longer managed by the CLI.

That page tells you what *should* change. I wanted the failure modes you hit when the file on disk is wrong *before* migrate rewrites anything — the kind of error that burns half a day of engineer time in a deploy script, not a token bill.

So I installed `@aws/agentcore@1.0.1` on a Linux box, built many small `agentcore/agentcore.json` fixtures, and ran `agentcore migrate` with **no AWS credentials**, no `deploy`, and no `invoke`. The short version:

1. **A guessed top-level `"resources": {}` never reaches a plan.** The binary fails deserialize with `Unrecognized key: "resources"`.
2. **`agents`, `gateways`, and `targets` at the top level are also unrecognized.** The v0 schema this CLI reads wants collections like `runtimes`, `memories`, and `harnesses` — not the names you might invent from the product vocabulary.
3. **A minimal `{ "version": 1, "name": "demo" }` does deserialize.** Migrate then writes a plan and lists local blockers (git, CDK package age, CDK app files, `aws-targets.json`) without calling AWS.
4. **`agentcore add knowledge-base` is an unknown command** on 1.0.1. The breaking page said so; the installed help confirms it.
5. **I did not complete a migrate on a real deployed project**, so I do **not** claim ARN or name preservation. Undeployed stub plans say "never deployed; no names to keep."

Code and raw logs: [yopa-experiments `experiment/agentcore-cli-1-0-migrate-20261106`](https://github.com/ypark9/yopa-experiments/tree/experiment/agentcore-cli-1-0-migrate-20261106/2026-11-06-agentcore-cli-1-0-migrate) (commit [`e7b1d25`](https://github.com/ypark9/yopa-experiments/commit/e7b1d25d4d955d8f834cc874a361c4c9fe10008c)).

This extends the CLI-version footnote in [Interactive Shells in Bedrock AgentCore Runtime](/blog/2026-06-08-agentcore-interactive-shells.html) — that post is about attaching a shell to a live runtime, not about project-format migration. Open draft PR #135 (Gateway model fallback) is a different surface again.

## The words, briefly

| Term | Meaning here |
|---|---|
| AgentCore CLI | The `@aws/agentcore` npm package. Version checked: **1.0.1** (`agentcore --version`). |
| v0 project | `"version": 1` in `agentcore/agentcore.json`. |
| v1 project | `"version": 2` in that file. Installing CLI 1.0 does **not** convert files; you run `agentcore migrate`. |
| Deserialize reject | Migrate refuses to read the JSON and prints `Failed to deserialize… Unrecognized key…` (or field errors). No plan file. |
| Plan / not ready | Migrate accepts the JSON, writes `agentcore/.cli/migrate/plan-*.md`, then exits because local checks failed. Still no AWS call in these runs. |

## How I ran it

- Unpacked `@aws/agentcore@1.0.1` from `npm pack` (SHA-256 `1a224c21…cca15db9` in the experiment folder).
- Credentials: unset access keys; `AWS_EC2_METADATA_DISABLED=true`; empty AWS config and credentials files.
- For each fixture: a project root with only `agentcore/agentcore.json` (plus a few stubs for readiness). Command: `agentcore migrate` (no `--yes` apply).
- Separately captured `create` / `add` / `status` / `migrate` help, and `agentcore add knowledge-base`.

Nothing left the machine for AWS. npm was used only to fetch the CLI package.

## Stage A: shapes that die on deserialize

These never produced a migration plan. The CLI rejected the file first.

| What the file looked like | What migrate printed | What to conclude |
|---|---|---|
| Minimal name plus a guessed `"resources": {}` wrapper | `Unrecognized key: "resources"` | Do not invent a resources envelope. Strip it or regenerate from a real v0 project. |
| A list under `"agents"` (the old product word for a runtime) | `Unrecognized key: "agents"` | Top-level collection is `runtimes`, not `agents`. The `add agent` → `add runtime` rename in the docs is about the **command**, and the JSON key you need for migrate is already `runtimes`. |
| Top-level `"gateways"` or `"targets"` | `Unrecognized key` for those names | Deployment targets belong in `agentcore/aws-targets.json`, not as a `targets` key inside `agentcore.json` (that shape was rejected here). |
| `"language"` / `"framework"` parked on the project root | `Unrecognized keys: "language", "framework"` | Those were create-time flags. v1 create takes `--template` instead; they are not project-file fields. |
| An arbitrary extra key (`fooBar`) | `Unrecognized key: "fooBar"` | The schema is strict. Extra keys fail closed. |
| Empty `{}` | Missing `name`; `version` expected `2` | Without `"version": 1`, you are not on the v0 path this article cares about. |
| Already `"version": 2` | `This project is already in the v1 format; there's nothing to migrate.` | Migrate is a one-way gate. |

Takeaway: if CI wraps your project file in a helper key or still says `agents`, migrate fails **before** it can help you. Fix the JSON shape first.[^ids]

Partial collections fail differently — the key is recognized, the fields are not:

| Situation | Observed field error | What to conclude |
|---|---|---|
| `runtimes: [{ "name": "Assistant" }]` only | `build` must be `CodeZip` or `Container`; missing `entrypoint` and `codeLocation` | Name alone is not enough for a runtime entry. |
| `memories: [{ "name": "Facts" }]` only | missing `eventExpiryDuration` | Matches the breaking page's rename from `--expiry` to `--event-expiry-duration`. |
| `harnesses: [{ "name": "Helper" }]` only | missing `path` | Migrate expects a path to the harness directory (and later a `harness.json` on disk). |
| `knowledgeBases` with a half-built data source | discriminator / `uri` errors | The **v0 schema still knows** `knowledgeBases`. That is not the same as CLI management (next section). |

## Stage B: a plan, then local blockers (still no AWS)

This file is enough to get past deserialize:

```json
{ "version": 1, "name": "demo" }
```

On that fixture, migrate printed `Migration plan: demo → v1` and wrote a plan markdown file. It then refused to apply anything until local checks passed. Across the stubs I used, the blockers were:

| Check | What I saw | Cost to you |
|---|---|---|
| git | "requires the project to be in a git repository so you can review and undo" | Init and commit before migrate. |
| CDK `package.json` | Missing, or "older than v0.24.2" | The CLI suggests `npx @aws/agentcore@0 deploy` once to refresh deps. **I did not run that** — it would touch AWS. |
| CDK app files | Needs `agentcore/cdk/bin/cdk.ts` and `lib/cdk-stack.ts` | A one-file stub `app.js` was not enough. |
| `aws-targets.json` | Required file | Use a real target entry; docs show placeholder account `111122223333` / `123456789012`. |
| CodeZip runtime | `runtimeVersion is required for CodeZip builds` | Even with `build` / `entrypoint` / `codeLocation` filled, migrate asked for `runtimeVersion`. I did not fully map the accepted value format. |
| Harness on disk | Missing `app/Helper/harness.json` | JSON path alone is not enough. |

Takeaway: migrate's first useful output is often a **checklist of local prep**, not a cloud diff. Budget engineer time for git + CDK layout before you schedule a deploy window.

A stub that already had git, `aws-targets.json` with account `123456789012`, and an old CDK `package.json` still failed three checks (CDK age, missing `cdk.ts` / `cdk-stack.ts`, missing `runtimeVersion`). The plan for that undeployed stub said **"never deployed; no names to keep."** That is why this post does not claim deployed ARN preservation.

## Commands your scripts still call

Independent of migrate, the installed binary's help matches the breaking page on the remaps that break shell scripts:

| Old habit | What 1.0.1 actually exposes | Measured check |
|---|---|---|
| `agentcore create --language Python --framework Strands` | `create` flags: `--name`, `--template`, `--skip-install`, `--skip-git` | `agentcore create --help` |
| `agentcore add harness --model-provider … --model-id … --no-memory --timeout 120` | `--model` JSON, `--memory` JSON, `--timeout-seconds` | `agentcore add harness --help` |
| `agentcore add agent …` | `add runtime` (with JSON config objects for network / authorizer / lifecycle) | `agentcore add --help` lists `runtime`, not `agent` |
| `agentcore status` filtered by runtime / state / type | `--target` only | `agentcore status --help`; breaking page: filters removed |
| `agentcore add knowledge-base …` | **Gone** | Exact stderr: `unknown command 'knowledge-base' for 'add'` |

The knowledge-base row is the sharp edge. The breaking page says to create knowledge bases with the AWS CLI (`aws bedrock-agent create-knowledge-base`). Gateway connectors that *point at* an existing knowledge base move under `agentcore add gateway-connector`. Meanwhile a v0 `agentcore.json` may still *contain* a `knowledgeBases` array that migrate tries to parse — management and schema are not the same thing.

Dominant cost here is **script and runbook churn**: every wrapper that still passes `--language` or calls `add knowledge-base` fails on the first CI job after the CLI bump, before any agent token is spent.

## What you should do

1. **Pin and check the CLI.** `npm view @aws/agentcore version` / `agentcore --version`. This article measured **1.0.1**.
2. **Run `agentcore migrate` on a throwaway clone with no AWS credentials first.** If you see `Unrecognized key`, fix the JSON shape. If you see a plan with "Not ready to migrate", clear the local checklist (git, CDK, `aws-targets.json`) before you involve an account.
3. **Rewrite create/add/status wrappers** against the help output above — especially knowledge-base and create templates.
4. **Only then** run migrate in an environment that can refresh v0 CDK deps and deploy, and verify resource names yourself. I did not verify that step.

If your project is small and mostly scaffolding, a fresh `agentcore create --template …` plus copying application code can be cheaper than fighting a half-custom v0 tree. If you already have deployed names you must keep, migrate is the path the docs prescribe — but the binary will not start that path until deserialize and local readiness pass.

## Limits

- Package under test: `@aws/agentcore@1.0.1` only. Later 1.x patches may change messages or schema.
- No AWS API calls; no successful end-to-end migrate with `--yes` on a deployed stack.
- Deployed ARN / name preservation: **unverified**.
- `runtimeVersion` accepted values: not fully mapped.
- Fixture keys were chosen from the breaking page and common guesses; they are not a dump of every field a real v0 CDK app emits.

[^ids]: Fixture folder names in the experiment repo (`with_resources`, `only_version_name`, and so on) are only for matching raw logs. The tables above use plain-language situations instead.
