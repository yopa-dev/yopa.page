---
title: "A popular LLM package was malware for two hours. Which install line would have pulled it?"
date: 2026-10-23T09:00:00-04:00
author: Yoonsoo Park
description: "LiteLLM 1.107.0 sat on PyPI for about two hours on 2026-10-21 with a credential stealer that ran on every Python start. I rebuilt the window on a local index with a stand-in package and tried nine pip and uv install lines. Unpinned installs and mid-window time gates took the bad release; a known-clean pin, a hash pin, and a cutoff before the bad upload did not."
categories:
  - Python
  - Security
tags:
  - Package Management
  - pip
  - uv
  - Supply Chain
  - measured
---

On 2026-10-21, [LiteLLM](https://docs.litellm.ai/) — an open-source proxy that lets one app talk to many LLM providers — published `litellm==1.107.0` to [PyPI](https://pypi.org/), the public Python package index. For about two hours (11:39–13:23 UTC) that version was the newest release. It was not the code from LiteLLM's public GitHub tag. According to LiteLLM's [incident report](https://docs.litellm.ai/blog/security-incident-oct-21-2026) and [SafeDep's analysis](https://safedep.io/litellm-pypi-compromise-credential-stealer-backdoor/), the wheels carried three extra files in `site-packages`:

- `cook.pth` — a one-line file Python loads at every interpreter start
- `cook.py` — a credential stealer
- `sitecustomize.py` — a backdoor that started a daemon

PyPI removed 1.107.0. I checked the public JSON API on 2026-10-23: the latest version is `1.106.2`, and `1.107.0` is gone. I did **not** download the malicious wheel.

LiteLLM published its [final attack-chain report](https://docs.litellm.ai/blog/security-incident-oct-21-2026-attack-chain) on October 23. It supersedes the initial post's evolving root-cause account; the initial post remains the reference for affected artifacts and remediation. The experiment below tests install behavior, not the attack chain.

The vendor posts answer how the release pipeline was abused. They do not answer the question I care about as someone who installs Python LLM tooling:

**During that two-hour window, which of the install lines teams already use would have installed the bad release, and which refuse by construction?**

So I rebuilt the window on a local index with a stand-in package named `supplydemo`. The "tampered" version only plants a harmless marker through a `.pth` file. No credentials, no outbound calls, no real LiteLLM artifact. Nine strategies. Short answer:

1. **Unpinned `pip install` took the tampered release** (newest wins).
2. **`==` to the bad version took it.** Pinning alone is not a defense if the pin is the bad release or if you resolve to "latest" while it is bad.
3. **`==` to a known-clean version stayed clean.**
4. **`--require-hashes` with only the clean file hash stayed clean,** and refused when the hash did not match the bad wheel.
5. **Time gates only help if the cutoff is before the bad upload.** `uv --exclude-newer` and `pip --uploaded-prior-to` pointed at the incident start installed clean; the same flags pointed at mid-window (after the bad upload) installed tampered.

Code and raw results: [yopa-experiments `experiment/litellm-install-strategies-20261023`](https://github.com/ypark9/yopa-experiments/tree/experiment/litellm-install-strategies-20261023/litellm-install-strategies) (commit `1080a69`).

## What "install strategy" means here

| Term | Meaning in this post |
|---|---|
| Unpinned | `pip install supplydemo` with no version — resolver picks the newest |
| Version pin | `supplydemo==1.0.0` or `==1.1.0` — exact version, still trusts the index bytes |
| Hash pin | `requirements.txt` with `--hash=sha256:…` and `pip install --require-hashes` — version **and** file digest must match |
| Time gate | Only consider artifacts uploaded before a timestamp (`uv --exclude-newer`, `pip --uploaded-prior-to`) |

This extends [Safely update Python project dependencies](/blog/2026-08-01-safe-python-dependency-updates.html) and [Why you should switch to uv](/blog/2026-02-14-Why-You-Should-Switch-to-Uv.html). Those posts cover update loops and tool choice. They do not measure cooldown or hash pinning against a live bad release.

## The local stand-in

A tiny HTTP index on `127.0.0.1` speaks [PEP 691](https://peps.python.org/pep-0691/) JSON and serves two wheels:

| Version | Upload time (UTC) | Behavior |
|---|---|---|
| `1.0.0` (clean) | `2026-10-21T10:44:22Z` | Package only |
| `1.1.0` (tampered) | `2026-10-21T11:40:00Z` | Adds `cook.pth` → `import supplydemo_cook`, which writes `_SUPPLYDEMO_MARKER` |

Incident start (from LiteLLM): `2026-10-21T11:39:51Z`. Mid-window probe: `12:00:00Z`. Environment: Python 3.13.5, pip 26.2.2 in each venv, uv 0.13.0. **No AWS, no paid API.** Cost for the experiment itself: local CPU and disk only.

The tampered `.pth` is the same *shape* SafeDep describes for LiteLLM (`cook.pth` importing a module at startup). The payload is a marker file, not malware:

```text
# cook.pth (fixture)
import supplydemo_cook
```

After each install I start Python once (so `.pth` runs) and record version, whether `cook.pth` exists, and whether the marker file exists.

## Results

| Strategy | Outcome | Version | `cook.pth` | Marker |
|---|---|---|---|---|
| `pip install supplydemo` (unpinned) | installed tampered | 1.1.0 | yes | yes |
| `pip install supplydemo==1.1.0` | installed tampered | 1.1.0 | yes | yes |
| `pip install supplydemo==1.0.0` | installed clean | 1.0.0 | no | no |
| `--require-hashes` with clean hash only | installed clean | 1.0.0 | no | no |
| `--require-hashes` for 1.1.0 with the clean hash | **refused** | — | — | — |
| `uv pip install --exclude-newer 2026-10-21T11:39:51Z` | installed clean | 1.0.0 | no | no |
| `uv pip install --exclude-newer 2026-10-21T12:00:00Z` | installed tampered | 1.1.0 | yes | yes |
| `pip install --uploaded-prior-to 2026-10-21T11:39:51Z` | installed clean | 1.0.0 | no | no |
| `pip install --uploaded-prior-to 2026-10-21T12:00:00Z` | installed tampered | 1.1.0 | yes | yes |

Unpinned install log (resolver picks newest):

```text
Collecting supplydemo
  Downloading supplydemo-1.1.0-py3-none-any.whl (1.4 kB)
Successfully installed supplydemo-1.1.0
```

Time gate cut off before the bad upload (pip):

```text
pip install --uploaded-prior-to 2026-10-21T11:39:51Z supplydemo
# → supplydemo-1.0.0
```

Same flag after the bad upload exists:

```text
pip install --uploaded-prior-to 2026-10-21T12:00:00Z supplydemo
# → supplydemo-1.1.0  (tampered)
```

## What this means for a two-hour window

**If CI or a laptop ran an unpinned install between 11:39 and 13:23 UTC, it would have taken 1.107.0.** That matches LiteLLM's own "who is affected" note.

**A version pin to a release you already trust still works** — here `==1.0.0`. A pin that you update automatically to "latest" during the window does not; it is the unpinned case with extra steps.

**Hash pinning checks the bytes against a digest you already trust.** When the requirements file asked for `1.1.0` but carried the clean wheel's SHA-256, pip refused. That checks a digest mismatch; it does not establish which wheel is safe. A lockfile generated from the malicious wheel would record its hash and accept that same wheel later. The clean GitHub source tag and the compromised PyPI wheels were different artifacts, so the tag's contents alone could not supply a trusted digest for the wheels.

**A time gate is not "use latest, but carefully."** `--exclude-newer T` means *only artifacts uploaded before T*. If T is after the attacker published, the bad wheel is eligible. A rolling 24-hour cooldown would exclude a release only a few hours old. It can admit a malicious release once that release is older than 24 hours and still available, or refuse everything if every candidate is newer than the cutoff. For this roughly two-hour incident, that cooldown would have kept the bad upload out during the exposure window. Age is still not a safety check: use a cutoff before the suspect upload, or digests of artifacts you independently trust.

## What I did not measure

- Real `litellm==1.107.0` (never downloaded).
- Docker tags (`latest` was also compromised per LiteLLM — different channel).
- Whether your lockfile tool writes upload times into the lock (uv lock + `--exclude-newer` in CI is a separate check).
- Enterprise private registries (LiteLLM says those were not hit).

## Practical default after this week

1. **Pin versions you have reviewed**, not "latest".
2. **Prefer hash-pinned requirements or a lockfile that records digests** for anything that runs in CI or on a host with cloud credentials.
3. **If you use a cooldown,** set the cutoff to a time *before* you last trusted the index — and know that a mid-incident "now" still sees the bad wheel.
4. **If you might have installed during the window,** follow LiteLLM's remediation: do not start Python in that environment first; remove `cook.pth` / `cook.py` / `sitecustomize.py` from the shell; rotate credentials the host could reach.

The experiment repo has the fixture wheels, the index server, and `results/matrix.json` so you can replay the nine lines without touching PyPI's LiteLLM project at all.
