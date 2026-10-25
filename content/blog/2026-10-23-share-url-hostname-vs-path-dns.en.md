---
title: "If the share secret is in the hostname, DNS publishes it"
date: 2026-10-23T10:00:00-04:00
author: Yoonsoo Park
description: "Claroc found 6,800+ Meta Muse share addresses in passive DNS because conversation titles lived in the hostname. I ran a local DNS logger against two URL schemes. Title-in-hostname queries logged the full title; title-in-path queries logged only the bare host. No Muse hosts and no commercial passive DNS were used."
categories:
  - Security
  - Architecture
tags:
  - Privacy
  - DNS
  - AI Agents
  - measured
---

In October 2026, security firm [Claroc](https://blog.claroc.io/ghostshares-muse-passive-dns/) reported that shared pages from Meta's Muse AI assistant were easy to find without being sent the link. Muse built each share's address from the conversation **title** plus a random id, and put that string in the **hostname** under `cf.metaaiusercontent.com`. When someone opened the link, their resolver looked that hostname up. Services that keep **passive DNS** — historical logs of DNS lookups — made those hostnames searchable. Claroc reported more than 6,800 share hostnames from one query. [Ars Technica](https://arstechnica.com/security/2026/10/meta-muse-exposes-users-personal-and-business-secrets-when-they-share-conversations/) and [The Verge](https://www.theverge.com/tech/1014627/meta-muse-ai-sharing-ai-chats) confirmed Meta paused sharing while it reviewed the report. On 2026-10-22 Meta said sharing was back and old artifact URLs were replaced ([The Verge](https://www.theverge.com/tech/1017066/meta-muse-sharing-back-on-artifiacts)).

Claroc sells a product that flags AI share links. Treat that as a stake. For Meta's words I relied on Ars and The Verge. Meta's later statement frames the bug as **artifact** URLs (documents and images), not chat sharing — that may not match Claroc's framing; both are recorded below.

I am not trying to re-find Muse pages. The useful question for anyone building a "share this AI conversation" feature is narrower:

**If the unguessable token (or the title) sits in the DNS hostname, does the first legitimate open publish the whole address into a query log? Does putting the same token in the path avoid that?**

I ran both schemes against a local DNS logger. Short answer: **yes, and yes.** The hostname scheme logged `q3-budget-review-4d7a19e2.share.test`. The path scheme logged only `share.test`.

Code and logs: [yopa-experiments `experiment/muse-share-hostname-dns-20261023`](https://github.com/ypark9/yopa-experiments/tree/experiment/muse-share-hostname-dns-20261023/muse-share-hostname-dns) (commit `199570f`).

## Terms

| Term | Meaning here |
|---|---|
| Hostname | The name looked up in DNS (`q3-budget-review-4d7a19e2.share.test`) |
| Path | The part after the host (`/s/q3-budget-review/4d7a19e2`) |
| Passive DNS | Databases that store observed DNS lookups over time; many are searchable |
| Unlisted link | A URL that is not meant to appear in search results; **not** the same as "absent from DNS history" |

`robots.txt` can ask crawlers to stay away. It does not stop a recursive resolver from logging a lookup. That is the channel Claroc used.

## The two schemes

Illustrative title and id (not a real Muse share):

- **Title in the hostname:** `http://q3-budget-review-4d7a19e2.share.test:8766/`
- **Title in the path:** `http://share.test:8766/s/q3-budget-review/4d7a19e2`

A tiny UDP DNS server on `127.0.0.1:5355` answers `A 127.0.0.1` for those names and appends every query to a log. A tiny HTTP server on `:8766` returns the host and path. The demo sends a DNS query for the host of each URL, then fetches the page with `curl --resolve` so traffic stays on loopback.

## Results

DNS log from the run:

```text
1792762615.723	q3-budget-review-4d7a19e2.share.test	qtype=1
1792762615.731	share.test	qtype=1
```

| Where the title and id go | Does the title show up in DNS logs? | What the DNS log recorded | HTTP body |
|---|---|---|---|
| In the hostname | **Yes.** Anyone who can search DNS history can read it | the full hostname, `q3-budget-review-4d7a19e2.share.test` | `ok host=q3-budget-review-4d7a19e2.share.test path=/` |
| In the path | **No** | only `share.test` | `ok host=share.test path=/s/q3-budget-review/4d7a19e2` |

Takeaway: one open of a hostname-style link is enough to put the title in DNS logs; a path-style link keeps it out.

The random id in the hostname version does not help once the name is queried. DNS logs the whole label. The secret only works while it stays out of protocols that record names.

## What Meta said, and what Claroc said

- Claroc: share hostnames under `cf.metaaiusercontent.com` included conversation titles; 6,800+ after filtering; some opened pages held sensitive content; reported via bug bounty on 2026-10-08.
- Meta (via Ars / The Verge, ~2026-10-20): paused the share functionality while reviewing how links can be discovered.
- Meta (via The Verge, 2026-10-22): issue fixed, sharing back on; problem described as artifact URLs; old links ask for a new URL from the sharer.

I did not independently measure Meta's new URL shape after the fix. If you design share links, assume **anything in the hostname is public to anyone who can search DNS history after one open**, until you have checked otherwise.

## Design rule

Put capability secrets in the **path** (or in a fragment / POST body), not in a DNS label. Prefer a single stable content host (`share.example.com`) over per-share subdomains when the subdomain would carry the title or the token. Titles are for humans; they are a poor secret and a great index key.

## What I did not do

- Query commercial passive DNS
- Open any real Muse share URL
- Contact Meta's content domain
- Claim how many of Claroc's 6,800 shares were sensitive (Claroc opened a sample; severity calls are theirs)

## Cost

Local only for the experiment (loopback DNS + HTTP). A draft PR for this post on yopa.page will still run CI `plan` jobs that assume a read-only AWS OIDC role for OpenTofu state refresh — that is separate from this measurement and is not "no AWS calls."
