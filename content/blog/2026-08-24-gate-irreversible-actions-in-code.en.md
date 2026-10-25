---
title: "Irreversible Actions Cannot Be Gated by a Prompt"
date: 2026-08-24T09:00:00-04:00
author: Yoonsoo Park
description: "An AI agent booked a gym class and deleted another person's reservation to do it. The lesson is not 'write a better prompt.' It is that destructive actions belong behind deterministic code, not behind a sentence you hope the model obeys. Here is how I learned that the expensive way."
categories:
  - AI
  - Architecture
tags:
  - ai-agents
  - agent-safety
  - authorization
  - human-in-the-loop
  - guardrails
---

In August 2026 an AI assistant was told to book a gym class. The class was full, so the agent found the booking API, noticed it had no real authorization check, created a reservation outside the allowed window, and canceled a higher-priority person on the waitlist to make room. Then it said "sorry about that."

The headlines called it a rogue agent hacking a system. That framing is wrong, and the wrong framing is dangerous because it points you at the wrong fix. The agent did not hack anything. It used an API exactly as the API allowed. The backend let an unauthenticated-enough caller cancel someone else's reservation, and nothing in the system required a human to approve an irreversible action before it happened. The agent was just the first caller careless enough to walk through the open door.

I want to argue one thing in this post: you cannot gate an irreversible action with a prompt. Not with a better system prompt, not with a "please confirm before destructive operations" instruction, not with a politely worded tool description. The stop has to live in deterministic code that runs whether or not the model cooperates. I believe this because I once deleted production infrastructure for eighteen teams, and the only reason it was recoverable is that a piece of dumb, non-negotiable code forced me to look before I leapt. The prompt would not have saved me. The code did.

## Why the prompt is the wrong layer

A prompt is a request. Even a good model treats "always ask before deleting" as strong guidance, not as a physical constraint. The moment the model decides the deletion is obviously fine, or misreads the situation, or gets nudged by adversarial input, the guidance loses. And an agent's whole value is that it acts without you in the loop, so by the time you would notice, the irreversible thing has already happened.

Think about the three places you could put the guardrail:

1. **In the prompt.** "Do not perform destructive actions without confirmation." This is a suggestion to a probabilistic system. It fails silently and it fails exactly when you need it most, under weird inputs.
2. **In the tool schema.** Mark the tool as dangerous, require a `confirm: true` argument. Better, but the model still fills in that argument. If the model can produce the token that unlocks the action, the model can unlock the action. You have moved the decision, not removed it from the model.
3. **In deterministic code the model cannot talk its way past.** A wrapper, a hook, a backend check that refuses the action unless a condition outside the model's control is met. This is the only layer that holds when the model is wrong.

The gym incident lived entirely at layer one and layer two. The backend trusted the caller. There was no layer three.

## The time I was the rogue agent

Here is my own version of the same failure, and I was the intelligence in the loop, not a language model.

I was cleaning up cloud infrastructure and ran a delete against what I thought was a scoped, throwaway resource. It was actually a shared API Gateway custom domain. Deleting it wiped the base-path mappings for eighteen teams in one call. Eighteen teams' traffic routing, gone, because one delete command did exactly what I asked instead of what I meant.

No prompt would have stopped me. I *was* the prompt. I read the command, I believed I understood the blast radius, and I was wrong. Human judgment is exactly the layer that fails here, the same way model judgment failed in the gym case. The intelligence being biological did not help.

What saved the recovery was a habit I had encoded as a step, not a suggestion: before any shared-resource delete, capture the full mapping table first. That query output, the boring `(base path -> API, stage)` dump I took right before deleting, turned out to be the exact blueprint I needed to rebuild seventeen of the eighteen mappings. The one I could not restore was the one whose backend API had itself been deleted, so there was nothing left to point at. The safety step meant to prevent the disaster was also the thing that made the disaster survivable.

So I did what the gym's backend engineers should have done. I moved the stop out of my head and into code.

## What the code layer actually looks like

I now run my agent tooling behind a pre-execution hook that inspects every command before it runs and hard-blocks a small set of catastrophic operations. Not warns. Blocks. The command does not execute.

The shape is simple:

- A denylist of operations whose blast radius is irreversible and shared: delete a shared domain, delete a hosted zone, drop a production table. These return a hard block with a non-zero exit before the action fires.
- A deliberately narrow denylist. The hook does *not* block the correctly-scoped fix (deleting a single base-path mapping, the surgical operation you actually want available during recovery). If you block everything, people route around you. Block only the operations whose cost is unrecoverable.
- An escape hatch that is auditable, not convenient. To proceed anyway you prefix the command with an explicit override token, something like `CONFIRM_SHARED_DELETE=1`. Typing that token is a physical act that shows up in shell history and audit logs. It is the difference between "the model emitted confirm: true" and "a human deliberately, on the record, chose to override a block."
- A block message that doubles as a runbook. When the hook stops you, it prints the blast-radius query to run first and the exact narrowly-scoped commands to use instead. The guardrail teaches you the safe path at the moment you are trying to take the unsafe one.

The key property is that none of this trusts the intelligence issuing the command. It does not matter whether that intelligence is Claude, a shell script, or me at 2am. The block is a property of the environment, not a plea to the actor.

## The general principle

Map it back to the gym. The correct fixes there were never "prompt the agent better." They were:

- The backend returns `403` when a caller tries to cancel a resource it does not own. Authorization in code, checked server-side, every time.
- Irreversible actions (canceling someone else's booking) require an approval step the caller cannot self-issue. Human-in-the-loop as a hard gate, not a prompt.
- After a refusal, the agent does not get to hunt for an alternate endpoint that skips the check. The check lives on every path, not on the polite one.

Notice that these are exactly the properties of my delete hook, expressed in a different domain. Narrow the denylist to the truly irreversible. Make the override auditable and human-issued. Enforce it on every path, not just the expected one. And design the refusal so it points at the safe alternative instead of just saying no.

## What to actually do

If you are shipping an agent that can touch anything consequential, do the boring thing:

- List your agent's actions and mark the ones that are irreversible or shared. That short list is the only part that needs a code-level gate. Everything else can stay fast and prompt-driven.
- For each item on that list, write a deterministic check that runs regardless of what the model says. A wrapper, a hook, a server-side authorization rule. If the model can emit the token that unlocks it, it is not a gate.
- Make the override a physical, auditable act by a human, not an argument the model can produce.
- Capture the recovery blueprint *before* the destructive step, not after. The query you run to check blast radius is also the map you will use to rebuild.

The uncomfortable takeaway is that the intelligence of the actor is not the safety layer. A smarter model does not save you here, because the failure is not stupidity, it is confident wrongness, and both humans and models have plenty of that. Put the stop where confidence cannot reach it. Put it in code.
