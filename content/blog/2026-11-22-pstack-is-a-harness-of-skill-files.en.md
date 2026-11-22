---
title: "pstack Is Not a Stack. It Is a Harness Made of Markdown, and One Skill in It Is Worth Stealing."
date: 2026-11-22T09:00:00-05:00
author: Yoonsoo Park
description: "pstack keeps showing up in my feed with more hype than explanation. I read the actual repository. It is a bundle of markdown skill files: one router, 22 playbooks, 24 principles, about 34 skills, 2 subagents. This post walks through the install commands, the file tree, and one task end to end, with every intermediate step shown. The mechanics that matter are small and stealable, and one of them, create-verification-skill, will raise your agent's output quality on its own."
categories:
  - AI Agents
  - Architecture
tags:
  - AI Agents
  - Architecture
  - Software Design
  - CLI
  - Programming
---

pstack keeps showing up in my feed, always attached to the same person: Lauren Tan, @poteto online, ex-Meta and Netflix, now at Cursor, and on the React core team where she works on the React Compiler. The numbers people quote are her own claims: her skills used around ten thousand times a week inside Cursor, roughly two thousand pull requests a month shipped through this workflow. She says herself the PR count was never the goal. Fine. The question worth answering is different: what is this thing, mechanically, and what can you take from it even if you never install it?

I read the repository ([cursor/plugins/pstack](https://github.com/cursor/plugins/tree/main/pstack), MIT licensed) instead of the hot takes. Here is everything, in order, assuming you have never touched a "skill" before.

## Step 0: what a skill even is

pstack is not a model, not an IDE, not a service. It is a folder of markdown files. Each file is a **skill**: a small YAML header plus written instructions that an AI coding agent (Cursor, Claude Code) reads before doing a certain kind of work. Here is a real one, the header of the skill this post ends up recommending:

```yaml
---
name: create-verification-skill
description: "Generate a project-local verification skill that drives your app
  the way a user does..."
disable-model-invocation: true
---
```

Two things to notice. The `description` is what the agent reads to decide whether this skill is relevant. And `disable-model-invocation: true` means the agent is **not allowed** to load this skill on its own just because a keyword matched. Most pstack skills carry this flag. Nothing happens until something with authority tells the agent which skill to pick up. Remember this; it matters in a minute.

The word for a collection like this is a **harness**. A strong horse without a harness runs in random directions. The model is the horse. The harness is whatever turns that strength into work in the direction you wanted. pstack is a harness made of about thirty thousand words of markdown.

## Step 1: install (two lines)

In Cursor:

```bash
/add-plugin pstack
```

In Claude Code:

```bash
/plugin marketplace add cursor/plugins
/plugin install pstack@cursor-plugins
```

In Claude Code, every command gets a `pstack:` prefix, so `/poteto-mode` becomes `/pstack:poteto-mode`. Features that only exist in Cursor (Bugbot, Automations) are skipped with a one-line note.

## Step 2: setup (one command)

Run `/setup-pstack`. It detects which models you have access to, asks you for a reasoning budget, and writes one small config file mapping each **role** to a model: who writes code, who handles judgment and prose, who sits on the review panel. In Claude Code the file lands at `~/.claude/rules/pstack-models.md`.

The out-of-the-box defaults, from the README: code delegates, prose, and judgment go to Claude Opus at the highest reasoning effort, and the default review panel is three models from different vendors. Why a panel? Because several skills, like `/interrogate`, work by having **different models try to break your diff**, keeping only findings a run actually proves. One vendor's blind spot gets caught by another vendor's model. This also tells you the limitation up front: in a single-vendor setup, the panel collapses toward the same model reviewing itself, which is a weaker check.

You only override what you want; every skill falls back to defaults when the config is absent.

## Step 3: what you just installed

The tree, condensed:

```
pstack/
├── skills/
│   ├── poteto-mode/        # the router + 22 playbooks
│   ├── principle-*/        # 24 one-line principles
│   └── ...                 # ~34 task skills (/how, /tdd, /arena, ...)
└── agents/
    ├── poteto-agent.md     # subagent that reads the full rules first
    └── comment-sicko.md    # read-only comment reviewer
```

Three layers, top to bottom:

**The router: `/poteto-mode`.** The name is literal: "work like poteto." This is the entry point. You type `/poteto-mode` followed by a plain-language task, and it picks a recipe.

**22 playbooks.** One per task type: bug fix, feature, refactoring, perf, prototype, overnight autonomous run, opening a PR, and so on. Think of each as a recipe card. The bug fix card says, in order: reproduce, find the root cause, fix, re-verify with runtime evidence.

**24 principles.** One line each. "Subtract before you add." "Fix the root cause, and a guard is a fix only when the state it handles is legitimate." "Model the domain in a structure instead of scattered conditionals."

The mental model that clicked for me: imagine the best senior engineer you know. She never fixes a bug the moment it is reported; she reproduces it first. She clicks through the fix herself before saying "done." She changes the minimum amount of code. If you wrote down every one of her habits and handed the document to a new hire, the hire would start working a little like her. pstack is that document, aimed at an agent.

One deliberate omission: there is no planning skill. The README says it plainly: "i don't believe in planning. the best spec is code."

## Step 4: one task, start to finish

This is the part nobody shows. Say you have a todo app and a bug: checking a todo as done does not survive a refresh. Here is what you type, and what happens at each step.

**You type:**

```
/poteto-mode marking a todo done doesn't survive a refresh. repro first, then fix and verify.
```

**The router opens a todo list, and the first items are the playbook steps, copied verbatim.** Not summarized. Copied. Reproduce the defect. Narrow the cause. Fix. Re-verify on the same screen. Open the PR. This looks like ceremony, but it is the first real mechanism: if the agent skips a step, it cannot quietly drop the item. It has to write down why it skipped it. Agents love silently omitting tedious steps, and verification is the most tedious step of all. Making omission require a written excuse is a cheap trick that does outsized work.

**Reproduce before fixing.** The agent launches your actual app in a browser (through a verification skill; see the next section), checks a todo, refreshes, and captures the failure as evidence. No fix attempt before reproduction. This alone eliminates the most common AI failure mode: reading the code, guessing the cause, and patching the guess.

**Narrow the cause.** Is the check not saved, or saved but overwritten on load? The agent forms hypotheses and knocks them down one at a time with logs, instead of fixing by vibes. Say the answer is: on startup, the app writes an empty list over storage before reading it.

**Fix the minimum.** Only that spot gets touched. The playbook carries a sentence I want framed: a safety net you add "just in case" is a hypothesis, not a fix, and it does not ship. When a model does not know the cause, it sprinkles defensive code everywhere, the symptom disappears, the code is a mess, and the real cause is still hiding. pstack bans the sprinkle.

**Re-verify on the same screen.** The original reproduction steps run again, in the same browser, and this time the checked state survives the refresh. "It should work now" is not a pass; a screenshot is.

**Commit in an order that tells the story.** The failing test is committed first, the fix commit goes on top. Anyone reading the history later sees the failure, then the fix.

**Open the PR.** The body format is fixed: why the change, what changed, what you deliberately did not do, what it might break, how it was verified.

Two more things happened invisibly during all this. The code was written by a **subagent** (a fresh agent given one slice of work), while the main agent stayed in the reviewer seat. And that subagent is not a generic helper: pstack's `poteto-agent` reads the entire poteto-mode rules file before it touches anything, so ten parallel workers all work the same way. The README warns that substituting a generic subagent skips that read, and the behavior drifts.

The same motion works for features. One principle fires that I wish more codebases enforced: do not spray state across booleans. Ask a naive agent for "overdue todos in red" and it adds an `isOverdue` flag next to `isDone`, and now "done but overdue" is a state your UI has to reckon with. The `model-the-domain` principle says: status is open or done, overdue is computed from the date. Illegal states become unrepresentable instead of merely handled.

## Step 5: the skill worth stealing

Of the ~34 skills, the author calls the verification skill the most important one in the toolbox, and after reading it, I agree. `/create-verification-skill` is a skill that writes a skill.

The problem it solves: agents forget everything between sessions, and without instructions your agent stops at "the build passes." This skill makes the agent produce a handover document for your app, written for the next agent who has never seen it. The process, straight from the file:

1. **Interview the repository, not the user.** The agent answers from the code: what does a user touch (web UI, CLI, API)? What command starts it? How can it be driven programmatically (existing Playwright specs first, a generic browser harness second)? What evidence can be captured (screenshots, logs, database state)?
2. **Write `.cursor/skills/verify-<app>/SKILL.md`** with real commands and real selectors from your repo, in fixed sections: Launch (the exact start command and how to know it is ready), Doctor (one read-only "is this instance worth driving" check), Drive, Evidence, Cleanup.
3. **Seed a feature map**: one markdown file per user-facing feature, answering how to reach it, how to drive it, and what observable end state proves it works.
4. **Prove it before handing it over.** The agent runs its own document end to end once: launch, drive one feature, capture evidence, clean up. The file says it directly: "a generated skill that was never executed is a draft, not a deliverable."

Once this exists, "fix it" changes meaning. The agent launches your app, clicks through the scenario, and finishes with screenshots attached instead of "it should work." The feature map is hardened memory: no re-reading the whole codebase every session.

If you are thinking "that is just E2E testing," the distinction matters. E2E tests check that what used to work has not broken. The verification skill checks that the thing the agent just built actually works, by having the agent operate the app itself. Already have Playwright tests? The skill reuses them. But the warning cuts both ways: if you cannot tell that the generated skill is clicking the wrong button, you have just automated the production of plausible screenshots. Understand the principle, then install the tool.

## The rule underneath everything

Buried in pstack is the idea I consider the real lesson, and it matches what I have been writing here about agentic coding. When your agent repeats a mistake, **where** you put the correction determines how strongly it binds. The `/correct` skill encodes the order explicitly: fix each repeated mistake at the highest layer that works.

1. **Architecture and code.** The bad pattern is impossible to write.
2. **Types, lint, CI.** A machine rejects it.
3. **Tests.**
4. **Docs and rules files.** A sentence asks nicely.

A "don't add comments" line in your rules file is layer 4, and models ignore sentences occasionally. A lint rule is layer 2. Tan's team went to layer 1 and banned comments in their internal framework. The reasoning is the part to remember: **an agent imitates whatever it sees in the codebase.** One "temporary, fix later" comment teaches it that sloppy is acceptable here. So her team deleted sloppy old code too, and kept exactly one way to do each thing. If it should not be imitated, it should not be visible.

Two corollaries fall out. Automation goes last: wiring Slack so bug reports auto-generate fix PRs looks great in a demo, but on an immature repository it amplifies slop automatically. And scale follows trust: a hundred agents you cannot trust produce a hundred times the garbage PRs. Her framing is better than mine: not a software factory, a Michelin kitchen, where every plate that leaves has a chef responsible for it.

## When not to use it, and the honest limits

Short list, because it matters as much as the rest:

- **Small chores.** A button color change does not need reproduction, verification, and a PR. The author says it herself: use it when rigor is needed.
- **Solo projects that push to main.** pstack always opens PRs. If that is not your flow, the default fights you.
- **Cost.** Subagents and three-model review panels burn tokens. One reported case: a thirty-minute task took an hour, and in exchange caught the agent's confident falsehoods. Your call whether that trade fits.
- **Prose is not enforcement.** "No merge without verification" is a sentence, not a mechanism. That is exactly the layer-4 problem above, and it is why the author pushes lessons down to lint and architecture wherever possible.
- **Better models shrink the gap.** Recent commits delete knowledge newer models no longer need. The durable value is not the tips; it is the forced order of operations and the demand for evidence.

## Verdict

pstack is one strong engineer's working habits, written down carefully enough that an agent can follow them. The volume of prose is not the point. The point is three small mechanisms: a router that decides which skill may be picked up, a todo list where skipped steps need written excuses, and evidence demanded before "done."

Take `create-verification-skill` even if you take nothing else; the moment your agent says "here is the proof" instead of "it should work," the output changes. Take the layer rule too: push every repeated correction as far down as you can, and clean the codebase of anything you would not want imitated.

And the endgame is built in: run `/automate-me` and it mines your own transcripts to draft a `<your-name>-mode` skill that routes through pstack underneath. The goal was never to work like Lauren Tan. It is to understand the principles well enough to build your own harness.
