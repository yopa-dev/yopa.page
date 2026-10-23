---
title: "Push Only After Green Tests: Where Should My Agent's Gate Keep the History?"
date: 2026-10-09T09:00:00-04:00
author: Yoonsoo Park
description: "A per-call gate cannot check 'tests passed in the last 15 minutes'. I ran the same twelve traces through a stateless gate, a small in-memory check, and AWS's new Dogwood Local Engine. The stateless gate let five bad pushes through. The in-memory check forgot everything on restart. Dogwood got both right, but only after I scoped the policy to the repo and commit: the launch post's version let a green run on one repo unlock a push on another. It also blocked good pushes after a policy reload, and its cost depends far more on the window than on the disk."
categories:
  - AI Agents
  - Security
  - Architecture
tags:
  - AI Agents
  - Security
  - authorization
  - tool-calling
  - Rust
---

Two weeks ago I measured [where an agent's refusal should live](/blog/2026-09-26-where-should-agent-refusals-live.html) and ended up recommending a small deterministic gate in front of the tools. That gate had one weakness I wrote down and then left alone: it only sees the call. It does not know what happened before.

Some rules are all about what happened before. The one every coding agent needs: **push only if the tests passed in the last 15 minutes and nothing has failed since.** A gate that reads only the push request cannot check that.

On 2026-09-30 AWS released the [Dogwood Local Engine](https://aws.amazon.com/blogs/opensource/introducing-the-dogwood-local-engine-temporal-governance-for-agent-actions/), an Apache-2.0 Rust library that decides each tool call against policies that can look back at earlier calls and their results. Its launch post uses exactly this rule, minus one detail that turned out to matter. So the question for me was not "is Dogwood good". It was: **if my gate needs history, do I keep it myself, or do I embed an engine like this, and what does each choice cost per tool call?**

## Short answer

- A per-call gate cannot enforce a "recently passed" rule. It can only trust what the agent writes in the request. In my test it allowed 5 of 6 pushes that should have been blocked.
- A small in-memory check, keyed by repo and commit, gets every rule right until the harness restarts. Then it blocks a push that should have gone through, because it forgot the test run.
- **The policy in the launch post does not say which repo or commit the tests were for.** When one history covers more than one repo or commit, that policy let a green run on repo A allow a push on repo B, let a green run on commit X allow a push of commit Y, and let a failure on repo B block a good push on repo A. Adding repo and commit conditions to the policy fixed all three.
- With those conditions, Dogwood got every trace right, including after a restart. But **re-applying the same policy set, or changing one policy, wiped the history**, and good pushes were blocked until the tests ran again. That is documented, deliberate, and easy to miss.
- Cost per decision is small with a 15-minute window: about 0.48 to 0.85 ms on disk. With a 24-hour window it grew with session length, to about 24 ms or 330 ms at 12 hours depending on how many matching events were in the window. The repo and commit conditions made the 24-hour case 18 to 32% slower than the unscoped policy. For scale, trials in my earlier agent experiment took a median of 2 to 6 seconds each.

## The setup

One rule, three gates, twelve event traces. Nothing runs: no git, no tests, no model. The harness feeds fake events to each gate and records the verdict on the last push. The clock is injected, so "17 minutes later" takes no real time.

| Gate | What it is | What it can see |
| --- | --- | --- |
| A, stateless | A per-call check, the shape of a Cedar rule on a gateway | Only the push request. The best it can do is trust a `tests_passed` field the agent fills in. |
| B, in-memory | A few lines in the harness: remember the last test result and its time for each repo and commit | Everything since the process started |
| C, Dogwood | `dogwood-local-engine` 1.0 tree (commit `d2cba92`), durable store on disk, the policy from the AWS post scoped to the repo and commit | Everything it was shown, kept on disk |

I also ran the launch post's policy unchanged on the same traces, as a fourth column. This is that policy:

```text
@id("push_after_green_tests")
permit (principal, action == Sandbox::Action::"git:push", resource)
when temporal {
    !Sandbox::Action::"tests"::response{ output.passed: false }
    since within 15m
    Sandbox::Action::"tests"::response{ output.passed: true }
};
```

Read it literally: "some test run passed in the last 15 minutes, and no test run has failed since." Some test run of what? It does not say. If one engine sees one agent working on one repo, that is fine. If the history is shared, by several agents, several repos, or several branches, any green run counts for any push.

The engine's README shows the fix in its own example, a rule that a user may read only after they logged in. The condition carries `input.user: context.input.user`, and the README says that this correlation is what makes the policy mean "the same user" rather than "anyone". The official Dogwood examples do the same thing for "the same principal".

So I added a repo and the tested commit to both actions in the schema:

```text
type TestInput  = { suite: String, repo: String, sha: String };
type TestOutput = { passed: Bool };
type PushInput  = { ref: String, repo: String, sha: String, tests_passed: Bool };
```

And required both halves of the condition to match the push:

```text
@id("push_after_green_tests")
permit (principal, action == Sandbox::Action::"git:push", resource)
when temporal {
    !Sandbox::Action::"tests"::response{ input.repo: context.input.repo, input.sha: context.input.sha, output.passed: false }
    since within 15m
    Sandbox::Action::"tests"::response{ input.repo: context.input.repo, input.sha: context.input.sha, output.passed: true }
};
```

In plain words: `input.repo` is the repo written on the earlier test result, and `context.input.repo` is the repo on the push being decided. The two must be equal, and the same for the commit. Now the rule reads "a test run of this repo at this commit passed in the last 15 minutes, and no run of this repo at this commit has failed since." This is gate C.

This only helps if the harness fills in `repo` and `sha` itself, from the checkout it actually tested and the commit it is actually pushing. If the agent can write them, it can name the green commit and push a different one.

Gate B is what most of us would write first, with the same scoping:

```rust
fn push_allowed(last: &HashMap<(String, String), (bool, i64)>, repo: &str, sha: &str, now: i64) -> bool {
    matches!(last.get(&(repo.to_string(), sha.to_string())),
             Some(&(true, ts)) if now - ts <= 15 * 60 * SEC)
}
```

Every test result overwrites the entry for its repo and commit, so "the latest run of this commit passed" also means "nothing has failed on it since". Gate A has no history, so it still trusts the `tests_passed` field the agent writes.

## Result 1: who gets the verdict right

"Rule says" is what the owner of the rule wants. A mark means the gate disagreed.

| Trace | What happens | Rule says | A stateless | B in-memory | C Dogwood, scoped | Launch post policy, unscoped |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | Tests fail, push 5 s later | DENY | DENY | DENY | DENY | DENY |
| T2 | Tests pass, push 5 s later | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| T3 | Tests pass, push 17 min later | DENY | **ALLOW** | DENY | DENY | DENY |
| T4 | Pass, then fail, then push | DENY | **ALLOW** | DENY | DENY | DENY |
| T5 | No test run, agent claims they passed | DENY | **ALLOW** | DENY | DENY | DENY |
| T6 | Tests pass, harness restarts, push | ALLOW | ALLOW | **DENY** | ALLOW | ALLOW |
| T7 | Tests pass, owner re-applies the same policies with `install()`, push | ALLOW | ALLOW | ALLOW | **DENY** | **DENY** |
| T8 | Tests pass, owner widens the push window to 30 min with `batch(Update)`, push | ALLOW | ALLOW | ALLOW | **DENY** | **DENY** |
| T9 | Same as T8, then tests run again, push | ALLOW | ALLOW | ALLOW | ALLOW | ALLOW |
| T10 | Tests pass on repo A, push on repo B | DENY | **ALLOW** | DENY | DENY | **ALLOW** |
| T11 | Tests pass on commit X, push commit Y in the same repo | DENY | **ALLOW** | DENY | DENY | **ALLOW** |
| T12 | Tests pass on repo A, fail on repo B, push repo A | ALLOW | ALLOW | ALLOW | ALLOW | **DENY** |

T1 to T9 use one repo and one commit. T10 to T12 are the shared-history cases.

Gate A's misses are the point of this post. In T5 nothing was tested at all; the agent just said so. My [older post on irreversible actions](/blog/2026-08-24-gate-irreversible-actions-in-code.html) has the rule for this: if the model can write the token that unlocks the action, it is not a gate. A `tests_passed: true` field is that token.

Gate B's miss is the honest cost of the simple version. It fails closed, so the restart in T6 cost one extra test run, not a bad push. Whether that matters depends on how often your harness restarts and how slow your tests are.

The last column is the pitfall I almost shipped. On one repo and one commit, the launch post's policy matches the scoped one on every trace. Once the history is shared, it fails in both directions. In T10 it allowed a push to repo B because repo A had just gone green, which is exactly the bad push the rule exists to stop. T11 is the same hole inside one repo: the agent tests one commit, then pushes another. In T12 it blocked a good push to repo A because repo B's tests failed, since "no run has failed since" also counts every repo. The scoped policy got all three right, and so did gate B once it was keyed the same way.

## Result 2: two things about Dogwood the launch post does not stress

**Re-applying policies resets their history.** T7 is the one that surprised me. I called `install()` again with the exact same policy text, the way a deploy script or a config reload would, and the next push was denied. The source says this is intended. This is the comment on `install` in the engine's `durable.rs`:

```rust
/// Semantics are **reborn-all**, not prospective: this models
/// `[SetActionSchema; DeleteAll; Add each]` (the declarative path wipes and
/// rebuilds, so *every* resulting
/// policy is born fresh with an empty window). To *keep* unchanged policies'
/// history, use `batch` with targeted verbs, which leaves unmentioned
/// policies untouched; this method deliberately does not.
```

In plain words: `install()` deletes every policy and adds them back, so every policy forgets what it has seen, even if you passed in the exact same text. If you want history to survive, you have to send only the change with `batch`. Even then, the policy you changed starts over, which is T8. The launch post explains the reason (the engine prunes events it no longer needs, so a new policy cannot look back), but it only shows the single-policy case.

In practice this means a policy change is also a "run the tests again" event. It fails closed, which is the right direction. But if your harness reloads policies on every deploy, your agent will be blocked after every deploy until it runs the tests again, and unless your harness says why, the agent only sees a deny.

**A store refuses to open if the clock went back more than five minutes.** This is the default configuration:

```rust
pub fn new(snapshot_interval: u64) -> Self {
    DurableConfig {
        snapshot_interval,
        clock: Box::new(WallClock),
        max_future_skew: Duration::from_secs(5 * 60),
        // ...
    }
}
```

And this is the check that runs when the store opens:

```rust
let (future_skew, exceeds_allowed) = future_skew_exceeds_allowed(last_ts, now, allowed);
if exceeds_allowed {
    return Err(future_skew_error(last_ts, future_skew, now, allowed));
}
```

So if the newest event on disk is stamped more than five minutes after what the machine's clock says now, the engine returns an error instead of opening. It fails closed: no store, no decisions, until someone fixes the clock or the config.

| Host clock at restart vs last stored event | Store opens? |
| --- | --- |
| 60 s behind | yes |
| 299 s behind | yes |
| 301 s behind | no |
| 600 s behind | no |

The error tells you to fix the host clock or the store. A host that comes back with a stale clock, for example a VM restored from a snapshot before time sync catches up, could leave the agent unable to do anything until someone fixes it.

## Result 3: what a decision costs, next to a model turn

I simulated a 12-hour session at 360 events per hour, the rate in the AWS post, with the scoped policy, and timed each push `submit` call from start to finish. For each hour I report the median of the last 10 pushes in that hour. Each `submit` writes the event to disk before it evaluates. This is the append path in the engine's log:

```rust
/// Durably append one record, returning its assigned offset. Commits with
/// `Durability::Immediate` (fsync) so the record survives a crash before
/// this returns — the atomic transaction boundary.
pub fn append(&self, record: &[u8]) -> Result<u64, LogError> {
    // ...
    txn.set_durability(Durability::Immediate)
```

`Durability::Immediate` means every event waits for an fsync, a forced write to the physical disk, before the call returns. To separate the disk from the evaluation, I ran the same session on `/dev/shm`, which is RAM.

A push is every 30th event, so 12 per hour. The AWS post does not say how many of its events matched the policy, so I ran two mixes. In "dense", the other events alternate between a test request and a passing test result, and each push takes the place of one result: per hour that is 180 test requests, 168 passing results, and 12 pushes. In "sparse", per hour there are 12 test requests, 12 passing results, 324 file reads, and 12 pushes. All of these events use one repo and one commit, so every test result matches the policy.

Median push-decision time, in milliseconds:

| Session length | 15 min window, disk | 24 h window, disk, sparse | 24 h window, disk, dense |
| --- | --- | --- | --- |
| 1 h | 0.54 to 0.78 | 0.60 | 1.9 |
| 4 h | 0.48 to 0.85 | 2.8 | 33.2 |
| 8 h | 0.52 to 0.73 | 11.1 | 143.9 |
| 12 h | 0.54 to 0.70 | 23.7 | 330.5 |

The 15-minute column shows the range across both mixes. On RAM the 15-minute window took 0.13 to 0.33 ms, so more than half of the disk time is the sync. With the 24-hour window, RAM and disk were almost the same (331.4 ms vs 330.5 ms at 12 hours, dense): the time is evaluation, not the disk.

Scoping is not free at the long window. In the same run, the unscoped launch post policy took 249.6 ms at 12 hours (24-hour window, dense, disk) against 330.5 ms scoped, and 20.1 ms against 23.7 ms in the sparse mix. With the 15-minute window the scoped policy was also a little slower, 0.48 to 0.85 ms against 0.39 to 0.72 ms, a gap close to the run-to-run spread.

Two things stand out.

**The window is what grows, and it grows faster than the session.** In the dense run, every doubling of session length made a push decision about four times slower. The AWS post reports 6 ms per decision at 12 hours with a 24-hour window, and the same growing curve. My numbers are not directly comparable to that 6 ms, because we measured different things. AWS reports the engine's evaluation time; I timed the whole `submit` call, which writes the event to disk and then evaluates. Each AWS point is the median of 200 evaluations; each of mine is the median of the last 10 pushes in that hour. On top of that, my box is an 8-vCPU VM, not their server-class host, the AWS post does not say how many of its events matched the policy, and my timed policy carries the repo and commit conditions. The RAM run takes the disk sync out, but the span and the sample are still different. So I read the AWS number and mine as the same direction, not as a check on each other's size.

**Next to a model turn, the short window is free and the long one is not.** In my [refusal experiment](/blog/2026-09-26-where-should-agent-refusals-live.html) the median gap between trial records was 2.0 s for Claude Haiku 4.5, 2.2 s for Amazon Nova Pro, and 5.8 s for Claude Sonnet 5. Each trial includes one to three model calls, so this is an upper bound on one model turn, not a measurement of it. Against 2 seconds, 0.85 ms is noise. 330 ms on every push is about a sixth of a fast turn, and in the dense 24-hour run the average cost of *every* event in hour 12, not just pushes, was 11.3 ms.

The in-memory check, for the record, took about 42 ns per decision.

## So where should the history live

| Your situation | Where I would keep the history |
| --- | --- |
| One harness process, short sessions, restarts are rare, losing history only costs an extra test run | In your own gate, keyed by repo and commit. A few lines, fails closed, about 42 ns. Gate B. |
| History has to survive restarts, several agents or repos share one gate, or you have more than a couple of these rules | An embedded engine like Dogwood, with short windows, and **every history condition tied to the repo and the commit being pushed** (`input.repo: context.input.repo`, `input.sha: context.input.sha`), filled in by the harness, not the agent. Without that, one repo's green run unlocks another repo's push. Treat every policy reload as "history starts now" and tell the agent why it was blocked. |
| The rule needs a long window ("$100 of refunds per day") | Still an engine, but measure it with your own event mix first. Keep the long window on the rarest event you can, and keep high-frequency events out of its scope. |
| You only have a per-call gate | Do not express a history rule as a field the agent fills in. Either add state somewhere the agent cannot write, or leave the rule to a human approval step. |

Whichever you pick, the engine only decides. The harness still has to send it every event, make sure the events are true, and actually block the call on a deny. The [engine's README](https://github.com/dogwood-policy/dogwood-local-engine) lists those duties, and they are the same duties my gate B has.

## What I did not test

- **No real agent, no real tests, no real git.** Fake events only. The verdicts are about the gate logic, not about any model's behavior.
- **Two repos, two commits, one agent.** The shared-history traces are the smallest cases that show the problem. I did not test several agents writing to one engine at the same moment, or branches and rebases where the same change gets a new commit id.
- **One rule.** Dogwood also has `previous`, `count`, and `sum`, and I did not test them.
- **Concurrency and crash in the middle of a write.** I restarted between events, not during one. The engine's own test suite covers crash recovery; I did not try to break it.
- **The latency numbers are from one 8-vCPU VM** with `/tmp` on overlayfs. Your disk will change the 15-minute column. The 24-hour column is mostly CPU.
- **The model-turn numbers come from trial timestamps** in my earlier experiment, not from timing single model calls.
- **I did not wire this into AgentCore Policy or any hosted gateway.** Everything ran locally and cost nothing.

## What to do this week

1. List the rules your agent's gate has that mention time or order: "after", "since", "within", "at most N per day". Each one needs history.
2. For each, find where that history lives today. If the answer is "in a field the agent fills in", that rule is not enforced.
3. If one gate or history serves more than one repo, branch, or agent, check that every "tests passed" condition names the repo and commit being pushed, and that the harness, not the agent, fills those in.
4. If you keep history in memory, restart your harness in the middle of a session and see what your agent is allowed to do.
5. If you try Dogwood, reload your policies once in a test session and check that your agent gets a clear message when the next push is blocked.

## Related posts

- [Your agent's refusal only covers the rules you wrote down](/blog/2026-09-26-where-should-agent-refusals-live.html): the per-call gate this post extends.
- [Irreversible actions cannot be gated by a prompt](/blog/2026-08-24-gate-irreversible-actions-in-code.html): why the check has to be code the model cannot talk past.

## References

- AWS Open Source Blog, [Introducing the Dogwood Local Engine: temporal governance for agent actions](https://aws.amazon.com/blogs/opensource/introducing-the-dogwood-local-engine-temporal-governance-for-agent-actions/), September 30, 2026.
- [dogwood-policy/dogwood-local-engine](https://github.com/dogwood-policy/dogwood-local-engine) on GitHub (Apache-2.0), commit `d2cba92`.
- [dogwood-local-engine on crates.io](https://crates.io/crates/dogwood-local-engine), version 1.0.0.

The harness and the full output of the run used here are in [yopa-experiments](https://github.com/ypark9/yopa-experiments/tree/13785fac5baf9daf546740011b03f383eeefb23e/2026-10-09-push-only-after-green-tests). It ran on 2026-10-09 on a Linux VM with rustc 1.99.0. No cloud resources, no model calls, cost $0.
