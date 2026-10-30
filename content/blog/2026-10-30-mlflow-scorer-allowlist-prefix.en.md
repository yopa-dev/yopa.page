---
title: "MLflow's Scorer Allow-List Checked the Name, Not Where the File Came From"
date: 2026-10-30T11:00:00-04:00
author: Yoonsoo Park
description: "MLflow 3.12.0 through 3.16.x let an unauthenticated caller run Python on the tracking server. The scorer allow-list accepted any module whose name started with an allowed package, and MLflow's own artifact upload could put a file under that package. I rebuilt both versions of the check with a harmless marker: the 3.16.1 prefix check let the uploaded file's code run, and the 3.17.0 exact-match check refused it. The 3.17.0 diff also closes a second path through the metric name that the advisory does not walk through."
categories:
  - Security
  - Python
tags:
  - Security
  - Python
  - Machine Learning
  - measured
---

On 2026-10-09 the MLflow project published [GHSA-26p8-2jq9-3vq9](https://github.com/mlflow/mlflow/security/advisories/GHSA-26p8-2jq9-3vq9), rated critical. MLflow is an open-source platform for tracking machine learning experiments, and many teams run its tracking server inside their network with no login in front of it. The advisory says that on versions 3.12.0rc0 up to (but not including) 3.17.0, anyone who can reach that server can make it run their Python code.

The part worth learning from is one sentence in the advisory:

> A package-name prefix is not a provenance boundary.

The check that was supposed to stop this looked at a module's *name*. It never asked where the file behind that name came from. I wanted to see that gap for myself without running an exploit against a real server, so I rebuilt the check from both versions of MLflow and pointed it at a throwaway package tree.

The short version:

1. **The 3.16.1 check accepted a file the caller had uploaded.** The uploaded module's name started with an allowed package, so it passed. Its constructor ran and wrote my marker file.
2. **The 3.17.0 check refused the same file.** It only accepts names that are exactly on the list.
3. **There was a second path through the metric name.** In 3.16.1 the deepeval wrapper builds an import from the caller's metric name. A name with a dot in it imported a module I had placed under the package. Version 3.17.0 now rejects any metric name that isn't a plain Python identifier.
4. **The fix in your hands is an upgrade.** 3.17.0 shipped on 2026-10-07, and 3.17.2 is the newest release as I write this. If you can't upgrade today, the server process should not be able to write into its own installed packages.

## What the advisory reports, and what I checked

Everything in this table comes from the advisory. The right-hand column says whether I checked it and how.

| Claim (GHSA-26p8-2jq9-3vq9) | What I did |
|---|---|
| Affected `>= 3.12.0rc0, < 3.17.0`, patched in 3.17.0 | Checked PyPI: 3.12.0rc0 was uploaded 2026-04-27 and 3.17.0 on 2026-10-07 (UTC) |
| The allow-list accepts "an exact root or any descendant" | Confirmed in the 3.16.1 source on PyPI (below) |
| An HTTP caller can place a `.py` file under an allowed package through experiment, run and artifact-upload endpoints | Not reproduced against a server. I reproduced only the import step. |
| On the official v3.14.0 image this runs as uid 0 with no credentials | Reported by the advisory, not checked |
| With basic auth on, the scorer endpoint uses `validate_gateway_proxy` and skips a per-experiment permission check | Reported by the advisory, not checked |
| A read-only filesystem, or a scorer package owned by another user, blocks this exact chain | Consistent with my test: the chain needs a writable directory under the package |

## How the check worked

When a request asks the server to run a third-party scorer, MLflow 3.16.1 reads a module path and a class name from the request. It checks the path against four allowed packages, imports it, and builds the class. This is the code from `mlflow/genai/scorers/base.py` in the 3.16.1 source distribution:

```python
if not any(
    module_path == m or module_path.startswith(m + ".")
    for m in THIRD_PARTY_SCORER_ALLOWED_MODULES
):
    raise MlflowException.invalid_parameter_value(...)
...
module = importlib.import_module(module_path)
scorer_class = getattr(module, class_name, None)
```

The four allowed packages were `mlflow.genai.scorers.ragas`, `.deepeval`, `.trulens` and `.phoenix`. "Starts with an allowed package" sounds safe if you picture only the files that ship with MLflow. The advisory's point is that MLflow itself will create new files there. A file-backed experiment stores each run's uploads at `<artifact_location>/<run_id>/artifacts/`. If the caller sets the experiment's artifact location to the installed `trulens` package directory, an uploaded `audit_x.py` becomes importable as `mlflow.genai.scorers.trulens.<run_id>.artifacts.audit_x`. That name starts with an allowed package, so it passes.

`importlib.import_module` runs the module's top-level code, and building the class runs its constructor. Both happen before MLflow checks whether the class is actually a scorer.

## Setup

- Python 3.13.5 on a Linux box. Standard library only.
- No MLflow install, no server, no network and no cloud account. The scripts recreate the check in a throwaway package called `simml`.
- The "uploaded" module only writes a random 16-character marker into a temp directory. "Did the uploaded code run?" means "was the marker written, with the right value?"
- The real MLflow 3.16.1 and 3.17.0 source distributions came from PyPI with `pip download --no-deps --no-binary :all:`. I used them only to read and diff the source.
- Code and raw output: [ypark9/yopa-experiments, `experiment/mlflow-scorer-allowlist-20261030`](https://github.com/ypark9/yopa-experiments/tree/experiment/mlflow-scorer-allowlist-20261030/2026-10-30-mlflow-scorer-allowlist), commit `4348797`.

## Result 1: prefix match against exact match

I tried three module paths against each version of the check:

| Module the request named | 3.16.1 check: allowed? | 3.16.1: did the uploaded code run? | 3.17.0 check: allowed? | 3.17.0: did the uploaded code run? |
|---|---|---|---|---|
| A real scorer module that ships with the package | Yes | No (nothing uploaded was involved) | Yes | No |
| A file the caller uploaded as a run artifact under an allowed package | **Yes** | **Yes, marker written** | No | No |
| A module outside every allowed package (`json`) | No | No | No | No |

Takeaway: both checks block a module from somewhere else entirely. Only the prefix check lets an uploaded file run, because the upload went *inside* an allowed package.

## Result 2: the metric name was a second path

The 3.17.0 diff adds two checks that the advisory doesn't describe. The first one caught my eye. In 3.16.1, when the deepeval wrapper sees a metric name that isn't in its registry, it builds the import from that name. This is from `mlflow/genai/scorers/deepeval/registry.py` in 3.16.1:

```python
module_path = "deepeval.metrics"
class_name = f"{metric_name}Metric"

module = __import__(module_path, fromlist=[class_name])
```

`__import__` with a `fromlist` entry tries to import that entry as a submodule when the package has no attribute by that name. So I asked: if the metric name contains a dot, does Python import a file the caller placed under the package? I tested this with a throwaway package, not with deepeval:

| Metric name in the request | Passes the 3.17.0 `isidentifier()` check? | Did the placed file's code run? |
|---|---|---|
| `Faithfulness` (a real metric name) | Yes | No |
| `upload.probe` (contains a dot) | **No** | **Yes, marker written** |

Takeaway: a dotted metric name reached a placed file through plain Python import rules, and the new identifier check turns that name away before the import. I did not test this path end to end with deepeval installed. The test shows only that the mechanism the 3.17.0 code comment describes is real.

## What 3.17.0 changed

The same block in 3.17.0 has three checks where 3.16.1 had one:

```python
# Exact match only: a dotted descendant of an allow-listed package can be a
# caller-placed file (e.g. a run artifact under a `file://` experiment root),
# and `import_module` would execute it before the class check below.
if module_path not in THIRD_PARTY_SCORER_ALLOWED_MODULES:
    raise ...
if not metric_name.isidentifier():
    raise ...
if "metric_name" in (data.get("kwargs") or {}):
    raise ...
```

The allow-list grew from 4 entries to 14. Every real submodule a scorer needs is now spelled out by name (for example `mlflow.genai.scorers.ragas.scorers.rag_metrics`), so nothing needs to match by prefix any more. The third check stops a `metric_name` passed in `kwargs` from overriding the value that was just checked. I read that check but did not test it.

## What I did not test

- I did not run an MLflow server or the advisory's proof of concept. My test reproduces the import decision, not the HTTP chain that places the file.
- I did not test the authenticated case, the uid 0 claim, or the `validate_gateway_proxy` mapping.
- I did not install deepeval, ragas, TruLens or Phoenix.
- I diffed only 3.16.1 and 3.17.0. The advisory says the behavior appeared in 3.12.0; I did not open 3.12 through 3.15.

## What to do

**1. Find out which version your server runs and whether it can write into its own scorer packages.** This is read-only. Run it as the same operating-system user that runs `mlflow server`, in the same Python environment:

```sh
set -eu
python3 - <<'PY'
import os
import mlflow
import mlflow.genai.scorers as scorers

print("mlflow", mlflow.__version__)
base = os.path.dirname(scorers.__file__)
for sub in ("ragas", "deepeval", "trulens", "phoenix"):
    path = os.path.join(base, sub)
    state = "WRITABLE" if os.access(path, os.W_OK) else "read-only"
    print(f"{sub:9} {state}  {path}")
PY
```

If the version is below 3.17.0 and any line says `WRITABLE`, the server has both halves of the advisory's chain.

**2. Upgrade.** `pip install --upgrade 'mlflow>=3.17.0'` in the server's environment, then restart the server. If you use the official container image, move to a 3.17 tag.

**3. If you can't upgrade today, take away the write half.** Run the server as a user that doesn't own its `site-packages` directory, or use a read-only root filesystem for the container. The advisory names both as blocking this chain. Don't expose an unauthenticated tracking server beyond the machines that need it.

**4. In your own code, don't treat a name prefix as a trust boundary.** If a request picks a module to import, compare it against an exact list. A prefix check is only as safe as every directory under that prefix, and you don't control what other code writes there.

## Cost

Everything ran on one Linux box. There were no cloud resources and no paid APIs. The experiments repository runs a GitHub Actions job that scans for identifiers such as account numbers. It doesn't touch any cloud account.

## References

- [GHSA-26p8-2jq9-3vq9: Remote code execution on unauthenticated MLflow servers via third-party scorer deserialization](https://github.com/mlflow/mlflow/security/advisories/GHSA-26p8-2jq9-3vq9), published 2026-10-09
- [mlflow on PyPI](https://pypi.org/project/mlflow/): release dates for 3.12.0rc0, 3.16.1, 3.17.0 and 3.17.2
- [Experiment code and raw output](https://github.com/ypark9/yopa-experiments/tree/experiment/mlflow-scorer-allowlist-20261030/2026-10-30-mlflow-scorer-allowlist), commit `4348797`
