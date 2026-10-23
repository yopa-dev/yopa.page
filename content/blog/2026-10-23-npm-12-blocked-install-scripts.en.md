---
title: "npm 12 Says the Install Worked. Your Native Module Disagrees."
date: 2026-10-23T09:00:00-04:00
author: Yoonsoo Park
description: "npm 12 stops running dependency install scripts, including the implicit node-gyp build, unless you approve them. I measured what that looks like from CI on npm 11.21.1 and 12.2.1: exit code 0, a warning that --silent removes, a review command that reports nothing on a clean checkout, and approvals that stop covering a package after a version bump. One of four real native packages broke. Here is the gate that fails the build instead of the first request."
categories:
  - Node.js
  - DevOps
tags:
  - npm
  - Package Management
  - Supply Chain
  - CI/CD
  - measured
---

npm 12 became the `latest` npm in July 2026. Its headline change is a security default. Dependency lifecycle scripts (`preinstall`, `install`, `postinstall`) no longer run unless the project approves them. That includes the build npm used to start on its own for any package that ships a `binding.gyp` file. GitHub's [release announcement](https://github.blog/changelog/2026-07-08-npm-install-time-security-and-gat-bypass2fa-deprecation/) puts it in one line:

> Dependency lifecycle scripts (i.e., `preinstall`, `install`, `postinstall`) and implicit `node-gyp` builds no longer run unless explicitly allowed.

I think it is a good default. An install script lets any package in your dependency tree run code on the machine during `npm install`, and that is the path npm is closing. But the vendor posts describe the policy, and I wanted to know what it looks like from the pipeline side. When a native dependency is skipped, does anything fail? Which packages actually break? Which check catches it before the first request in production does?

So I measured it with a local registry, two stand-in packages, npm 11.21.1, npm 12.0.0 and npm 12.2.1 (the `latest` tag when I ran this on 2026-10-23), and four real packages from the public registry. The short version:

1. **npm 12 exits 0.** Every module that needed its install script is missing, and the first `require()` fails.
2. **`npm ci --silent` prints nothing at all.** The only signal was a warning, and `--silent` drops it.
3. **npm 11.21.1 prints almost the same warning, but still runs the scripts.** A team that learned to ignore it on npm 11 is likely to ignore it on npm 12 too.
4. **The read-only review command exits 0, and on a clean checkout it says there is nothing to review.**
5. **Approvals are pinned to a version by default.** Bump the dependency and it is blocked again, still with exit 0.
6. **`--strict-allow-scripts` turns an unreviewed script into exit 1.** That is the gate, together with a `require()` smoke test. It already exists on npm 11.21.1, so you can add it before you upgrade.
7. **Of four real native packages, only `sqlite3` broke.** The warning lists packages whose scripts were skipped, not packages that are broken.

Code and raw logs: [yopa-experiments `experiment/npm12-skipped-install-scripts-20261023`](https://github.com/ypark9/yopa-experiments/tree/experiment/npm12-skipped-install-scripts-20261023/npm12-skipped-install-scripts) (final commit `741a425`).

## The words, briefly

| Term | Meaning here |
|---|---|
| Lifecycle script | A command in a package's `package.json` `scripts` that npm runs at install time (`preinstall`, `install`, `postinstall`) |
| Native add-on | A Node module written in C or C++ and compiled to a `.node` file that `require()` loads |
| `node-gyp` | The tool npm uses to compile native add-ons. If a package has a `binding.gyp` and no `install` script, npm used to run `node-gyp rebuild` for it on its own |
| Prebuilt binary | A `.node` file built ahead of time, either shipped inside the package (`prebuilds/`) or downloaded by an install script |
| `allowScripts` | A new field in the root `package.json` that lists which dependencies may run install scripts |

## The setup

A small read-only registry on `127.0.0.1` serves two stand-in packages. Both are shaped like real ones, and neither does anything outside its own folder:

- **`nativedemo`**: fourteen lines of C and a `binding.gyp`, with no install script. Its `index.js` is `module.exports = require('./build/Release/nativedemo.node')`, so it only works if npm compiled it.
- **`postdemo`**: a `postinstall` that writes `generated.js`, which `index.js` requires. This is the shape of ORM clients and tools that download a binary at install time.

```json
{ "name": "postdemo", "version": "1.0.0", "main": "index.js",
  "scripts": { "postinstall": "node gen.js" } }
```

After every install I ran a smoke test: `require()` each package and call it. The registry serves only these tarballs. The real-package runs used the public npm registry. Nothing was published, and no cloud account was involved.

## What the pipeline sees

| Case | npm | Command | Exit | After install |
|---|---|---|---|---|
| c01 | 11.21.1 | `npm install` | 0 | both modules load |
| c02 | 12.2.1 | `npm install` | **0** | both fail: `Cannot find module './build/Release/nativedemo.node'`, `Cannot find module './generated.js'` |
| c03 | 12.2.1 | `npm ci --silent`, lockfile written by npm 11 | **0** | both fail, and the log is empty |
| c05 | 12.2.1 | `npm install --strict-allow-scripts` | **1** | `ESTRICTALLOWSCRIPTS`, nothing installed |
| c06 | 12.0.0 | `npm install` with `strict-allow-scripts=true` in `.npmrc` | 1 | same error on the first npm 12 release |

c03 is the common CI shape: a lockfile from before the npm upgrade, `npm ci`, and a quiet log level. Its entire log is the command line and the exit code:

```text
$ npm ci --silent --registry http://127.0.0.1:4873/ --no-audit --no-fund --cache $TMP/cache12
[exit 0]
```

Without `--silent`, npm 12 does tell you, at the end of the output:

```text
added 2 packages in 206ms
npm warn install-scripts 2 packages had install scripts blocked because they are not covered by allowScripts:
npm warn install-scripts   nativedemo@1.0.0 (install: node-gyp rebuild)
npm warn install-scripts   postdemo@1.0.0 (postinstall: node gen.js)
```

Now compare what npm 11.21.1 printed for the same two packages. It printed this while it **was still running both scripts**:

```text
added 2 packages in 475ms
npm warn install-scripts 2 packages have install scripts not yet covered by allowScripts:
npm warn install-scripts   nativedemo@1.0.0 (install: node-gyp rebuild)
npm warn install-scripts   postdemo@1.0.0 (postinstall: node gen.js)
```

"have install scripts not yet covered" became "had install scripts blocked". Same prefix, same list, same position after the summary line. npm 11.16+ shows the warning so teams can get ready before the upgrade. But if your logs have shown it for weeks with nothing broken, you have learned to skip it. The day the toolchain moves to npm 12, it looks the same and means the opposite.

This is the same trap I hit with [ECS deployments that report "completed" with nothing running](/blog/2026-09-27-ecs-deployment-observability.html). The tool reports what it did, and what it did is not what you needed.

## The review command is not a gate

The docs point you to a read-only listing: `npm install-scripts ls`, or its alias `npm approve-scripts --allow-scripts-pending`. It is useful at a desk. I wanted to know whether it could fail a build.

| Case | When | Output | Exit |
|---|---|---|---|
| c04 | after an install, 2 packages pending | lists both | **0** |
| g5 | fresh checkout, before any install | `No packages with unreviewed install scripts.` | **0** |

It exits 0 when there is something to review, so `&&` will not stop on it. And it reads what is installed in `node_modules`, not the lockfile. On the fresh checkout a CI job starts from, it tells you there is nothing to review. The lockfile does carry the signal: npm 11's lockfile for this project had `"hasInstallScript": true` on both packages. But nothing in npm turns that into a failure unless you use strict mode.

## Approvals are pinned, so a version bump blocks it again

The fix the docs describe works. I measured it:

```bash
npm install-scripts approve nativedemo postdemo
npm rebuild
```

`approve` wrote this into `package.json`:

```json
"allowScripts": { "nativedemo@1.0.0": true, "postdemo@1.0.0": true }
```

`npm rebuild` ran both scripts and both modules loaded (c07). A fresh clone with that `package.json` committed passed `npm ci` and loaded both too (c08).

Then I did what a dependency bot does and bumped `nativedemo` to 1.0.1 (c09):

```text
changed 1 package in 220ms
npm warn install-scripts 1 package had install scripts blocked because they are not covered by allowScripts:
npm warn install-scripts   nativedemo@1.0.1 (install: node-gyp rebuild)
[exit 0]
```

`allowScripts` still said `nativedemo@1.0.0`. The new version was blocked, the install exited 0, and `require('nativedemo')` failed again. Pinned approvals are the safer default, because a new version of a package gets reviewed again. But it means every Dependabot or Renovate PR that bumps a native dependency can pass `npm ci` and break at runtime, unless something in CI fails on unapproved scripts. (`--no-allow-scripts-pin` writes name-only approvals that cover future versions. That trades the review away, and I did not test it.)

## Which real packages actually broke

The warning tells you which packages had scripts skipped. It does not tell you which of them needed those scripts. So I installed four real packages, with four different install shapes, on both npm versions, then loaded each one and called it once:

| Package | How it gets its binary | npm 12 warning? | npm 12.2.1 smoke test |
|---|---|---|---|
| `sqlite3@6.0.1` | `install: prebuild-install -r napi \|\| node-gyp rebuild` downloads or builds it | yes | **FAIL: `Could not locate the bindings file`** |
| `bcrypt@6.0.0` | ships `prebuilds/` in the tarball; `install: node-gyp-build` | yes | ok |
| `esbuild@0.28.2` | platform binary comes from an optional dependency (`@esbuild/linux-x64`); `postinstall` only checks it | yes | ok |
| `better-sqlite3@13.0.3` | ships `prebuilds/`, no install script, `"gypfile": false` | no | ok |

All four worked on npm 11.21.1. On npm 12.2.1 three of the four printed the warning, and one of them was broken. After `npm install-scripts approve sqlite3` and `npm rebuild`, `sqlite3` loaded and opened an in-memory database.

So the honest reading of the warning is "these packages *might* need you". This changes what you do about it:

- **Do not approve everything to make the warning go away.** `bcrypt` and `esbuild` worked without their scripts, so approving them gives install-time code execution back for no benefit. `npm install-scripts approve --all` exists. Turning the default back off for every package is the opposite of why npm changed it.
- **Approve what your smoke test shows you need, and deny the rest.** `npm install-scripts deny <pkg>` records an explicit `false`. Strict mode then stops flagging that package (I measured this below), and per the docs `approve --all` will not turn it back on (I did not test that part).

This was one platform (Linux x86_64, Node 24.22.0). A package whose `prebuilds/` folder does not cover your OS, CPU, or libc will fall back to its install script and can break where it worked for me.

## The gate I would add

Two real steps in CI, after a read-only preflight. The first fails on any dependency with unreviewed install scripts. The second proves that the native modules you depend on load:

```bash
#!/usr/bin/env bash
# usage: ci-gate.sh <native-module> [<native-module> ...]   e.g. ci-gate.sh sqlite3
set -euo pipefail
[ "$#" -ge 1 ] || { echo "usage: $0 <native-module>..." >&2; exit 2; }
# read-only preflight: npm ci needs a lockfile; print the npm version in the log
test -f package-lock.json || { echo "no package-lock.json; refusing to install" >&2; exit 1; }
echo "npm $(npm --version)"
npm ci --strict-allow-scripts
node -e 'for (const m of process.argv.slice(1)) require(m); console.log("loaded:", process.argv.slice(1).join(" "))' "$@"
```

Run it as `ci-gate.sh sqlite3`, with your own native dependencies as the arguments. `npm ci` only writes `node_modules` inside the checkout. When the strict `npm install` failed in c05 and c06, it left no `node_modules` folder behind. g1, g2 and g7 ran this exact file (`scripts/ci-gate.sh` in the experiment repo) against the stand-ins. g3, g4 and g6 ran only the strict `npm ci` step, with a different setup:

| Case | Setup | Exit |
|---|---|---|
| g1 | npm 12.2.1, lockfile with no approvals | **1**, `ESTRICTALLOWSCRIPTS` lists both packages |
| g2 | npm 12.2.1, `allowScripts` committed | 0, `loaded: nativedemo postdemo` |
| g3 | npm 12.2.1, `strict-allow-scripts=true` in the project `.npmrc`, plain `npm ci` | 1 |
| g4 | **npm 11.21.1**, `npm ci --strict-allow-scripts` | 1 |
| g7 | npm 12.2.1, no `package-lock.json` | 1, the preflight refuses before installing |
| g6 | npm 12.2.1, `nativedemo` approved, `postdemo` denied with `false`, strict `npm ci` | **0**, no warning, and `require('postdemo')` fails |

g4 is the useful surprise. The strict flag is already on npm 11.21.1, so you can turn it on now, sort out approvals while npm 11 still runs the scripts, and upgrade npm later. (npm 11.21.1's own warning already points to `npm install-scripts approve`. I did not run `approve` on npm 11.) The `.npmrc` form (g3) is the one to commit, so local installs and CI follow the same rule.

The `require()` line matters even with strict mode on, and g6 shows why. Strict mode checks your policy. A package you denied passes it silently, and the install exits 0. If that package did need its script, only loading it will tell you. The same goes for a prebuilt binary that does not exist for the platform you deploy to.

## What I did not measure

- macOS, Windows, Alpine/musl, or ARM. The real-package results depend on which prebuilt binaries exist for the platform.
- Workspaces and `install-strategy=linked`. npm 12.2.1's changelog has a fix for `allowScripts` keys in linked installs, so behavior there has changed recently.
- pnpm and Yarn, which have their own script policies.
- Docker layer caches that restore an old `node_modules`. Those can hide the change until the cache is invalidated.
- Earlier npm 11 releases. Only 11.21.1 was tested.
- `--no-allow-scripts-pin`, `--dangerously-allow-all-scripts`, and whether `approve --all` respects an earlier `deny`.

## What to do

- **Before you upgrade**: npm says the warnings exist from 11.16.0. I only tested 11.21.1, where `--strict-allow-scripts` already fails the install. On that version or later, add `strict-allow-scripts=true` to the project `.npmrc`, run `npm ci`, and see which packages it lists. Approve only the ones whose `require()` fails without the script, and deny the rest. Commit `package.json`.
- **In CI:** keep strict mode on, and add a `require()` smoke test for each native dependency. Do not rely on the warning or on `npm install-scripts ls` to catch this. The first can be silenced, and the second exits 0.
- **For dependency-bot PRs:** expect native packages to fail strict mode on every version bump, because approvals are pinned. That failure is the review step working. Re-approve with `npm install-scripts approve <pkg>` once you have read the diff.

For the Python side of keeping dependency updates reviewable, see [Safely Update Python Project Dependencies](/blog/2026-08-01-safe-python-dependency-updates.html).

## References

- [GitHub Changelog: Upcoming breaking changes for npm v12 (2026-06-09)](https://github.blog/changelog/2026-06-09-upcoming-breaking-changes-for-npm-v12/), the source for "a package with a `binding.gyp` and no explicit install script still gets blocked"
- [GitHub Changelog: npm install-time security and GAT bypass2fa deprecation (2026-07-08)](https://github.blog/changelog/2026-07-08-npm-install-time-security-and-gat-bypass2fa-deprecation/)
- [npm CLI v12.0.0 release notes](https://github.com/npm/cli/releases/tag/v12.0.0)
- [npm docs (v12): `npm install-scripts`](https://docs.npmjs.com/cli/v12/commands/npm-install-scripts/) and [config: `strict-allow-scripts`](https://docs.npmjs.com/cli/v12/using-npm/config/)
- Found through GeekNews Weekly's link to "Thank you, Deno", which notes npm 12's move to not running install scripts by default
