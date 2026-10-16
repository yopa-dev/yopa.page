---
title: "Deno Is Winding Down. Can Node's --permission Replace It as a Sandbox? I Ran 13 Probes."
date: 2026-10-16T09:00:00-04:00
author: Yoonsoo Park
description: "Deno's team is joining Cloudflare, and the runtime gets about a year of fixes before development ends. Some tools use Deno as a cage for JavaScript they did not write. I ran the same 13 probes under Deno and under Node 22, 24 and 26 with --permission. Deno blocked every probe it could run. Of those, Node let 7 through on 22 and 24, and 5 on 26."
categories:
  - AI Agents
  - Security
tags:
  - Security
  - Node.js
  - JavaScript
  - AI Agents
  - isolation
---

On 2026-10-09 the Deno team [announced it is joining Cloudflare](https://deno.com/blog/cloudflare). The Deno runtime gets about 12 months of monthly bugfix and security releases, and then the team stops developing it. Deno Deploy shuts down sooner, in about six months.

Most coverage asks what this means for people who build apps on Deno. I care about a smaller group: people who use Deno as a **cage**. Deno starts with no access to files, network, or environment variables unless you grant them. That makes it an easy place to run JavaScript you did not write. yt-dlp, the video downloader, runs YouTube's player code this way. Agent builders do the same with code a model just wrote.

Node.js has its own switch, `--permission`. yt-dlp already ships a Node path that uses it. So the question is practical: if you swap `deno run` for `node --permission`, which walls do you keep?

In short, I ran 13 probes, each one a small attempt to reach outside the cage, under Deno 2.9.7 and Node 22, 24 and 26, all on one Linux box:

1. **Files and child processes: same.** With no grants, Node blocked direct file reads, file writes, and spawning a process, on all three versions, just like Deno.
2. **Environment variables: Node lets them through.** Every Node version let the code read a secret from its environment. Deno blocked it.
3. **Network: depends on the version.** Node 22 and 24 have no network permission at all, so the code could fetch freely. Node 26 blocked it.
4. **Side doors: open in Node.** On every Node version, the code read and wrote a SQLite file outside its allowed paths, read a file handle it inherited, and switched on the debugger of another Node process on the same machine. Deno blocked all of these that it supports.
5. **Two walls neither runtime has.** A symlink inside an allowed folder led outside it in both. And a heap limit stopped neither from holding 512 MB.

Count: Deno could run 12 of the 13 probes and blocked all 12. Of those 12, Node let 7 through on 22 and 24, and 5 on 26. Node also let the 13th through, which Deno could not run at all.

## What "permission" means here

A **permission model** is a switch inside the runtime that refuses certain calls unless you **grant** them on the command line. Deno has had one from the start: `--allow-read`, `--allow-net`, `--allow-env`, and so on. With none of them, the code can compute but cannot touch anything. Node added `--permission` later. Once it is on, file access, child processes, and worker threads are refused unless you add `--allow-fs-read`, `--allow-child-process`, and similar flags.

The two projects describe their models very differently. The [Node documentation](https://nodejs.org/api/permissions.html) says:

> The permission model implements a "seat belt" approach, which prevents trusted code from unintentionally changing files or using resources that access has not explicitly been granted to. It does not provide security guarantees in the presence of malicious code.

A seat belt is for code you trust that might make a mistake. A cage is for code you do not trust. The [Deno docs](https://docs.deno.com/runtime/fundamentals/security/) are not naive either. For untrusted code they ask for more than one layer, including OS sandboxing and a VM. But Deno's default is "nothing until granted", and that is what people relied on.

## How yt-dlp calls each runtime

yt-dlp is a good test case because it already supports both. Here is the option list it gives Deno:

```python
_DENO_BASE_OPTIONS = [
    '--ext=js', '--no-code-cache', '--no-prompt', '--no-remote',
    '--no-lock', '--node-modules-dir=none', '--no-config',
]
```

There is no `--allow-*` flag in the list. So Deno runs the script with no file, network, environment, or process access. `--no-prompt` means "refuse instead of asking", and `--no-remote` means the script cannot import code from the internet.

And here is the Node path:

```python
# Node permission flag changed from experimental to stable in v23.5.0
if self.runtime_info.version_tuple < (23, 5, 0):
    args.append('--experimental-permission')
    args.append('--no-warnings=ExperimentalWarning')
else:
    args.append('--permission')

cmd = [self.runtime_info.path, *args, *self._ARGS]
```

It turns the permission model on and grants nothing. That looks equivalent. One detail is not. The Deno path builds its environment from `os.environ.copy()`, and the Node path calls `Popen` without an `env=` argument. **Both children receive the full environment of the user who ran yt-dlp**, API keys included. Under Deno that does not matter, because the script cannot read environment variables without `--allow-env`. Under Node it does, as the results below show.

yt-dlp's own [README](https://github.com/yt-dlp/yt-dlp) is honest about this. Only Deno is enabled by default, and it says `node` and `bun` "are still considered insecure".

## The setup

- **Runtimes:** Deno 2.9.7, Node 22.23.3, Node 24.22.0, Node 26.12.0. Official Linux x64 builds, with checksums checked.
- **Profiles:** `P0` grants nothing, the way yt-dlp runs both runtimes. `P1` grants read and write on one work folder, the way a tool that needs scratch space would run.
- **Input:** the script goes in on standard input, as yt-dlp does it. The child's environment holds a fake secret (`PROBE_FAKE_SECRET`). The child also gets a file handle that is already open on a file outside the work folder.
- **Controls:** every probe also ran with full access (`deno run -A`, plain `node`). A probe that cannot succeed even then is marked `n/a`, not "blocked". Otherwise a broken probe would look like a working wall.
- **Network:** a small HTTP server on 127.0.0.1. Nothing left the machine. No cloud account, no paid API.
- **Repeats:** three full runs. All three matrices were identical.

Each probe either returns a value or throws an error. This is the environment probe:

```js
await probe('env_secret', () => {
  const v = proc.env.PROBE_FAKE_SECRET;
  if (v === undefined) throw new Error('PROBE_FAKE_SECRET is undefined');
  return v;
});
```

If the runtime lets the code see the variable, the probe returns its value and counts as "allowed". If the runtime refuses, the error is recorded. Deno's error was `NotCapable: Requires env access to "PROBE_FAKE_SECRET"`. Node returned the value.

For two of the side doors, I did not trust the probe's own report. For SQLite, the harness counted rows in the database afterwards. For the debugger probes, it checked whether the other process printed `Debugger listening`. The [code and raw output](https://github.com/ypark9/yopa-experiments/tree/experiment/deno-sandbox-to-node-permission-20261016/2026-10-16-deno-sandbox-to-node-permission) are public.

## Results with no grants (P0)

| Probe | Deno 2.9.7 | Node 22 | Node 24 | Node 26 |
| --- | --- | --- | --- | --- |
| Read a file outside the folder | blocked | blocked | blocked | blocked |
| Write a file outside the folder | blocked | blocked | blocked | blocked |
| Write inside the work folder | blocked | blocked | blocked | blocked |
| Read a symlink in the folder that points outside | blocked | blocked | blocked | blocked |
| Run `/bin/echo` | blocked | blocked | blocked | blocked |
| Read the secret environment variable | blocked | **allowed** | **allowed** | **allowed** |
| `fetch` the local server | blocked | **allowed** | **allowed** | blocked |
| Raw TCP socket to the local server | blocked | **allowed** | **allowed** | blocked |
| Read a SQLite file outside, with `node:sqlite` | blocked | **allowed** | **allowed** | **allowed** |
| Insert a row into that SQLite file | blocked | **allowed** | **allowed** | **allowed** |
| Read the inherited file handle | n/a | **allowed** | **allowed** | **allowed** |
| `process._debugProcess(pid)` on another Node process | blocked | **allowed** | **allowed** | **allowed** |
| `process.kill(pid, 'SIGUSR1')` on another Node process | blocked | **allowed** | **allowed** | **allowed** |

The one `n/a` is the inherited file handle under Deno. Deno's Node-compatible `fs` could not read it even with full access, so I cannot say Deno blocks it. That is why the Deno count is 12 of 12, not 13 of 13.

With a work-folder grant (P1), the only cells that changed were the two you would expect. Writing inside the folder and reading the symlink became "allowed" in all four runtimes. Every other cell stayed the same.

### Environment variables

No Node version has an environment permission, so `--permission` does nothing for `process.env`. In the yt-dlp case, the downloaded player script would be able to read whatever the user had exported, like cloud credentials or model API keys. I did not run yt-dlp itself; this follows from its launch code above and the probe result. An agent tool that starts Node with its parent's environment has the same problem.

### Network

`node --help` on 22.23.3 and 24.22.0 lists no `--allow-net` flag. On those versions, turning on `--permission` does not touch the network. Both `fetch` and a raw socket reached my local server. Node 26.12.0 adds `--allow-net`, and both were refused with `ERR_ACCESS_DENIED`. Put the two rows together: on Node 22 and 24, code can read a secret from the environment and send it anywhere.

### The side doors

The Node docs list these as known limits, and every one of them reproduced:

- **SQLite.** The docs say the model "does not guarantee that users will not be able to access the file system through other means, such as through the `node:sqlite` module." With zero file grants, the probe read a row from a database outside its folder and inserted a new one. The harness counted two rows afterwards.
- **Inherited file handles.** A file that was already open when the process started is readable, permission model or not. My harness passed one on purpose. A launcher leaks one by accident if it hands open handles to the child.
- **Another process's debugger.** The docs say `process._debugProcess(pid)` "is not gated by the kInspector scope or any other Permission Model scope". A plain `SIGUSR1` signal does the same thing. In both cases, the other Node process, which had no restrictions at all, opened its V8 inspector. The **inspector** is Node's debugging port, and a debugger connected to it can run code in that process with that process's full rights. I checked only that the port opened; I did not connect to it. The docs' advice is to run the sandboxed process and other Node processes as different OS users.

### What neither runtime gives you

- **Symlinks.** With a grant on the work folder, a symlink inside it that pointed to a file outside could be read in Deno and in all three Node versions. A folder grant is only as tight as the links inside it. Node's docs warn about this. I did not find the same warning on Deno's security page, but the result was the same.
- **Memory.** A 128 MB heap limit (`--max-old-space-size=128`) killed ordinary JavaScript arrays in all four runtimes, at a peak of 201 to 258 MB of resident memory across the three runs. The same limit did nothing to `Uint8Array` buffers, which live outside the JavaScript heap. All four held 512 MB, at a peak of 549 to 557 MB. If you need a memory cap, it has to come from the operating system. I did not test that part.

## What I would do

This adds a row to the decision table in [where to run agent-generated code](/blog/2026-07-02-where-to-run-agent-generated-code.html), the cheapest option that post skipped: a permission flag inside the runtime, on the same host.

| Situation | What to reach for |
| --- | --- |
| Third-party or model-written JS that only computes (no files, network, or secrets), and you are moving off Deno | Node 26 with `--permission`, an empty environment, no inherited handles, and a separate OS user. Self-test the exact launch line. |
| The same, but you are stuck on Node 22 or 24 | `--permission` is not a network wall there. You need a network block outside Node (not tested here), or stay on Deno while it still gets security fixes. |
| The code needs network, files, or secrets to do its job | A real boundary: a MicroVM or container, as in the earlier post. A runtime flag is the wrong layer. |

The first row has several parts, and I measured only some of them. The empty environment, the network block on 26, and the self-test below are measured. The separate OS user comes from Node's own docs. I did not test it here.

Before you trust a launch line, test it. This script is read-only. It checks that the Node you have actually has a network permission. Then it runs a tiny program through the exact command and confirms two things: the network is refused by the permission model, not just by a closed port, and the environment is empty.

```sh
#!/bin/sh
# Read-only self-test of a Node --permission launch line. Writes nothing, changes nothing.
set -eu
NODE=${NODE:-node}
command -v "$NODE" >/dev/null 2>&1 || { echo "FAIL: $NODE not found" >&2; exit 1; }

# 1. Does this Node build have a network permission at all? (Node 22 and 24 do not.)
if ! "$NODE" --help | grep -q -- '--allow-net'; then
  echo "FAIL: $("$NODE" --version) has no --allow-net, so --permission does not block network" >&2
  exit 1
fi

# 2. Run the exact launch line once with a tiny script: it must be denied the network
#    (not just refused by a closed port) and must see an empty environment.
SELFTEST='fetch("http://127.0.0.1:65535").then(
  () => process.exit(2),
  (e) => process.exit(e.cause && e.cause.code === "ERR_ACCESS_DENIED"
    ? (Object.keys(process.env).length <= 1 ? 0 : 3) : 4))'
status=0
printf '%s' "$SELFTEST" | env -i PATH=/usr/bin:/bin "$NODE" --permission - || status=$?
case $status in
  0) echo "OK: network denied, environment empty (PATH only)" ;;
  3) echo "FAIL: network denied but environment variables are visible" >&2; exit 1 ;;
  *) echo "FAIL: network was not denied by the permission model (exit $status)" >&2; exit 1 ;;
esac
```

On my box it failed on Node 22 and 24 at step 1, and passed on Node 26. I also checked that it can fail on 26. With `env -i` removed, it reported the visible environment. With `--permission` removed, it reported that the network was not denied. One catch about the port: I first used port 9, and `fetch` refused it for a different reason, because port 9 is on fetch's list of blocked ports. That is why the script checks the error code instead of treating any failure as a pass.

The script does not cover SQLite or the debugger signal. Those stay open on every Node version I tested, and that is the reason for the separate OS user.

## What I did not test

These results come from one Linux x86_64 machine and the exact versions above. I did not test Bun, macOS, or Windows. I did not test Deno's per-worker permissions, OS isolation (separate users, cgroups, seccomp), or a real yt-dlp download. Node 26 was not a long-term-support line when I tested; 26.12.0 shipped on 2026-10-14 as a Current release. So "use 26" also means following a release line that changes faster.

Deno still gets security fixes for about a year. That is enough time to move carefully. Just do not assume that `node --permission` keeps every wall `deno run` gave you. Of the 12 walls Deno held in my test, Node 22 and 24 kept 5, and Node 26 kept 7.
