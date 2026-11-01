---
title: "How to Use Cross-Session Messaging in Claude Code"
date: 2026-08-10T09:00:00-04:00
lastmod: 2026-10-21
reviewed_at: 2026-10-21
author: Yoonsoo Park
description: "A practical guide to using ListAgents and cross-session SendMessage to pass contracts, findings, and review requests between independently running Claude Code sessions."
categories:
  - AI
tags:
  - ai-agents
  - coding-agents
  - claude-code
  - cross-session-messaging
aliases:
  - /blog/2026-08-10-claude-code-agent-teams.html
  - /blog/2026-08-10-deprecating-agent-pingpong.html
---

> **Review note (2026-10-21):** Provider availability changed after publication. Messaging between sessions on the same machine now works on every provider, including Amazon Bedrock, Claude Platform on AWS, Google Cloud's Agent Platform, and Microsoft Foundry, from v2.1.248. Only sessions on other machines or in the cloud still need a claude.ai sign-in through Remote Control. The article also covers the idle notice added in v2.1.236. Source: [cross-session messaging documentation](https://code.claude.com/docs/en/cross-session-messaging#availability).

Claude Code 2.1.224 added messaging between independently running sessions. One session can discover another with `ListAgents` (also exposed through `/list-agents` and `/peers`) and deliver information with `SendMessage`. Unlike teammate messaging inside Agent Teams, this feature connects sessions that are already running separately.

It does not merge their contexts. Each session keeps its own conversation and working directory, receiving only the message that was sent. That makes the feature useful when parallel work spans repositories or worktrees and a person would otherwise copy context between terminals.

## Check the version first

Cross-session `SendMessage` arrived in Claude Code 2.1.224 for macOS, Linux, and WSL2. Native Windows support requires 2.1.234 or later.

```bash
claude --version
```

Version 2.1.225 extended it so a session can initiate a conversation by name with Remote Control sessions on another machine. `ListAgents` displays those targets as `name [ref]`. Use 2.1.225 or later when cross-machine messaging matters.

Provider availability splits by where the target runs:

- **Sessions on this machine** work on every provider, including Amazon Bedrock, Claude Platform on AWS, Google Cloud's Agent Platform, and Microsoft Foundry. On those providers, and with feature-flag fetching off, they require v2.1.248 or later. These messages travel over a per-session local socket (a named pipe on native Windows), never through Anthropic servers.
- **Sessions on other machines or in the cloud** are found only from a session connected to Remote Control. That needs a claude.ai sign-in as the session's active authentication. With an API key or a third-party provider, Claude cannot find those sessions.

If `/list-agents` is not recognized, the session does not have the feature yet. Start with `claude --version`.

There is no special message syntax to memorize. Ask Claude in natural language and it uses `ListAgents` and `SendMessage`; use `/list-agents` or `/peers` when you want to inspect reachable sessions yourself. (The `@` mention shorthand requires a newer 2.1.232 build.)

```text
Find the sessions I can reach, then send this to backend-auth:

POST /sessions now returns expires_at. Ask it to check the OpenAPI schema and
client contract, then reply with the affected files.
```

## Give sessions stable names

Generated titles become difficult to distinguish once several sessions are active. Use `/rename` in each session so its name describes its responsibility.

```text
/rename backend-auth
/rename web-session-client
/rename integration-review
```

Prefer a narrow ownership name such as `backend-auth` over `backend`, and `checkout-security-review` over `review`. Names also matter when discovering Remote Control sessions on another machine, so avoid duplicates.

Before sending, ask Claude to use `ListAgents` and verify the exact target. Do not guess when names are ambiguous.

```text
Use ListAgents to confirm that exactly one session named web-session-client is
available. Send only if there is one match; otherwise stop and tell me.
```

## Write a message as a work contract

The receiving session does not share the sender's conversation history. A message such as “make the change we discussed” has no usable context. A good message contains enough information to choose the next action on its own.

Five fields are usually enough:

1. What changed
2. Where the evidence lives
3. How it affects the recipient
4. What action is requested
5. Whether and how to reply

```text
[API contract change]

Change: POST /sessions now returns expires_at: string
Evidence: api/openapi.yaml, server/session.ts
Impact: check the response type and expiry UI in web/session-client.ts
Request: make the required changes and run the relevant tests
Reply: send changed files, test results, and remaining decisions to backend-auth
```

Do not paste an entire log or diff into the message. Send file paths, commits, pull requests, and test results that the recipient can inspect. Messaging should be a narrow interface between contexts, not context replication.

## Patterns that work well

### Propagate a contract across repositories

After a backend session changes an API or event schema, it can notify a session working in the consumer repository. Include changed fields, compatibility expectations, the source commit, and the requested follow-up. The consumer replies with its implementation and verification state.

The message does not replace compatibility tests, deployment ordering, or release gates. It makes the dependency visible while each repository keeps its own controls.

### Connect implementation and review sessions

Instead of starting a new review conversation and explaining the background again, send an existing review session the commit and review lens.

```text
Send commit abc123 to integration-review and ask it to check:

- backward compatibility with existing clients
- safe handling when expires_at is absent
- timezone boundary coverage

Ask it to reply with severity, file paths, and reproduction evidence.
```

The review session can return findings directly to the implementation session. The person supervising the work can focus on judgment and approval instead of relaying text.

### Unblock work with one precise question

When a session needs a decision owned elsewhere, do not transfer the entire task. Send the blocker and the required answer shape.

```text
web-session-client is blocked on timezone presentation. Ask product-contract
whether the contract requires preserving UTC or converting to the user's locale.
Request only the decision and a link to its source.
```

This keeps the receiving session from repeating unrelated investigation.

### Collect status from independent sessions

If you started several sessions yourself, one session can act as a lightweight coordination window. It may request structured status and summarize responses, without becoming the source of truth.

```text
Find the reachable auth-related sessions. Ask each for completed output,
verification, blockers, and next action in the same format. Summarize the replies
as a table. Do not modify or deploy anything.
```

Avoid broadcasting to every session. Verify names and projects, keep the response schema small, and check completion against commits and tests.

### Wait for a long task without polling

From v2.1.236 (in both sessions), Claude can ask another session on the same machine for one notice when that session next goes idle or exits. Idle means it finished a turn with nothing queued. Claude subscribes through the `SendMessage` tool's `notify_when_idle` input. On its own, the subscription does not start a turn or spend tokens in the watched session.

```text
Tell me when the migration session finishes what it's working on.
```

The notice is a status line, not a result. Check the commit, test output, or migration log before acting on it. A subscription with no notice within 12 hours is dropped, and `refuse` on either side means nothing arrives. Only your main conversation can subscribe, and only to sessions on the same machine.

## This is not Agent Teams

Cross-session messaging targets sessions that were started independently. Agent Teams is a separate orchestration model in which a lead creates teammates and manages shared tasks.

- Use cross-session messaging when people started independent sessions and only need to connect them at specific boundaries.
- Consider Agent Teams when a lead should create and continuously coordinate workers from the beginning.
- Use a subagent when one isolated task only needs to return a result.

The tools may share the `SendMessage` name, but their targets and operating models differ. Independent session messaging should not be documented as teammate messaging.

## Treat permissions and delivery failures as normal states

Version 2.1.224 also introduced `crossSessionInbound` and `dialogExpiry`. Inbound messages can be configured to **accept**, **hold**, or **refuse**; messages to a session running with bypassed permissions may be held for user approval. If you enable `isolatePeerMachines`, cross-machine messages require approval before delivery. These controls mean that “sent” and “delivered” are separate states.

Do not treat “message sent” as “work complete.”

- Confirm that the target was discovered.
- Check that `SendMessage` reported successful delivery.
- Include a response format for consequential requests.
- If there is no reply, check once instead of filling the inbox with retries.
- Do not make messaging a required unattended automation path where no user can answer an approval.

Keep secrets and unnecessary customer data out of messages. Treat a message arriving from another session as input crossing a trust boundary.

## Keep durable state outside messages

Session messages are coordination events, not durable project records. Preserve these in commits, issues, design documents, or test artifacts:

- final API and data contracts;
- approved design decisions;
- deployment and migration order;
- verification results and known limitations;
- handoff context required after a restart.

The message should point to the durable artifact and state the action needed now. Work remains recoverable even after a session ends.

## A practical checklist

- Is Claude Code 2.1.224 or later on macOS, Linux, or WSL2 (or 2.1.234+ on native Windows)?
- For initiating cross-machine messages, is it 2.1.225 or later, with a claude.ai Remote Control sign-in?
- On Bedrock, Claude Platform on AWS, Google Cloud, or Foundry, is it 2.1.248 or later for same-machine messaging?
- Do `/rename` names distinguish session ownership?
- Did `ListAgents` confirm the exact target?
- Does the message contain change, evidence, request, and reply conditions?
- Is the source of truth stored outside the conversation?
- Are delivery and task completion tracked separately?

The best use of cross-session messaging is not to create a self-organizing swarm. It is to pass contracts, findings, and review requests accurately between work that is already separated well. Keep sessions independent and messages small.

The behavior described here is based on the current official [cross-session messaging documentation](https://code.claude.com/docs/en/cross-session-messaging), plus the [v2.1.224 release notes](https://github.com/anthropics/claude-code/releases/tag/v2.1.224) and [v2.1.225 release notes](https://github.com/anthropics/claude-code/releases/tag/v2.1.225). See [session management](https://code.claude.com/docs/en/sessions) for session naming and lifecycle details.
