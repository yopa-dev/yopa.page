---
title: "Your Agent Panel Defaults to 127.0.0.1. Your Compose File Doesn't."
date: 2026-10-23T10:00:00-04:00
author: Yoonsoo Park
description: "NorForge found more than 20 open Cairn control panels on the Internet, all on port 8000. Cairn's own server defaults to 127.0.0.1, but its recommended Compose file binds 0.0.0.0 and publishes 8000:8000. I reproduced both shapes on one machine with a network namespace as the outside client: which bind is reachable, why 127.0.0.1 inside a container is the wrong fix, why a host INPUT drop rule did not stop a published port, and a read-only check that fails when a panel is exposed."
categories:
  - Security
  - DevOps
tags:
  - Security
  - Docker
  - AI Agents
  - Self-Hosting
  - measured
---

On 2026-10-19 NorForge published [Inside Cairn](https://norforge.com/blog/inside_cairn), a look at agent control panels that were left open on the Internet. Cairn is an open-source engine that coordinates AI agent workers toward a goal, and its first use case is penetration testing. NorForge found more than 20 panels that it links to malicious operators, and describes them like this:

> These panels appear completely unprotected, exposing what looks like the full administrative functionality of the harness.

The article does not say how the panels ended up public. It does list their addresses, redacted, and all 25 panel entries end in `:8000`. That made me look at how Cairn starts. The server's own command line binds to loopback by default. This is from `cairn/src/cairn/cli.py` at commit [`8e7e0ea`](https://github.com/oritera/Cairn/blob/8e7e0ea67552383851dfcabfba0c4e9c8d007878/cairn/src/cairn/cli.py):

```python
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host")
@click.option("--port", default=8000, show_default=True, help="Bind port")
```

The README calls Docker Compose the recommended setup, and [`docker-compose.yaml`](https://github.com/oritera/Cairn/blob/8e7e0ea67552383851dfcabfba0c4e9c8d007878/docker-compose.yaml) at the same commit overrides that default and publishes the port:

```yaml
    ports:
      - "8000:8000"
    ...
    command: ["uv", "run", "cairn", "serve", "--host", "0.0.0.0", "--no-access-log"]
```

I can't tell whether those operators used this file, so I won't claim it caused anything. But it is an easy shape to end up with: a safe default in the code and a public port in the quick-start. So I reproduced both on one machine and measured what another machine could reach. The short version:

1. **A process bound to `127.0.0.1` was not reachable from the outside client. The same process on `0.0.0.0` was.** That part is what everyone expects.
2. **Inside a container, `127.0.0.1` is the wrong fix.** With `-p 18003:8000` and the app on loopback inside the container, nothing could use the panel, not even the host itself. That is why Compose files say `0.0.0.0`.
3. **With the Compose shape (`0.0.0.0` inside, `-p 18004:8000`), the outside client got HTTP 200.** On the host, `ss` showed `docker-proxy` listening on `0.0.0.0` and `[::]`.
4. **Changing the port line to `127.0.0.1:18005:8000` was enough.** The host still got 200, and the outside client was refused.
5. **A host firewall rule did not stop the published port.** An `INPUT` drop rule blocked the plain process (timeout), but the outside client still got 200 from the container.
6. **A read-only check catches all of it.** A short script over `ss` and `docker ps` exited 1 for every exposed case and 0 for the two loopback ones.

## Terms

| Term | Meaning here |
|---|---|
| Bind address | The local address a server listens on. `127.0.0.1` accepts only connections from the same machine. `0.0.0.0` (and `[::]` for IPv6) accepts them on every interface. |
| Publish (`-p host:container`) | Docker maps a host port to a container port. With no host address, Docker uses every host address. |
| `docker-proxy` | The Docker process that listens on the host side of a published port. It is what `ss` and `lsof` show. |
| DNAT | The NAT rule Docker adds so that traffic to the host port is rewritten to the container's address. |
| `INPUT` chain | The firewall chain for packets addressed to the host itself. Host firewalls such as ufw add their rules there. |

## Setup

Everything ran on one Linux machine. I didn't scan or contact any real panel, and I didn't run Cairn itself. The server is a 22-line Python stand-in, `panel.py`, with no authentication and the same `--host 127.0.0.1` default. `GET /projects` returns a fake list.

The "other machine" is a network namespace called `panelclient`, joined to the host by a veth pair. The host end is `10.250.0.1`, so the client reaches the host on a non-loopback interface, the way a machine on your network or the Internet would. Each case records the input, the read-only evidence (`ss`, `lsof`, `docker port`, the Docker NAT rule) and one `curl` from loopback and one from the namespace. The versions were Docker 26.1.5 (the Debian package, iptables backend), Linux 6.12, Python 3.13.5 and the `python:3.13-alpine` image. The code and raw logs are in [yopa-experiments at `6a097d7`](https://github.com/ypark9/yopa-experiments/tree/6a097d7/2026-10-23-agent-panel-exposed-by-one-port-line).

One thing about the test machine. It had a leftover `iptables-legacy` ruleset with a `FORWARD` policy of `DROP`, which a clean Docker host doesn't have. On the first run that rule dropped every forwarded packet, so the container cases timed out from the namespace. The run script now adds two `DOCKER-USER` accept rules, only between the veth and `docker0` and only for the length of the run, and removes them on exit. The first run is kept as `results/run0-stale-legacy-forward-drop.tsv`. If your containers seem unreachable when you expect them to be reachable, check `iptables-legacy -S FORWARD` before you trust the result.

## Results

| Case | Setup | `ss` shows | From loopback | From the namespace |
|---|---|---|---|---|
| b01 | process, `--host 127.0.0.1` | `127.0.0.1:18001` | 200 | refused |
| b02 | process, `--host 0.0.0.0` | `0.0.0.0:18002` | 200 | **200** |
| b03 | container, app on `127.0.0.1`, `-p 18003:8000` | `0.0.0.0:18003`, `[::]:18003` | connection reset | refused |
| b04 | container, app on `0.0.0.0`, `-p 18004:8000` | `0.0.0.0:18004`, `[::]:18004` | 200 | **200** |
| b05 | container, app on `0.0.0.0`, `-p 127.0.0.1:18005:8000` | `127.0.0.1:18005` | 200 | refused |
| b06 | b02 and b04 plus `iptables -I INPUT -p tcp --dport <port> -j DROP` | unchanged | | 18002 timed out, **18004 still 200** |

"Refused" is `curl` exit 7, "connection reset" is exit 56 and "timed out" is exit 28 after 3 seconds. The raw lines are in `results/matrix.tsv`.

## Inside a container, 127.0.0.1 locks out everyone

b03 is the result I would have guessed wrong. The container's port was published, and the host showed a listener on every address, but even `curl` on the host itself failed. The published port goes to the container's own network interface. An app bound to the container's loopback never sees that traffic.

That is the reason Compose files run the app on `0.0.0.0`. Inside the container it is the correct bind, and it doesn't decide who can reach the panel. The `ports:` line does.

## The port line decides

b04 is the Cairn Compose shape with a different port number. From the host it looks like this:

```text
$ ss -H -ltnp "sport = :18004"
LISTEN 0      4096   0.0.0.0:18004 0.0.0.0:* users:(("docker-proxy",pid=N,fd=N))
LISTEN 0      4096      [::]:18004    [::]:* users:(("docker-proxy",pid=N,fd=N))
$ docker port p04
8000/tcp -> 0.0.0.0:18004
8000/tcp -> [::]:18004
```

b05 changes only the host side of `-p`:

```text
$ ss -H -ltnp "sport = :18005"
LISTEN 0      4096   127.0.0.1:18005 0.0.0.0:* users:(("docker-proxy",pid=N,fd=N))
$ iptables -t nat -S DOCKER | grep 18005
-A DOCKER -d 127.0.0.1/32 ! -i docker0 -p tcp -m tcp --dport 18005 -j DNAT --to-destination 172.17.0.4:8000
```

The NAT rule now matches only traffic addressed to `127.0.0.1`, and the namespace client was refused. Docker's [port publishing page](https://docs.docker.com/engine/network/port-publishing/) says the same:

> Publishing container ports is insecure by default. Meaning, when you publish a container's ports it becomes available not only to the Docker host, but to the outside world as well.

> If you include the localhost IP address (`127.0.0.1`, or `::1`) with the publish flag, only the Docker host can access the published container port.

For Cairn's file, the change is one line: `- "127.0.0.1:8000:8000"`.

## A host firewall rule did not help

b06 is the case I would least want to find out about later. I added the same `INPUT` drop rule for the plain process port and the container port. The plain process went silent, and the namespace client timed out. The container answered 200 as if the rule weren't there.

Docker's [packet filtering page](https://docs.docker.com/engine/network/packet-filtering-firewalls/) explains why, in its ufw section:

> Docker routes container traffic in the nat table, which means that packets are diverted before it reaches the INPUT and OUTPUT chains that ufw uses.

I tested a raw `iptables` rule, not ufw itself. But the mechanism is the one in the quote: the traffic is rewritten to the container address and goes through `FORWARD`, not `INPUT`. If your plan is "the panel is published, but the firewall blocks port 8000", test it from another machine before you rely on it.

## A read-only check

This is the script I ran in every case, `check-listeners.sh` in the experiment folder. It only reads `ss` and `docker ps` and changes nothing:

```bash
#!/usr/bin/env bash
# Read-only. Lists TCP listeners that accept connections from beyond loopback,
# plus Docker published ports that are not bound to 127.0.0.1.
# Exit 1 if it finds one. With port arguments, only those ports are checked.
# usage: check-listeners.sh [port ...]   (no ports = report every port)
set -euo pipefail
ports=" $* "
bad=0
# ss -H -ltn prints: State Recv-Q Send-Q Local:Port Peer:Port
while read -r _ _ _ local _; do
  addr=${local%:*}; port=${local##*:}
  [ "$#" -eq 0 ] || [[ "$ports" == *" $port "* ]] || continue
  case "$addr" in
    127.*|\[::1\]) echo "ok       $local";;
    *)             echo "EXPOSED  $local"; bad=1;;
  esac
done < <(ss -H -ltn)
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  while read -r name mapping; do
    [ -n "$mapping" ] || continue
    for m in ${mapping//,/ }; do
      hp=${m%%->*}; hp=${hp##*:}
      [ "$#" -eq 0 ] || [[ "$ports" == *" $hp "* ]] || continue
      case "$m" in
        127.0.0.1:*|\[::1\]:*) echo "ok       docker $name $m";;
        *-\>*)                 echo "EXPOSED  docker $name $m"; bad=1;;
      esac
    done
  done < <(docker ps --format '{{.Names}} {{.Ports}}')
fi
exit "$bad"
```

For the Compose shape it printed:

```text
$ ./check-listeners.sh 18004
EXPOSED  0.0.0.0:18004
EXPOSED  [::]:18004
EXPOSED  docker p04 0.0.0.0:18004->8000/tcp
EXPOSED  docker p04 :::18004->8000/tcp
```

It exited 0 for b01 and b05 and 1 for b02, b03 and b04. b03 counts as exposed even though nothing answered, because the host port was open on every address. Run it with the panel's port after every `docker compose up`, or with no arguments to see everything the machine listens on.

The check reads the machine's own sockets. It doesn't tell you whether a cloud security group or a router port forward lets the traffic in. That has to be checked from outside, and only against your own host.

## What I did not measure

- **Cairn itself.** I used a stand-in with the same default bind and no authentication. I checked Cairn's `cli.py`, `docker-compose.yaml` and `server/app.py` at `8e7e0ea`. `app.py` registers five routers and a static mount, and has no authentication code, but I didn't read the routers.
- **What the exposed operators ran.** NorForge's article doesn't say, and I can't tell from port numbers.
- **Docker 28 or newer.** Docker's docs warn that "in releases older than 28.0.0, hosts within the same L2 segment ... can reach ports published to localhost" ([moby/moby#45610](https://github.com/moby/moby/issues/45610)). My Docker was 26.1.5, and I didn't test that path. b05 shows that the namespace couldn't reach the loopback publish through the host address. It doesn't show that a neighbour on the same switch can't.
- **ufw, firewalld, nftables-backend Docker, rootless Docker, Podman, an IPv6 client, a cloud security group.**
- **An SSH tunnel to a loopback-published panel** (`ssh -L 8000:127.0.0.1:8000 <host>`). It is the usual way to reach a panel published on `127.0.0.1` from a laptop, but I didn't run it here.

## What to do

- **Publish agent panels on loopback.** Use `"127.0.0.1:8000:8000"` in Compose. Keep `--host 0.0.0.0` inside the container, which is needed (b03).
- **Don't rely on a host `INPUT` rule to cover a published port** (b06). If you need host-level filtering for containers, Docker's [iptables page](https://docs.docker.com/engine/network/firewall-iptables/) describes `DOCKER-USER` as "a placeholder for user-defined rules that will be processed before rules in the DOCKER-FORWARD and DOCKER chains." I didn't test a rule there.
- **Consider a loopback default for the daemon.** The port publishing page documents `"ip": "127.0.0.1"` in `daemon.json` for the default bridge and `com.docker.network.bridge.host_binding_ipv4` for user-defined networks. I didn't test either. Note that `docker compose` normally puts services on a user-defined network, so the `"ip"` setting alone may not cover it.
- **Run the read-only check after every deploy** and fail the deploy on exit 1.
- **Upgrade Docker to 28.0.0 or later** if you rely on loopback publishing and share an L2 network with machines you don't trust.
- **Add authentication anyway.** A loopback bind keeps a panel off the network, but anything else running on that machine can still reach it.

For the Compose shape on a Synology box with no published ports at all, see [the Hermes on Synology post](/blog/2026-08-08-migrate-hermes-from-aws-to-synology.html).

## References

- NorForge, [Inside Cairn: Open Windows into massive AI-Driven Cyber Operations](https://norforge.com/blog/inside_cairn), 2026-10-19.
- oritera/Cairn at commit [`8e7e0ea`](https://github.com/oritera/Cairn/tree/8e7e0ea67552383851dfcabfba0c4e9c8d007878): `cairn/src/cairn/cli.py`, `docker-compose.yaml`, `cairn/src/cairn/server/app.py`.
- Docker docs, [Port publishing and mapping](https://docs.docker.com/engine/network/port-publishing/).
- Docker docs, [Packet filtering and firewalls](https://docs.docker.com/engine/network/packet-filtering-firewalls/).
- Docker docs, [Docker with iptables](https://docs.docker.com/engine/network/firewall-iptables/).
- Experiment code and raw output: [ypark9/yopa-experiments, `2026-10-23-agent-panel-exposed-by-one-port-line` at `6a097d7`](https://github.com/ypark9/yopa-experiments/tree/6a097d7/2026-10-23-agent-panel-exposed-by-one-port-line).
