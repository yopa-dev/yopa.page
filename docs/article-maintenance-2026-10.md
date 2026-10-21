# Article Maintenance: 2026-10 Freshness Pass

Reviewed: 2026-10-21

This ledger records the October 2026 freshness pass over every live English article in `content/blog`. It follows the conventions of the [2023–2025 maintenance ledger](article-maintenance-2023-2025.md) and the 2026-08-28 agent-article refresh:

- Preserve URLs and the original `date`.
- Set `lastmod` and `reviewed_at` to the review date only when the change is substantive.
- Add a dated `Review note (2026-10-21)` blockquote near the top that says what changed.
- Replacement articles (`maintenance_status: replacement`) keep `lastmod` and `reviewed_at` at their 2026-08-01 rewrite date. The article template renders `lastmod` as "Rewritten" for replacements, and `tests/test_archived_articles.py` pins that lineage date, so the dated review note alone records the October change. The 2026-08-28 pass used the same rule for the Private Key JWT article.
- `scripts/validate_article_tags.py` previously scoped 2023–2025 articles by the literal `reviewed_at: 2026-08-01`. It now matches any 2026 `reviewed_at`, so articles re-reviewed in this pass stay under tag validation.
- Prefer in-place updates. Archive and publish a replacement (`maintenance_status`, `replaces_url`) only when the premise cannot be repaired.
- Back every changed claim with an official source. Leave out anything that could not be verified.

## Scope and method

- 220 live articles reviewed (43 archived originals and open draft PRs excluded). 17 are evergreen non-technical posts.
- Every article got a keyword scan for versions, runtimes, model IDs, preview/GA status, pricing, deprecations, and tsconfig/CLI snippets. About 35 high-volatility articles were read in full against primary sources.
- 297 unique external links were checked with curl.
- TypeScript, Node.js, and Jest snippets were reproduced locally at $0 with `typescript@7.0.2`, `typescript@6.0.3`, `ts-jest@29.4.15`, `ts-node@10.9.2`, `tsx@4.23.15`, and Node.js 24.22.0. No cloud calls were made.
- Result: 19 articles need updates (6 high, 5 medium, 8 low), 4 could not be verified at $0, and the rest were OK.

Fixes ship as three draft pull requests, one per severity batch, so each can be reviewed and merged independently.

## High: copy-paste breakage (this batch)

| Article | Verdict | Material change | Evidence |
| --- | --- | --- | --- |
| `2024-02-10-Mastering-Jest-with-TypeScript-A-Comprehensive-Guide.md` | Update | Pin `typescript@6` for `ts-jest` (its peer range is `>=4.3 <7`), show the `@typescript/typescript6` alias for TS 7 users, use an explicit `tsconfig.json` with `"types": ["jest", "node"]`, and add a `tsc --noEmit` check. | [TypeScript 7.0](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/), local reproduction |
| `2023-04-24-Streamline-Your-TypeScript-Projects-with-Advanced-Path-Mapping-Techniques.md` | Update | Remove `baseUrl` and make `paths` targets project-relative. Add Node.js subpath imports (`#app/*`) for runtime resolution. | [TypeScript 7.0](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/), [Node.js TypeScript: paths aliases](https://nodejs.org/api/typescript.html#paths-aliases), local reproduction (TS5102/TS5090) |
| `2024-02-26-Mastering-Update-Notifier-in-Node.js-with-TypeScript.md` | Update | Replace `target: es5` / `commonjs` with `es2022` / `nodenext` ESM, use JSON import attributes, and install `@types/update-notifier` (7.3.1 ships no declarations). | [TypeScript 7.0](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/), local reproduction (TS5108, TS7016) |
| `2023-08-18-Passing-Command-Line-Arguments-to-a-TypeScript-Script-using-NPM.md` | Update | Replace `ts-node` with `node your-script-file.ts` (type stripping) and keep `tsx` as the fallback. Argument handling unchanged. | [Node.js TypeScript](https://nodejs.org/api/typescript.html), local reproduction (ts-node crash with TS 7) |
| `2026-05-23-deploy-hermes-ai-agent-aws-ecs-fargate-slack.md` | Update | Replace the retired Model access step with the Anthropic one-time usage form, move Node.js 18/20 to 24 LTS, and correct "Fargate only supports x86_64" (ARM64 is supported and must match `cpuArchitecture`). | [Bedrock automatic enablement](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-automatic-enablement-serverless-foundation-models/), [Node.js releases](https://nodejs.org/en/about/previous-releases), [ECS ARM64](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-arm64.html) |
| `2026-08-01-safe-container-updates-on-a-personal-docker-host.en.md` | Update | State that `containrrr/watchtower` is archived and fails on Docker Engine 29. Replace the monitor with notify-only Diun (pinned) and Renovate, and add a read-only Docker API check. | [Archive announcement](https://github.com/containrrr/watchtower/discussions/2135), [Docker Engine 29 notes](https://docs.docker.com/engine/release-notes/29/), [issue #2124](https://github.com/containrrr/watchtower/issues/2124), [Diun docs](https://crazymax.dev/diun/install/docker/) |

## Medium: factual drift (follow-up batch)

| Article | Planned change |
| --- | --- |
| `2026-08-10-claude-code-cross-session-messaging.en.md` | Same-machine messaging works on every provider (v2.1.248+). Only cross-machine and cloud sessions need claude.ai Remote Control. Add `notify_when_idle` (v2.1.236). |
| `2025-07-22-kiro-ide-the-smart-coding-tool-that-plans-before-it-builds.md` | Kiro Web reached GA on 2026-09-01. Drop the "preview" wording. |
| `2025-05-25-aws-vector-databases-rag-applications-complete-architectural-decision-guide.en.md` | Add DynamoDB native vector search (GA 2026-08-05) as the "vectors on the operational table" option. |
| `2024-04-30-Leveraging-NPX-and-NVM-for-Efficient-Backend-Development.md` | Replace the end-of-life Node.js 12/14 examples with supported LTS lines. |
| `2024-01-25-How-to-Check-if-Google-Analytics-is-Working.md` | Universal Analytics is gone. Reframe the duplicate-tag example around GA4 and the Google tag. |

## Low: version bumps and links (follow-up batch)

| Article | Planned change |
| --- | --- |
| `2026-08-01-durable-long-running-jobs-with-agentcore.en.md` | Note that runtime instances support sessions up to 14 days, while the microVM runtime stays at 8 hours. A long session is still not durable state. |
| `2026-08-01-deploy-a-serverless-api-with-cdk-v2.en.md` | `Runtime.NODEJS_22_X` → `Runtime.NODEJS_24_X`. |
| `2026-03-30-personal-aws-cost-guardrails.en.md` | Cost Anomaly Detection runs about three times a day. Detection can still lag up to 24 hours. |
| `2026-02-28-Strands-vs-LangGraph.md` | Fix the Strands quickstart link (404) and the diagram model label. |
| `2026-05-27-adding-llms-txt-to-hugo.en.md` | Hugo Output Formats link moved to `/configuration/output-formats/`. |
| `2024-01-01-Managing-Multiple-Versions-with-Pyenv-and-Virtual-Environments.md` | Replace the hard-coded 3.13.5 example (3.13 is now security-only). |
| `2026-08-01-python-project-environments.en.md` | Same Python example bump. |
| `2024-03-25-Setting-Up-a-Shortcut-for-GitHub-Copilot-in-VS-Code.md` | Lead with the built-in Chat view shortcut. Keep the custom binding as optional. |

## Not changed: could not verify at $0

- `2024-01-14-Freeing-Up-Ports-80-and-443-on-Synology-NAS-for-Reverse-Proxy-Usage.md`: DSM nginx template edits need a real NAS to verify. Recommend a manual check with a backup and rollback step.
- `2026-08-24-give-every-agent-its-own-worktree.en.md`: the "Cursor Shadow Workspace" removal has no official changelog source.
- `2026-05-28-bruno-aws-sigv4-sso-profile.en.md`: `profileName` / `opencollection.yml` behavior was not re-verified against the current Bruno release.
- `2026-02-09-Why-Do-Python-Experts-Use-the-Property-Decorator.md`: the YouTube handle link returns 404 to curl, which YouTube does for valid handles too. Consider the channel-ID URL.

## Watch list

- `2023-04-13-Manage_Nodejs_Versions_explained.md`: `.nvmrc` 24 is correct today. Node.js 26 becomes Active LTS on 2026-10-28; revisit after that.
- `2026-08-01-typescript-decorators.en.md`: TypeScript 7 still accepts `experimentalDecorators`. Optional TS 7 mention.

## Validation

Each batch runs `python3 scripts/validate_frontmatter.py`, `python3 scripts/validate_article_tags.py`, `python3 scripts/validate_expeditions.py`, `python3 -m unittest discover -s tests`, and `hugo --gc --minify` before it is pushed.
