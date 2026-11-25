---
title: "pstack Is Not a Stack. It Is a Harness Made of Markdown, and One Skill in It Is Worth Stealing."
date: 2026-11-22T09:00:00-05:00
author: Yoonsoo Park
description: "pstack keeps showing up in my feed with more hype than explanation. I read the actual repository at version 0.15.46. It is a folder of markdown: 58 skill files (one router, 24 principles, 33 task skills), 22 playbooks, and 2 subagents. This post walks through the install, the file tree, and the bug-fix playbook step by step. Two things surprised me: the default review panel is less mixed than it sounds, and the rule I liked most was deleted last week. The skill I would steal first is create-verification-skill."
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

pstack keeps showing up in my feed, always attached to the same person: Lauren Tan, @poteto online. In the README she says she has worked at Meta, Netflix, and Cursor, and that she is on the React core team, where she helps build the React Compiler. The numbers people quote are her own: by her account, her team used these skills about ten thousand times in one week, and she merged roughly two thousand pull requests in a month ([her post about the talk](https://x.com/poteto/status/2102050467505430555)). She also says the PR count was never the goal. Fine. The question worth answering is different: what is this thing, mechanically, and what can you take from it even if you never install it?

I read the repository ([cursor/plugins/pstack](https://github.com/cursor/plugins/tree/main/pstack), MIT licensed) instead of the hot takes. Two ground rules for everything below:

- **Version.** Every fact here is from pstack 0.15.46, which is `cursor/plugins` at commit `7a58391` (November 22, 2026). pstack changes fast. Its default models changed three times in the week before I wrote this, so check your version before you trust a detail.
- **I have not run it for this post.** Step 4 walks through the bug-fix playbook on a made-up todo app. It shows what the playbook tells the agent to do. It is not a log of a real run.

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

Two things to notice. The `description` is what the agent reads to decide whether this skill is relevant. And `disable-model-invocation: true` means the agent is **not allowed** to load this skill on its own just because a keyword matched. 57 of the 58 pstack skills carry this flag. The only one without it is `setup-pstack`. So a person has to start things: you type `/poteto-mode`, and from there the mode tells the agent which other skill files to read. In Claude Code you can see this directly. The agent's Skill tool refuses these skills, so pstack's Claude Code guide tells the agent to open the `SKILL.md` file and follow it instead.

The word for a collection like this is a **harness**. A strong horse without a harness runs in random directions. The model is the horse. The harness is whatever turns that strength into work in the direction you wanted. pstack is a harness made of about 29,000 words in its `SKILL.md` files alone, and about 46,000 if you count the playbooks and reference files next to them.

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

In Claude Code, every command gets a `pstack:` prefix, so `/poteto-mode` becomes `/pstack:poteto-mode`, and paths under `.cursor/` become `.claude/`. I use the Cursor names in the rest of this post. Features that only exist in Cursor (Bugbot, Automations) are skipped with a one-line note.

One more Claude Code detail that matters later: Claude Code leaves auto-update off for third-party marketplaces by default. You stay on the version you installed until you update it yourself.

## Step 2: setup (one command)

Run `/setup-pstack`. It detects which models you have access to, asks you for a reasoning budget, and writes one small config file mapping each **role** to a model: who writes code, who handles judgment and prose, who sits on the review panels. In Claude Code the file lands at `~/.claude/rules/pstack-models.md`.

The defaults in 0.15.46: code, prose, and judgment go to Claude Opus 5.5 at `xhigh` effort, and the README says "no role runs above xhigh." So `xhigh` is the cap, not the top level. The default review panel has three seats: Claude Fable 5.2, Claude Opus 5.5, and Gemini 4 Neon.

Why a panel? Because several skills, like `/interrogate`, work by having **different models try to break your diff**, keeping only findings a run actually proves. The idea is that one model's blind spot gets caught by another. But look at who sits on the panel. Two of the three seats are Anthropic models, and pstack's own setup file says it directly: "Fable and Opus are one vendor." In Claude Code it goes one step further. A Gemini seat cannot run there, so pstack's Claude Code guide maps any non-Claude seat to your session model. That means in Claude Code, all three seats are Claude by default. Models from the same company tend to miss the same things, so this is a weaker check than the word "panel" suggests. If you want a second opinion from another company's model, plan for it yourself. (I got this from reading the files, not from a run.)

You only override what you want; every skill falls back to defaults when the config is absent.

## Step 3: what you just installed

The tree, condensed:

```
pstack/
├── skills/
│   ├── poteto-mode/        # the router + 22 playbooks
│   ├── principle-*/        # 24 one-line principles
│   └── ...                 # 33 task skills (/how, /tdd, /arena, ...)
└── agents/
    ├── poteto-agent.md     # subagent that reads the full rules first
    └── comment-sicko.md    # read-only comment reviewer
```

Three layers, top to bottom:

**The router: `/poteto-mode`.** The name is literal: "work like poteto." This is the entry point. You type `/poteto-mode` followed by a plain-language task, and it picks a recipe.

**22 playbooks.** One per task type: bug fix, feature, refactoring, perf, prototype, overnight autonomous run, opening a PR, and so on. Think of each as a recipe card. The bug fix card says, in order: reproduce, find the root cause, fix, verify again with runtime evidence.

**24 principles.** One line each. "Subtract before you add." "Fix the root cause, and a guard is a fix only when the state it handles is legitimate." "Encode the domain in a structure instead of scattered conditionals."

The mental model that clicked for me: imagine the best senior engineer you know. She never fixes a bug the moment it is reported; she reproduces it first. She clicks through the fix herself before saying "done." She changes the minimum amount of code. If you wrote down every one of her habits and handed the document to a new hire, the hire would start working a little like her. pstack is that document, aimed at an agent.

One deliberate omission: there is no planning skill. The README says Cursor's own plan mode works fine with pstack, and then: "personally, i don't believe in planning. the best spec is code." If you want a plan anyway, there is a multi-phase plan playbook, but planning is not the default.

## Step 4: the bug-fix playbook, one step at a time

This is the part nobody shows, so here is the bug-fix playbook applied to a made-up example. Again, this is what the playbook text tells the agent to do. I did not record a real run. Say you have a todo app and a bug: checking a todo as done does not survive a refresh.

**You type:**

```
/poteto-mode marking a todo done doesn't survive a refresh. repro first, then fix and verify.
```

**The router opens a todo list, and the first items are the playbook steps, copied in.** Not summarized. Copied: reproduce, narrow the cause, plan the fix, verify on the same surface, stage the commits, open the PR. This looks like extra paperwork, but it is the first real mechanism. The steps are on the list before any work starts, so the order is fixed up front, and at the end you can hold the agent's report up against the list.

**Reproduce before fixing.** The playbook says to reproduce the bug yourself "on the matching surface via the control skill." Here is a detail the hype skips: that control skill is not in pstack. The README lists `control-ui` (browser, Electron, web) and `control-cli` under "not shipped here"; they come in Cursor's `cursor-team-kit` plugin. The other way is to build one for your own app with `create-verification-skill` (next section). With one of those in place, the agent launches your app, checks a todo, refreshes, and captures the failure as evidence. No fix attempt before reproduction. This alone removes the most common AI failure mode: reading the code, guessing the cause, and patching the guess.

**Narrow the cause.** Is the check not saved, or saved but overwritten on load? The playbook says to binary-search: list the candidate causes, then rule them out one at a time with logs and runtime evidence, instead of fixing by feel. Say the answer is: on startup, the app writes an empty list over storage before reading it.

**Fix the minimum.** Only that spot gets touched. The playbook carries a sentence I want framed: belt-and-suspenders code that "might help" is a hypothesis, not a fix, and it does not ship. When a model does not know the cause, it sprinkles defensive code everywhere, the symptom disappears, the code is a mess, and the real cause is still hiding. pstack bans the sprinkle.

**Verify on the same surface.** The original reproduction runs again, the same way, and this time the checked state survives the refresh. The playbook is strict here: "inconclusive" or the wrong surface is not a pass, and unit tests show branch behavior, not that the bug is gone. "It should work now" is not a pass; a screenshot is.

**Commit in an order that tells the story.** The failing repro or test lands first, and the fix goes on top. Anyone reading the history later sees the failure, then the fix. (The playbook lets the agent skip the test when it would be expensive or unclear.)

**Open the PR.** The body is a short briefing, under 40 lines, with fixed headings: Why, What changed, Scope, Tradeoffs, Blast Radius, Verification.

Two more things happen behind the scenes. The fix is written by a **subagent** (a fresh agent given one slice of work), while the main chat stays in the lead and reviews. And that subagent is not a generic helper: pstack's `poteto-agent` reads the full poteto-mode rules before it touches anything, so parallel workers start from the same rules. The README warns that a generic subagent skips that read, and the behavior drifts.

The same motion works for features. One principle fires that I wish more codebases enforced: do not spray state across booleans. Ask a naive agent for "overdue todos in red" and it adds an `isOverdue` flag next to `isDone`, and now "done but overdue" is a state your UI has to deal with. The `model-the-domain` principle says: status is open or done, overdue is computed from the date. Illegal states become impossible to write instead of merely handled.

## The rule that disappeared last week

Until November 15, the router had one more rule, and it was the cleverest sentence in the bundle. `poteto-mode` said: "A step you choose not to do stays in the list with a one-line `skip: <reason>`." An agent could not quietly drop a step. It had to leave the step in the list and write down why. Agents love to skip tedious steps, and verification is the most tedious step of all, so a rule that turns every skip into a written excuse does a lot of work for one sentence.

On November 16 that sentence was deleted, in a commit titled "shorter skill texts, worker.md, and Opus-first routing capped at xhigh" (#1249). It is not anywhere in 0.15.46; I searched every file. The same commit also changed the default models.

This matters even if you never install pstack:

- **Two people reading this post can have different pstack.** Claude Code leaves auto-update off for third-party plugins by default. If you installed pstack in early November and never updated, your todo list still has `skip: <reason>`. If you install it today, it does not.
- **A rule you liked can vanish in a cleanup commit.** Nothing in the README tells you it is gone. You only find out by reading the diff.
- **So pin the version, and read the diff before you update.** Treat a skill bundle like any other dependency.

## Step 5: the skill worth stealing

Of the 33 task skills, this is the one I would take first. `/create-verification-skill` is a skill that writes a skill.

The problem it solves: agents forget everything between sessions, and without instructions your agent stops at "the build passes." This skill makes the agent produce a handover document for your app, written for the next agent who has never seen it. The process, straight from the file:

1. **Interview the repository, not the user.** The agent answers from the code: what does a user touch (web UI, CLI, API)? What command starts it? How can it be driven by a program (existing Playwright specs first, a generic browser harness second)? What evidence can be captured (screenshots, logs, database state)?
2. **Write `.cursor/skills/verify-<app>/SKILL.md`** (`.claude/skills/...` in Claude Code) with real commands and real selectors from your repo, in fixed sections: Launch (the exact start command and how to know it is ready), Doctor (one read-only "is this instance worth driving" check), Drive, Evidence, Cleanup.
3. **Seed a feature map**: one markdown file per user-facing feature, starting with the top three to five, answering how to reach it, how to drive it, and what visible end state proves it works.
4. **Prove it before handing it over.** The agent runs its own document end to end once: launch, drive one feature, capture evidence, clean up. The file says it directly: "a generated skill that was never executed is a draft, not a deliverable."

Once this exists, the "reproduce" and "verify" steps from Step 4 have something to drive. The agent can launch your app, click through the scenario, and finish with screenshots attached instead of "it should work." The feature map works as saved memory, so the agent does not have to re-read the whole codebase every session.

If you are thinking "that is just E2E testing," the difference matters. E2E tests check that what used to work has not broken. The verification skill checks that the thing the agent just built actually works, by having the agent operate the app itself. Already have Playwright tests? The skill reuses them. But the warning cuts both ways: if you cannot tell that the generated skill is clicking the wrong button, you have just automated the production of nice-looking screenshots. Understand the principle, then install the tool.

To be honest about my own limits here: I have not run this generator yet, so I cannot tell you how good its first draft is on a real app. That is the next thing I want to measure.

## The rule underneath everything

Buried in pstack is the idea I consider the real lesson, and it matches what I have been writing here about agentic coding. When your agent repeats a mistake, **where** you put the correction decides how strongly it holds. The `/correct` skill writes the order down: fix each repeated mistake at the highest level that works.

1. **Architecture and code.** The bad pattern is impossible to write.
2. **Types, lint, CI.** A machine rejects it.
3. **Tests.**
4. **Docs and rules files.** A sentence asks nicely.

A "don't add comments" line in your rules file is layer 4. I want to be careful here, because I have measured this layer. In [my test of where agent refusals should live](/blog/2026-09-26-where-should-agent-refusals-live.html), a clear rule written in the prompt held every time, across five models, for single requests. The bigger gap was the rules nobody wrote down. That test did not cover a long run with many steps, so I cannot tell you how well a written rule holds there. But it points the same way as pstack: a sentence only covers what you thought to write, and a check in code covers every call, whatever the model. That is also why I [put my push gate in code](/blog/2026-10-09-push-only-after-green-tests.html).

A lint rule is layer 2. Tan's team went to layer 1: in [her talk](https://x.com/poteto/status/2102050467505430555), she describes banning comments in their internal framework. The reasoning is the part to remember: **an agent copies whatever it sees in the codebase.** One "temporary, fix later" comment teaches it that sloppy is fine here. So her advice is to delete existing tech debt too, because agents will copy it. If it should not be copied, it should not be visible.

Two more points follow. Automation goes last: pstack even ships a Slack automation, benny, that triages bug reports and fixes confirmed bugs, but it ships turned off and you set it up yourself. On a young codebase, auto-generated fix PRs just spread slop faster. And scale follows trust: a hundred agents you cannot trust produce a hundred times the bad PRs. Her framing in the talk is better than mine: not a software factory, a Michelin kitchen, where every plate that leaves has a chef responsible for it.

## When not to use it, and the honest limits

Short list, because it matters as much as the rest:

- **Small chores.** A button color change does not need reproduction, verification, and a PR. The README itself says to use `/poteto-mode` for work "that requires rigor."
- **Solo projects that push to main.** Every playbook ends by opening a PR. If that is not your flow, the default fights you.
- **Cost.** Subagents and multi-model panels burn tokens. I have not measured how much for a typical task, so I will not guess a number. Measure it on your own repo before you turn it on everywhere.
- **Prose is not enforcement.** "No merge without verification" is a sentence, not a mechanism. That is exactly the layer-4 problem above, and it is why the author pushes lessons down to lint and architecture wherever possible. The deleted skip rule shows the other side of it: prose can also just disappear in an update.
- **Better models shrink the gap.** Recent commits keep shortening the skill texts. The lasting value is not the tips; it is the forced order of operations and the demand for evidence.

## Verdict

pstack is one strong engineer's working habits, written down carefully enough that an agent can follow them. The amount of prose is not the point. The point is three small mechanisms: a router that a person has to start, a todo list that begins with the playbook steps copied in, and evidence demanded before "done."

Take `create-verification-skill` even if you take nothing else. Without a way to drive your app, the "reproduce" and "verify" steps have nothing to stand on. Take the layer rule too: push every repeated correction as far down as you can, and clean the codebase of anything you would not want copied. And pin the version, because the bundle you read about is not always the bundle you install.

The last step is built in: run `/automate-me` and it mines your own transcripts to draft a `<your-name>-mode` skill that routes through pstack underneath. The goal was never to work like Lauren Tan. It is to understand the principles well enough to build your own harness.
