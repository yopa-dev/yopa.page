---
title: "Anthropic Left Git at 30,000 Merges a Day. Here Is Where Git Bent First on One Machine."
date: 2026-10-23T11:00:00-04:00
author: Yoonsoo Park
description: "Anthropic replaced git with Scion, an in-house system where commits, merges and history queries happen on the server. I can't check their numbers, but I can measure the git limits they name on one machine: 32 agents pushing to one branch needed 519 to 528 push attempts, a blob:none clone with a full checkout was up to ten times slower than a plain clone and didn't finish at a million files, and a path-limited log on a tree:0 clone made 500 round trips. Here is what each git workaround bought and where it stopped helping."
categories:
  - DevOps
  - AI
tags:
  - Git
  - AI Agents
  - DevOps
  - measured
---

On 2026-10-13 Anthropic published [Redesigning source control at Anthropic](https://www.anthropic.com/research/redesigning-source-control). It explains why the company moved its monorepo from git to Scion, a version control system it built in-house. The headline number is the merge rate:

> In May 2026, Anthropic averaged around 2,500 code changes merged per day; as of September, we merged over 30,000 per day.

Most of us are nowhere near that. The post says so itself: "Scion is by no means a suitable replacement for git for general use." But it also names the specific git workarounds Anthropic used and outgrew: shallow clones, sparse checkouts, promisor remotes (partial clone), mirrors and repository snapshots. Those are tools a normal team reaches for once agents start cloning and pushing all day. So I measured them on one machine, at sizes a normal team could actually reach. I wanted to know which one bends first, and how badly.

The short version:

1. **Pushing to one branch is the first wall, and it grows with the square of the agent count.** When 32 agents pushed to `main` at once, exactly one landed. With a `pull --rebase` retry loop, all 32 got in after 519 to 528 push attempts.
2. **`git status` was not the problem.** At a million files it took 0.91 s warm, and 0.29 s with `-uno`. The built-in file system monitor that would speed it up refused to start on Linux.
3. **A `blob:none` partial clone with a full checkout was slower than a plain clone.** It took 11.4 s against 2.7 s at 100,000 files and 92.6 s against 9.3 s at 300,000. At a million files it hadn't finished after 900 s, where the plain clone took 29.9 s.
4. **A partial clone combined with a sparse checkout was fast.** One directory out of 100 at a million files took 3.3 s to clone.
5. **History commands on partial clones turn into round trips.** `git log -p -n 100` made 100 fetches on a `blob:none` clone. On a `tree:0` clone, `git log -- d000` made 500 fetches and took 110 s, against 0.008 s on a full clone.

## What Anthropic reports, and what I can check

Everything in this section comes from Anthropic's post. I can't verify any of it. These are the claims that matter for this article, quoted or close to it:

| Claim (Anthropic's post, 2026-10-13) | Status |
|---|---|
| ~2,500 merges/day in May 2026, over 30,000/day in September | Reported by Anthropic, not verifiable |
| Main branch history "almost 100 GB", compressed working copy "over 25 GB" | Reported, not verifiable |
| "on the order of 25 million code checkouts per day for CI" | Reported, not verifiable |
| "at our peak, we operated several hundred internal git mirrors" | Reported, not verifiable |
| Partial clones needed "more and more care" to keep "diff and blame, working" | Reported. I measured the general mechanism below. |
| In Scion "every commit, rebase, or merge happens on the server" and refs are discouraged except main and release branches | Design description |
| "There is no equivalent of packfiles ... so no repository maintenance is needed" | Design description |
| Infrastructure "200x smaller" than the git mirrors; CI got "a 25% CPU capacity win" | Reported, not verifiable |
| Built by "a team of seven people" in five months | Reported, not verifiable |

Nothing below measures Scion. What I can measure is the git side of the story: the limits the post says pushed Anthropic away, at a much smaller scale.

## Setup

All of it ran on one Linux machine (8 vCPUs, 15 GB of RAM, a local ext4 disk) with git 2.47.3. Every clone used `file://` with `--no-local`, so git used its real pack transfer instead of copying files. There was no network and no hosted forge.

The repositories are synthetic and built with `git fast-import`. Each has 100 top-level directories of small unique text files, at 10,000, 100,000, 300,000 and 1,000,000 files. Each also has 500 commits that rewrite 20 random files each. That is a short history for a big tree, the opposite of Anthropic's 100 GB of history over 25 GB of working copy. Keep that in mind for the clone numbers.

The code and raw output are in [yopa-experiments at `53b174c`](https://github.com/ypark9/yopa-experiments/tree/53b174c/2026-10-23-git-cliffs-before-scion). Every table here comes from `results/raw.log` through `summarize.py`.

## Cliff 1: everyone pushes to main

This is the one I expect an agent-heavy team to hit first, long before repo size matters. Each of K clones of a 10,000-file repo committed one new file, all in different directories, so there were no content conflicts. Then they all pushed to `main` at the same moment. I ran three trials per K.

| Agents | Landed on the first try | Push attempts until all landed (3 trials) | Most attempts by one agent | Retry time (median) |
|---|---|---|---|---|
| 1 | 1 | 1, 1, 1 | 1 | 0.00 s |
| 2 | 1 | 3, 3, 3 | 2 | 0.23 s |
| 4 | 1 | 10, 10, 9 | 4 | 0.43 s |
| 8 | 1 | 36, 36, 35 | 8 | 1.16 s |
| 16 | 1 | 135, 135, 136 | 16 | 2.97 s |
| 32 | 1 | 528, 519, 525 | 32 | 10.16 s |

In every trial exactly one push won. The others got this:

```text
remote: error: cannot lock ref 'refs/heads/main': is at 91d2bd2d... but expected c817c4f6...
 ! [remote rejected]   HEAD -> main (failed to update ref)
```

The retry loop is `git pull --rebase` followed by `git push`, repeated until the push succeeds. Each round lets one more agent in, so the total is close to K(K+1)/2. For K = 32 that is 528, which one trial hit exactly. The last agent needed 32 attempts. Ten seconds doesn't sound like much, but the setup was favourable. Client and server were on the same disk with no network latency, every commit touched a different file, and nothing ran CI between attempts. Over a real network, each round trip makes the race window wider.

This is where Anthropic's design differs most directly from git. In Scion, commits and merges happen on the server and are cheap, and moving a ref is described as "a compare-and-swap on a single Spanner row". On git, the usual way out is a merge queue or bot that serializes landing. The post also says they "haven't been able to effectively replicate the industry standard of a global repository lock on the merge queue" and moved to post-merge testing instead. I didn't test a merge queue here.

If your agents push straight to one branch, count your push attempts. If the attempts grow much faster than the commits, you have hit this cliff.

## Cliff 2: a big working tree (smaller than I expected)

| Files | Clone + checkout | Index | `status` | `status -uno` | `status` with untracked cache | `sparse-checkout set` to 1 of 100 dirs | `status` after sparse |
|---|---|---|---|---|---|---|---|
| 10,000 | 0.63 s | 1.0 MB | 0.036 s | 0.016 s | 0.026 s | 0.21 s | 0.005 s |
| 100,000 | 2.70 s | 8.9 MB | 0.088 s | 0.034 s | 0.038 s | 1.52 s | 0.061 s |
| 300,000 | 7.97 s | 26.5 MB | 0.206 s | 0.086 s | 0.096 s | 4.87 s | 0.172 s |
| 1,000,000 | 30.16 s | 88.2 MB | 0.908 s | 0.285 s | 0.308 s | 17.12 s | 0.187 s |

These are warm-cache medians of five runs. I didn't drop the page cache on a machine other agents share, so a cold `status` would be slower. At a million files, `status` grows to about a second, and the untracked cache brings it down to about a third of a second. That is slow for an interactive prompt, but it won't stop anyone.

The tool that would help most on a huge tree is git's built-in file system monitor. On this machine it didn't start:

```text
$ git fsmonitor--daemon start
fatal: fsmonitor--daemon not supported on this platform
```

That matches git's build configuration at v2.47.3. `config.mak.uname` sets `FSMONITOR_DAEMON_BACKEND` only for `darwin` and `win32`. Many agent sandboxes are Linux containers, and there this speed-up isn't available.

Two numbers surprised me. First, narrowing a million-file checkout to one directory took 17 s, about half as long as the clone itself. Second, the index stayed at full size after the sparse checkout. I didn't enable `index.sparse`, which is meant for exactly that.

## Cliff 3: partial clone with a full checkout

| Repo | Variant | Clone | `.git` size | Files on disk |
|---|---|---|---|---|
| 100k | full | 2.69 s | 31.4 MB | 100,000 |
| 100k | `--depth 1` | 2.55 s | 27.8 MB | 100,000 |
| 100k | `--filter=blob:none` | 11.42 s | 38.0 MB | 100,000 |
| 100k | `--filter=tree:0` | 11.13 s | 36.1 MB | 100,000 |
| 100k | `--filter=blob:none --sparse`, then 1 dir | 0.49 s + 0.17 s | 14.2 MB | 1,000 |
| 300k | full | 9.32 s | 85.4 MB | 300,000 |
| 300k | `--filter=blob:none` | 92.55 s | 108.4 MB | 300,000 |
| 1M | full | 29.88 s | 274.3 MB | 1,000,000 |
| 1M | `--depth 1` | 29.04 s | 270.7 MB | 1,000,000 |
| 1M | `--filter=blob:none` | **not done after 900 s** | | |
| 1M | `--filter=blob:none --sparse`, then 1 dir | 3.31 s + 1.96 s | 117.0 MB | 10,000 |

A partial clone downloads commits and trees, and then checkout fetches the blobs it needs. Git's [partial clone notes](https://github.com/git/git/blob/v2.47.3/Documentation/technical/partial-clone.txt) say checkout does this in one batch:

> `checkout` (and any other command using `unpack-trees`) has been taught to bulk pre-fetch all required missing blobs in a single batch.

It was still one batch here, but its cost didn't grow in a straight line. Three times the files took eight times as long (11.4 s to 92.6 s). At a million files I killed the first attempt by hand at 798 s and the rerun hit its 900 s timeout. In both cases the `git fetch --stdin` child was at about 100% CPU on the client. I didn't profile it, so I can't say which part of the client is slow. It may also behave differently on a newer git or over HTTPS.

Part of the gap is my synthetic repo. Its history is small, so a partial clone has little to skip. On a history-heavy repo like the one Anthropic describes, `blob:none` saves much more. The useful result is the last row of each size. A partial clone combined with a sparse checkout is the variant that stayed fast, because it never asks for most of the blobs. That 117 MB `.git` at a million files is probably mostly the index, which keeps every entry without `index.sparse` (it was 88 MB in the full checkout). I didn't measure the index in that clone separately.

## Cliff 4: history questions on a partial clone

Anthropic writes that keeping "operations that depend on history, like diff and blame" working on partial clones took more and more care. Git's own notes describe why:

> Dynamic object fetching invokes fetch-pack once *for each item* because most algorithms stumble upon a missing object and need to have it resolved before continuing their work.

I counted those fetches with `GIT_TRACE2_EVENT` on clones of the 100,000-file repo:

| Clone | Command | Time | Lazy fetches |
|---|---|---|---|
| full | `git log -p -n 100` | 0.068 s | 0 |
| `blob:none` | `git log -p -n 100` | 1.801 s | 100 |
| `tree:0` | `git log -p -n 100` | 29.349 s | 200 |
| full | `git log --oneline -- d000` | 0.008 s | 0 |
| `blob:none` | `git log --oneline -- d000` | 0.007 s | 0 |
| `tree:0` | `git log --oneline -- d000` | 109.954 s | 500 |
| full | `git blame d001/s22/f0017201.txt` | 0.027 s | 0 |
| `blob:none` | `git blame d001/s22/f0017201.txt` | 0.065 s | 1 |
| `tree:0` | `git blame d001/s22/f0017201.txt` | 17.017 s | 63 |

That is one fetch per commit for `log -p` on `blob:none`, and about one per commit in the 501-commit history for a path-limited log on `tree:0`. The blame target is the most-changed file in the repo, but it changed only 4 times, so blame got off lightly. My first pass undercounted these numbers. Auto-gc merged the new packs once there were more than 50, so I reran with `gc.auto=0`. Both passes are kept in the raw log.

This is the job Scion moves to the server. The post says jobs "ask the server" for diffs and history instead of keeping a local repo. On git, the closest thing is a forge API or a full clone kept on a CI cache volume. In practice that means either give history-heavy jobs a full clone, or let them ask an API, and use `tree:0` only for jobs that never look back.

## Not a cliff here: repacking

On the million-file bare repo, `git repack -a -d -f` took 13.27 s and `git gc` took 5.61 s. At this size that is routine maintenance. Anthropic's point is that it doesn't scale with their history and mirror count ("no repository maintenance is needed" in Scion). Nothing I built is big enough to show that.

## What I did not measure

- **Scion**, and any of Anthropic's numbers. They are all self-reported.
- **A real network or forge.** Everything ran over `file://` on one disk. Network latency would make the push race and the per-object lazy fetches worse, but that is an expectation, not a measurement.
- **A history-heavy repo.** Mine has 500 commits. The clone comparisons would favour `--depth 1` and `blob:none` much more on a repo with long history.
- **A cold cache, `index.sparse`, Scalar, `git maintenance` schedules, or a newer git than 2.47.3.**
- **A merge queue or server-side merge** as the fix for cliff 1.
- **Why the million-file `blob:none` checkout was slow.** I only measured that it was.

## What to do

- **Don't let many agents push to one branch directly.** Give each agent its own branch or worktree (see [Give Every Agent Its Own Worktree](/blog/2026-08-24-give-every-agent-its-own-worktree.html)) and land through something that serializes merges. Watch the number of push attempts per landed commit.
- **Use partial clone together with sparse checkout, not partial clone alone.** On my repos, `blob:none` with a full checkout was the slowest option, and `blob:none --sparse` was the fastest. For reading part of a repo from a short-lived job, the [Lambda sparse checkout post](/blog/2024-07-31-efficient-github-cloning-in-aws-lambda-sparse-checkout-to-the-rescue.html) uses the same idea.
- **Keep history questions off `tree:0` clones.** Give those jobs a full or `blob:none` clone, or answer them through an API.
- **Don't plan on fsmonitor in Linux containers** with git 2.47. Use `core.untrackedCache` and `status -uno` where they fit.
- **Measure before you migrate.** Every number here came from a script that runs in minutes on one machine. Run it at your own file count and agent count before deciding git is the problem.

## References

- Anthropic, [Redesigning source control at Anthropic](https://www.anthropic.com/research/redesigning-source-control), 2026-10-13.
- git v2.47.3, [Documentation/technical/partial-clone.txt](https://github.com/git/git/blob/v2.47.3/Documentation/technical/partial-clone.txt).
- git v2.47.3, [config.mak.uname](https://github.com/git/git/blob/v2.47.3/config.mak.uname) (`FSMONITOR_DAEMON_BACKEND`).
- Experiment code and raw output: [ypark9/yopa-experiments, `2026-10-23-git-cliffs-before-scion` at `53b174c`](https://github.com/ypark9/yopa-experiments/tree/53b174c/2026-10-23-git-cliffs-before-scion).
