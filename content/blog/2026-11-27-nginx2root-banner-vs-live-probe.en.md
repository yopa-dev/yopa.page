---
title: "Is Your nginx Exposed to NGINX2Root? The Banner, the Config Grep, and a Live Probe Disagree"
date: 2026-11-27T09:00:00-05:00
author: Yoonsoo Park
description: "On November 18, nginx fixed two HTTP/2 bugs (CVE-2026-123007 and CVE-2026-123633) in 1.30.7 and 1.31.9, and Rapid7 showed remote code execution against 1.31.8. I ran four real nginx builds on loopback, with no exploit traffic, to see which quick check tells you whether you are exposed. A Debian package that prints nginx/1.26.3 carries the fix. A grep for `listen ... http2` misses the modern `http2 on;` syntax. A grep for any `http2` line is fooled by an override. A live HTTP/2 probe matched reality in all eight config shapes I tried, and it must be repeated per server name."
categories:
  - Security
  - DevOps
tags:
  - Security
  - nginx
  - Web Servers
  - Self-Hosting
  - measured
---

On November 18, 2026, nginx published fixes for a batch of vulnerabilities. Two of them live in the HTTP/2 code: CVE-2026-123007 (memory corruption in HTTP/2 flow control) and CVE-2026-123633 (use-after-free in HTTP/2). The security community calls the pair "NGINX2Root". Red Hat's bulletin uses that name, and [Rapid7's write-up](https://www.rapid7.com/blog/post/ve-cve-2026-123007-critical-nginx-http-2-integer-underflow-leads-to-rce-fixed/) includes a video of unauthenticated remote code execution against nginx 1.31.8 with `http2 on` and TLS enabled. Per the [nginx.org advisories page](https://nginx.org/en/security_advisories.html), both are fixed in 1.30.7 (stable) and 1.31.9 (mainline).

The vendor pages tell you what is broken. They don't tell you how to find out, on your own servers, whether you are exposed. There are three obvious ways to check, and I wanted to know how often each one is wrong:

1. **Read the banner.** Compare the `Server: nginx/x.y.z` header or `nginx -v` with the fixed versions.
2. **Grep the config.** Look for `http2`.
3. **Probe it.** Ask the server which protocol it actually negotiates.

I ran all three against real nginx builds on one machine. The short version:

1. **The banner can say "vulnerable" for a package that is patched.** Debian's `nginx/1.26.3-3+deb13u11` prints `nginx/1.26.3`, below every fixed version upstream lists. Its packaging changelog says it backports the CVE-2026-123007 and CVE-2026-123633 fixes.
2. **`grep 'listen.*http2'` misses the modern syntax.** In 2 of my 8 config shapes (`http2 on;` inside the server, and `http2 on;` once at the `http` level) it reported "no HTTP/2" while clients negotiated HTTP/2.
3. **`grep http2` is fooled by an override.** With `http2 on;` at the `http` level and `http2 off;` in the server, it reported "HTTP/2 on" while clients got HTTP/1.1.
4. **A live probe matched reality in all 8 shapes.** But HTTP/2 follows the server block that the TLS server name selects, so you have to probe every name you serve.

I did not run any exploit, crash trigger, or malformed HTTP/2 frame. Nothing here proves a build is or isn't exploitable.

## Terms

| Term | Meaning here |
|---|---|
| HTTP/2 | The newer web protocol browsers use when the server offers it. nginx turns it on per server block, or per `listen` line in older configs. |
| ALPN | The part of the TLS handshake where client and server agree on a protocol. `curl --http2` offers `h2` through ALPN, so the answer shows what the server really chose. |
| SNI | The server name a client sends in the TLS handshake. nginx uses it to pick the server block, and with it the `http2` setting. |
| Banner | The `Server: nginx/x.y.z` response header. `server_tokens off;` hides the version number. |
| Backport | A distro fix applied to an older version without changing the version number. |

## What the vendors say

Only the parts I rely on, each from the page that says it:

| Source | What it says |
|---|---|
| [nginx.org advisories](https://nginx.org/en/security_advisories.html) | CVE-2026-123007: vulnerable 1.9.5 through 1.31.8, fixed in 1.30.7+ and 1.31.9+. CVE-2026-123633: vulnerable 1.19.7 through 1.31.8, same fixed versions. A separate CVE-2026-132779 (excessive CPU with `ssl_early_data`) is fixed in 1.30.8+ and 1.31.10+. |
| [Rapid7](https://www.rapid7.com/blog/post/ve-cve-2026-123007-critical-nginx-http-2-integer-underflow-leads-to-rce-fixed/) | CVSS v4 score 9.2. Their exploit needs about 128 GB of HTTP/2 data. Proxied HTTP/2 connections will likely not retransmit the attacker's frames in a way that works. |
| [Red Hat RHSB-2026-019](https://access.redhat.com/security/vulnerabilities/RHSB-2026-019) | Mitigation for both HTTP/2 bugs: remove the `http2` parameter from `listen`, or set `http2 off;` (nginx 1.25 and later). Their CVSS 3.1 score for CVE-2026-123007 is 8.1. |
| [AWS bulletin 2026-192-AWS](https://aws.amazon.com/security/security-bulletins/2026-192-aws/) | CloudFront and Application Load Balancer are updated. Amazon Linux has patched packages. AWS WAF rules cannot effectively detect or block these issues. |

The two scores come from different scoring versions (v4 and 3.1), so they aren't directly comparable.

Rapid7's 128 GB figure is worth a little arithmetic, because it shows who can realistically attempt this. The default connection lifetime in their write-up is one hour. This is my arithmetic from their number, not something I measured:

| Attacker's link speed | Time to send 128 GB (1,024 gigabits) | Fits in one hour? |
|---|---|---|
| 10 Gbit/s | about 102 seconds | Yes |
| 1 Gbit/s | about 1,024 seconds (17 minutes) | Yes |
| 300 Mbit/s | about 3,413 seconds (57 minutes) | Barely |
| 100 Mbit/s | about 10,240 seconds (2.8 hours) | No |

Takeaway: an attacker on an ordinary server or cloud link is not slowed down by the traffic volume. Don't treat the size as protection.

## Setup

Everything ran on one Linux machine, on `127.0.0.1`, with a throwaway self-signed certificate. I extracted the nginx binaries from four `.deb` packages with `dpkg-deb -x` (no install, no root):

- Debian trixie-security `1.26.3-3+deb13u11`
- nginx.org `1.30.6`, `1.30.7`, and `1.30.8`

The client is curl 8.14.1. Cost: local CPU only. No cloud account, no paid service, nothing sent to a real host.

## Result 1: the banner and the changelog disagree on Debian

For each package I started a TLS server with `http2 on;`, read the `Server` header, checked what curl negotiated, and searched the package's `changelog.Debian.gz` for the CVE.

| Package | `Server` header | HTTP/2 negotiated? | Banner compared with nginx.org's fixed versions | Packaging changelog lists the CVE-2026-123007 patch? |
|---|---|---|---|---|
| Debian 1.26.3-3+deb13u11 | `nginx/1.26.3` | Yes | Looks vulnerable | **Yes**, in 1.26.3-3+deb13u11 |
| nginx.org 1.30.6 | `nginx/1.30.6` | Yes | Vulnerable | Not mentioned |
| nginx.org 1.30.7 | `nginx/1.30.7` | Yes | Fixed | Not mentioned |
| nginx.org 1.30.8 | `nginx/1.30.8` | Yes | Fixed | Not mentioned |

Takeaway: a scanner that only reads the banner will flag the patched Debian package, and it will also be blind to hosts that hide the version. The Debian entry for 1.26.3-3+deb13u11 says:

> Backport security fixes from upstream 1.30.7:

and then lists `d/p/CVE-2026-123007.patch` ("include queued DATA in HTTP/2 flow control checks") and `d/p/CVE-2026-123633.patch` ("keep HTTP/2 connections with active streams out of the reusable connection queue"), among others.

Two limits. The "fixed" and "vulnerable" labels in this table come from nginx.org's version ranges and Debian's changelog text. I did not test any of these binaries for the bug. And the nginx.org package changelogs only say `1.30.7-1` and similar, so "not mentioned" there means nothing about whether the fix is in.

## Result 2: eight config shapes, three kinds of answer

For each shape I started nginx 1.30.7 with that config, dumped the effective config with `nginx -T`, ran two greps over it (ignoring comment lines), and then asked the running server what it negotiates. TLS listeners use `curl --http2`. Plain-HTTP listeners use `curl --http2-prior-knowledge`.

| Config shape | Grep: any line with `http2` | Grep: only `listen ... http2` | What the client negotiated |
|---|---|---|---|
| `http2 on;` inside the server block | on | off | **HTTP/2** |
| Old style: `listen ... ssl http2;` | on | on | **HTTP/2** |
| TLS listener, no `http2` anywhere | off | off | HTTP/1.1 |
| `http2 on;` once at the `http` level, plain `listen ... ssl;` in the server | on | off | **HTTP/2** |
| `http2 on;` at the `http` level, `http2 off;` in the server | on | off | HTTP/1.1 |
| `# http2 on;` only as a comment | off | off | HTTP/1.1 |
| Plain HTTP, `listen ... http2;` | on | on | **HTTP/2** (prior knowledge) |
| Plain HTTP, no `http2` | off | off | Not HTTP/2 (the request failed) |

Takeaway: the `listen ... http2` rule is right in 6 of 8 shapes and misses the two that use the newer `http2 on;` directive. The any-line rule is right in 7 of 8 and gets the override case wrong, so it can tell you to worry about a server that is fine. Neither is safe to put in a compliance script. The live answer matched what the config actually does in all 8.

The first miss is the dangerous one. A rule written when `listen ... http2` was the only syntax keeps passing after a team moves to `http2 on;`, and it reports "no HTTP/2" for servers that do speak it.

## Result 3: one port, two servers, two answers

I put two server blocks on one TLS port: `a.test` with `http2 on;` and `b.test` as the default server with `http2 off;`.

| Server name sent in the TLS handshake | Negotiated |
|---|---|
| `a.test` | HTTP/2 |
| `b.test` | HTTP/1.1 |
| No name (connecting by IP address) | HTTP/1.1, the default server's setting |

Takeaway: probing a bare IP address can tell you "HTTP/1.1" for a machine that serves HTTP/2 to real visitors. Probe every name that points at the box.

## The probe I used

`check_h2.py` sends one ordinary `HEAD` request per target with curl and prints the negotiated version and the `Server` header. It has no exploit logic. Run it only against servers you operate:

```bash
$ python3 check_h2.py 127.0.0.1:18999 127.0.0.1:1
127.0.0.1:18999   negotiated=2  server=nginx/1.30.7  -> HTTP/2 is negotiated: confirm the package version or the vendor's backport notice, or set `http2 off;` until patched
127.0.0.1:1       negotiated=0  server=(no Server header)  -> no TLS answer (check host, port, and SNI name)
```

It answers one question: "does this name speak HTTP/2?" It does not tell you whether the build is patched. For that you need the package changelog or the vendor bulletin, as in Result 1.

## What I did not measure

- **Whether any build is exploitable.** No trigger traffic was sent. Version labels are copied from the advisory and the Debian changelog.
- **The cost of `http2 off;`.** It forces browsers to open more parallel connections, but loopback has no round-trip time, so a local test would show nothing useful. I did not run one.
- **Proxied and CDN setups.** AWS says CloudFront and ALB are updated and that requests through them are protected. Rapid7 says proxied HTTP/2 will likely not carry their frames through. I didn't test either path.
- **Other nginx builds.** Only these four packages, on amd64, with curl 8.14.1. Other distro backports, containers, and nginx Plus were not run.
- **The other CVEs in the batch.** HTTP/3, the resolver, the mail proxy, and `alias` bugs are in the advisory list. I looked only at the two HTTP/2 ones.
- **`ssl_early_data`.** CVE-2026-132779 is fixed only in 1.30.8+ and 1.31.10+ according to nginx.org. I didn't test it, and the Debian changelog entry quoted above does not list it.

## What to do

- **List every nginx you run**, including containers, base images, and ingress controllers. Ask each one for its package version, not just its banner.
- **For distro packages, read the changelog.** `zcat /usr/share/doc/nginx/changelog.Debian.gz | head` on Debian shows whether the HTTP/2 fixes were backported. On Amazon Linux, AWS says patched packages are available through `yum update nginx`.
- **Probe each server name with the live check**, not a grep. Try every name, not the bare IP.
- **If HTTP/2 is negotiated and you can't confirm the fix:** upgrade to 1.30.7 or later (1.31.9 on mainline), or set `http2 off;` and reload until you can. If you use `ssl_early_data`, prefer 1.30.8 or later.
- **Close the direct path.** AWS notes that servers reachable directly, for example by a public IP, stay exposed even when CloudFront or an ALB in front is updated. Restrict the origin to the CDN or load balancer.
- **Don't count on the web application firewall.** AWS says its WAF rules can't effectively detect or block these issues, because they work at the HTTP/2 protocol layer.

## References

- nginx.org, [Security advisories](https://nginx.org/en/security_advisories.html) (checked 2026-11-27).
- Rapid7, [CVE-2026-123007: critical NGINX HTTP/2 integer underflow leads to RCE](https://www.rapid7.com/blog/post/ve-cve-2026-123007-critical-nginx-http-2-integer-underflow-leads-to-rce-fixed/).
- Red Hat, [RHSB-2026-019 NGINX2Root](https://access.redhat.com/security/vulnerabilities/RHSB-2026-019).
- AWS, [Security bulletin 2026-192-AWS: Issue with nginx HTTP/2 implementation](https://aws.amazon.com/security/security-bulletins/2026-192-aws/).
- Debian package `nginx 1.26.3-3+deb13u11` and nginx.org packages 1.30.6, 1.30.7, 1.30.8 (changelog files inside the `.deb`s).
- Experiment code and raw output: [ypark9/yopa-experiments, `nginx2root-exposure` at `55ec79f`](https://github.com/ypark9/yopa-experiments/tree/55ec79f/nginx2root-exposure).
