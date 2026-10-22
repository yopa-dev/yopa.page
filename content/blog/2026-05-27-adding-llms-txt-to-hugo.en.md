---
title: "Adding llms.txt to a Hugo Blog with Output Formats"
date: 2026-05-27T03:00:00-04:00
author: Yoonsoo Park
description: "How to add an /llms.txt endpoint to a Hugo static site using a custom Output Format, so LLMs can ingest your blog without crawling 180 HTML pages — and an honest take on whether it actually works."
categories:
  - Hugo
  - SEO
tags:
  - llms-txt
  - hugo
  - llm
  - aws
---

In September 2024, [Jeremy Howard](https://jeremy.fast.ai/) (Answer.AI / fast.ai) proposed [`/llms.txt`](https://llmstxt.org/) — a curated, plain-Markdown index that sits at a site's root, alongside `robots.txt` and `sitemap.xml`. The pitch: LLM context windows are tiny, HTML is noisy, and crawlers shouldn't have to parse 180 HTML pages to understand what your site is about. So give them a hand-curated map.

Sounds reasonable. The harder question is whether it does anything yet.

## What `llms.txt` actually is

It's a Markdown file with a strict, parseable structure:

```
# Site Name                  ← H1, exactly one, required
> One-line summary           ← blockquote
Free-form prose (optional)

## Docs                      ← H2 sections
- [Title](URL): short description

## Optional                  ← reserved meaning: skip if context is tight
- [Appendix](URL)
```

Two adjacent conventions show up in the spec:

- **`llms-full.txt`** — same idea, but with all the linked content inlined into a single file. Useful for "drop the entire docs into a context window."
- **`.md` mirror URLs** — every page at `/foo/` is also reachable at `/foo.md` as clean Markdown. nbdev does this automatically; FastHTML pioneered the pattern.

## Adoption: docs sites yes, LLM providers… not really

Documentation sites have adopted it widely. Anthropic's docs, Cloudflare, Mintlify (auto-generated), Vercel, Supabase, Hugging Face, FastHTML — all publish `/llms.txt`. Mintlify, Fern, and Docusaurus plugins are doing most of the heavy lifting in spreading it.

The part nobody likes to say out loud: **none of the major LLM providers have publicly committed to fetching it.** OpenAI's GPTBot, Anthropic's ClaudeBot, Google-Extended — they all crawl HTML and follow `sitemap.xml`. None of their published docs say `llms.txt` is preferred or even read. John Mueller (Google) commented in late 2024 that there was no evidence any AI service was using it.

So today, `llms.txt` is closer to **good documentation hygiene** than a working SEO channel. The cost of adding one is near-zero, though, and if/when providers start consuming it, you're already there.

## Implementation in Hugo

Two ways to add it:

1. Drop a static `static/llms.txt` file. Done. Stale within a month.
2. Generate it from your content via Hugo's [Output Formats](https://gohugo.io/configuration/output-formats/) so it stays current with every post.

(2) is the only correct answer for a blog where posts are added regularly.

### Step 1 — register the output format

In `config.yaml`:

```yaml
outputFormats:
  LLMS:
    mediaType: "text/plain"
    baseName: "llms"
    isPlainText: true
    notAlternative: true

outputs:
  home: ["HTML", "RSS", "JSON", "LLMS"]
```

`isPlainText: true` skips Hugo's HTML-aware processing. `notAlternative: true` keeps it out of the `<link rel="alternate">` chain — `llms.txt` is not an alternate representation of the homepage.

### Step 2 — write the template

`layouts/index.llms.txt`:

```go-html-template
# {{ .Site.Title }}

> {{ .Site.Params.siteDesc }}

{{ .Site.Params.siteName }} is the personal tech blog of {{ .Site.Params.author }}.

## Pages
- [About]({{ "about.html" | absURL }}): About the author
- [Articles]({{ "articles.html" | absURL }}): Curated articles index

## Blog Posts
{{- range first 80 (where .Site.RegularPages "Section" "blog") }}
- [{{ .Title }}]({{ .Permalink }}){{ with (.Description | default (.Summary | plainify | truncate 140)) }}: {{ . }}{{ end }}
{{- end }}

## Optional
- [RSS Feed]({{ "index.xml" | absURL }})
- [Tags]({{ "tags/" | absURL }})
```

Build, and Hugo emits `public/llms.txt` automatically. Sync to S3 / CloudFront like any other static file. Verify the `Content-Type`:

```bash
hugo --gc --minify
head public/llms.txt              # starts with '# thats.nono'
curl -I https://www.yopa.page/llms.txt   # Content-Type: text/plain
```

That's it.

## What I didn't add (yet)

- **`llms-full.txt`**. Tempting, but for a blog with 180+ posts it'd be massive, and there's no evidence anyone is fetching it.
- **`.md` mirror URLs.** Two extra lines in `outputs.page` would do it, but it doubles the surface area for caching headaches and content drift. Defer.

## Honest take

I added `llms.txt` to yopa.page because the cost is one template and zero ongoing maintenance, not because I expect Claude or ChatGPT to start reading it tomorrow. If the standard catches on, my site is ready. If it doesn't, I lost 30 minutes but well? 

That asymmetry — cheap to adopt, free option on future upside — is the whole reason to do this now. Don't rewrite your content strategy around it. Don't tell your boss it'll move SEO numbers. Just ship the file and move on.

## References

- Spec: <https://llmstxt.org/>
- Repo: <https://github.com/AnswerDotAI/llms-txt>
- This blog's [`llms.txt`](https://www.yopa.page/llms.txt)
- PR that added it: [ypark9/yopa.page#19](https://github.com/ypark9/yopa.page/pull/19)
