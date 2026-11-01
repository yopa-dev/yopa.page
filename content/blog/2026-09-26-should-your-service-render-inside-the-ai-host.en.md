---
title: "Should Your Service Render Inside the AI Host? I Ran One MCP App on Two Hosts"
date: 2026-09-26T09:00:00-04:00
author: Yoonsoo Park
description: "MCP Apps lets your server hand an AI host an HTML widget to show inside the chat. I ran the same widget on MCP Inspector and on Claude Desktop. The plumbing works, but the two hosts run it under different rules: one blocks data images, the other allows eval; one waits for a human to refresh the tool list, the other refreshes in a millisecond and caches your HTML. Here is the mental model, what I measured, and what I would decide."
categories:
  - AI Agents
  - Architecture
  - AWS
tags:
  - AI Agents
  - MCP
  - Amazon Bedrock AgentCore
  - Security
  - ui-extension
aliases:
  - /blog/2026-09-21-should-your-service-render-inside-the-ai-host.html
---

For two years the way I thought about MCP (Model Context Protocol) was "here are my functions, model, pick one". The MCP Apps extension adds something new. Your server can now hand the AI host a small HTML page, a **widget**, and the host shows it inside the conversation. The user sees a card or a table instead of a paragraph.

That is a bigger decision than adding a tool, because your interface now lives on someone else's screen. AWS published a reference implementation of this on Amazon Bedrock AgentCore on 2026-09-11, a sample called Unicorn Rentals. I read it, and then I ran my own small MCP App on two hosts: MCP Inspector, the local test tool, and Claude Desktop.

In short:

1. The whole flow works locally, and you can test more of it than I expected before you touch a real host.
2. **The same widget runs under different rules on each host.** Inspector blocked inline `data:` images. Claude allowed them, and also allowed `eval`.
3. Declaring one image CDN in your widget's settings also lets that CDN serve **scripts** into your widget. Same on both hosts.
4. When your tool list changes, Claude re-reads it within a millisecond. Inspector waits for a human to click Refresh.
5. Claude reads your widget HTML once per connection and reuses it. Inspector reads it on every call.

## The mental model: it is MVC

MVC (model, view, controller) is an old way to split an app into three jobs, and it maps onto MCP Apps almost exactly:

| MVC part | In an MCP App | In the AWS reference |
| --- | --- | --- |
| **View** | the widget, HTML running in a sandboxed iframe inside the host's page | the unicorn cards |
| **Controller** | the MCP server: receives the tool call, checks the arguments, calls the business layer, returns data plus a pointer to the widget | MCP server on AgentCore Runtime |
| **Model** | your business logic and data | a Lambda function and DynamoDB |

Once you hold this picture, most of the rules below stop being rules you have to remember:

- **No logic in the widget.** It is the view. It runs inside an iframe (a page embedded in another page) on someone else's site, under their sandbox.
- **State lives behind the controller.** Bookings, sessions, and their expiry belong in the database, not in the widget.
- **The controller stays thin.** In the reference, the business Lambda knows nothing about MCP, and it could be your existing service on ECS or EKS. So if the widget experiment fails, you delete the view and the controller. The model never moved.
- **Validate twice.** The controller checks the arguments against a strict schema. The model checks again, because the layer that owns the data has to make its own decision. The reference says the same thing, and it is the same idea as [keeping the final "no" in the layer that owns the resource](/blog/2026-09-26-where-should-agent-refusals-live.html).

## How it works, in four steps

1. The host asks your server for its tools and its resources.
2. A tool's settings include a field, `_meta.ui.resourceUri`, that points at a widget, for example `ui://fleet-experiment/card-default`. When the model calls that tool, the result also carries `structuredContent`, the data the widget will show.
3. The host reads that `ui://` resource and gets back one self-contained HTML page.
4. The host puts the HTML in a sandboxed iframe and passes the data in through messages.

A **sandbox** here means the browser runs the widget with limited powers. The main limit is a **CSP** (content security policy): a list of which websites the page may load images, scripts, and styles from, and which it may send requests to. Your server can ask for more access by declaring domains:

```javascript
registerAppResource(server, "Fleet card (declared CSP)", "ui://fleet-experiment/card-permissive", {
  mimeType: RESOURCE_MIME_TYPE,
  _meta: {
    ui: {
      csp: {
        connectDomains: ["https://api.github.com"],     // fetch() may go here
        resourceDomains: ["https://cdn.jsdelivr.net"],  // images, styles... and more, see below
      },
    },
  },
}, readWidgetHtml);
```

## What the AWS reference chooses

Unicorn Rentals lets a customer browse unicorns, book one, see their bookings, and return one. One MCP server on AgentCore Runtime, AgentCore Gateway in front, business logic in Lambda, data in DynamoDB, images from CloudFront.

Two choices in it are worth separating from the sample itself.

**Not every answer gets a widget.** Browsing and booking show cards. Viewing bookings and returning a unicorn answer in text. The reference says it plainly: not every request needs a rich interface. I would treat that as a design rule, not a shortcut. Every widget is HTML you now have to maintain on hosts you don't control.

**The gateway takes requests with no login.** The gateway accepts calls without checking who the caller is, then calls the runtime with its own IAM role, signing each request with SigV4 (AWS's standard way of signing a request with IAM credentials). The runtime only accepts calls from that role. What protects the front door is edge protection:

- a **WAF** (web application firewall), rules that drop known-bad requests before they reach your code; I covered what those rules catch in [WAF for AgentCore Gateway](/blog/2026-07-02-waf-for-agentcore-gateway.html)
- an **IP allowlist**, so only requests from listed network addresses get in
- **rate limiting**, a cap on how many requests one caller can send per second

That is fine for a demo, and it can be fine for an internal tool with one known client. For anything with customers or tenants, it means nothing between the public internet and your business logic knows who is calling. A firewall rule is not an identity. That is why I argued earlier that [MCP clients on AgentCore Gateway should use the OAuth authorization code flow](/blog/2026-06-03-agentcore-gateway-mcp-oauth-auth-code.html), so each call carries a real user.

## What I ran

I built a small MCP App: a fleet of three fake unicorns, three tools, and two widget resources with **byte-identical HTML** that differ only in their CSP settings (one declares nothing, one declares the two domains above). The widget runs six probes, each trying to load something, and records what the browser itself says was blocked.

- **Host 1: MCP Inspector 2.8.0**, the protocol's local test host, on 2026-09-23.
- **Host 2: Claude Desktop 2.9939.2**, a real host, on 2026-09-26, with the same server added to its config.

Both runs used stdio, which means the host starts the server as a child process on my laptop. No AWS, no public endpoint, no cost. The code and every raw message are in [yopa-experiments](https://github.com/ypark9/yopa-experiments/tree/main/2026-09-26-should-your-service-render-inside-the-ai-host).

## Finding 1: the plumbing works, and you can test more of it locally than I thought

On Inspector, the whole chain worked: tool, `resourceUri`, `resources/read`, render, and the data arriving in the widget.

Two things I did not expect:

- **The widget-or-text rule is enforced by the settings, not by discipline.** Of three tools, only the two carrying `_meta.ui.resourceUri` showed up as apps. The text-only tool never tried to render.
- **You can test the fallback before you have a host.** My server checks whether the host says it supports MCP Apps, and registers text-only versions of the tools if not. I ran both paths locally by connecting a client that did not advertise support.

## Finding 2: same widget, different rules on each host

This is the one I would put at the top of any review. The browser reports the exact policy it enforces, so I didn't have to guess:

| Probe | Inspector, nothing declared | Claude, nothing declared | Claude, domains declared |
| --- | --- | --- | --- |
| inline `data:` image | blocked | **loaded** | loaded |
| image from the declared CDN | blocked | blocked | loaded |
| `fetch()` to the declared API | blocked | blocked | loaded |
| `fetch()` to an undeclared site | blocked | blocked | blocked |
| stylesheet from an undeclared site | blocked | blocked | blocked |
| iframe to an undeclared site | blocked | blocked | blocked |

The spec says that when a widget declares nothing, the host must allow `img-src 'self' data:`, and that it may restrict further. Inspector restricted further (`img-src 'none'`), so a `data:` icon, the obvious way to keep a widget self-contained, broke. Claude followed the spec's default, and then went the other way on scripts: `script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: data:`. Inspector allowed `'unsafe-inline'` only.

- Inspector. Pro: strict, so it catches dependencies you didn't mean to have. Con: it rejects things a real host accepts, so a "broken" widget may be fine in production.
- Claude. Pro: more of your widget just works. Con: `eval` and `data:` scripts are allowed, so the sandbox you are relying on is looser than the one you tested in.

Bottom line, the policy you see on one host is that host's policy, not the protocol's. Test on every host you ship to.

One more trap: my widget also checked each probe in page code (did the image fire `load`, did the stylesheet object exist), and on **both** hosts two of those checks said "loaded" for things the browser had blocked. Only the browser's own `securitypolicyviolation` events were right. If you test your widget's sandbox, read those events, not your own load handlers.

## Finding 3: one image CDN becomes a script source

I declared `resourceDomains: ["https://cdn.jsdelivr.net"]` because I wanted to load one image. On Inspector that domain was added to `script-src`, `style-src`, `img-src`, `font-src`, and `media-src`. On Claude it was added to all of those **and** `worker-src`.

The spec documents this, but the field name reads like "where my pictures come from", and it also means "which sites may run code in my widget". If a widget only needs images, host them on a domain that serves nothing else, or ask whether you need the external image at all. This goes on my review checklist.

## Finding 4: tool list changes, three hosts, three behaviors

The AWS article warns that hosts may cache your tool and resource lists, so a change can arrive late. I made my server add a tool, `late_arrival`, the moment `fleet_status` was first called. The server then sends `notifications/tools/list_changed`, and I watched what each host did.

| Host | What it did after `list_changed` |
| --- | --- |
| MCP Inspector | showed a "List updated" badge, then did nothing until I clicked Refresh, 2 minutes later |
| Claude Desktop, regular chat | asked for the tool list again **1 ms later**; the model found `late_arrival` and called it |
| Cowork (Claude Desktop's agent mode) | never asked again in my one observation; its tool list still has no `late_arrival` |

```
21:20:34.192  host->server  tools/call fleet_status
21:20:34.210  server->host  notifications/tools/list_changed
21:20:34.211  host->server  tools/list          <- 1 ms later, nobody clicked anything
```

So "the host may cache listings" is true, and which way it goes depends on the host, even inside one app. The Cowork row is a single observation, not a controlled test, so treat it as a warning, not a measurement.

## Finding 5: Claude caches your widget HTML inside a connection

I called the same widget tool twice in one chat, 30 seconds apart.

```
21:22:07.913  host->server  resources/read ui://fleet-experiment/card-default   <- first call
21:22:07.913  host->server  tools/call browse_fleet
21:22:38.449  host->server  tools/call browse_fleet                              <- no resources/read
```

Inspector read the resource on every call. Claude read it once and reused it. The data was fresh each time (the "generated at" time changed), but the HTML was not re-read. My widget shows the time the server started, and that stamp only changed when the server process restarted.

So a widget fix you ship while a user's connection is open will not reach that connection. With a local stdio server, a restart is a new connection, so this is easy to miss in testing. With a remote server, a deploy usually does **not** reconnect anyone (I have not tested that case), so plan for old HTML talking to new data for a while, and keep the data format backward compatible.

## Small things worth knowing

- **Claude's handshake is as forgiving as Inspector's.** My widget first sends a `ui/initialize` in the wrong shape on purpose. Both hosts rejected it, and both still showed the widget. A stricter host might not, so don't depend on this.
- **Don't trust `hostInfo.version`.** Claude reported `1.0.0` while the app was 2.9939.2. Inspector reported 2.0.0 while it was 2.8.0. Branch on the capabilities a host declares, not on its version.
- **The widget can call your server back, through the host.** My widget sent its probe results to a tool, `record_probe_report`, marked `_meta.ui.visibility: ["app"]`. It worked, and that tool never showed up in the model's list. That is a clean way to give the view an action the model should not see.
- **The host talks to the model about your widget.** Claude added a line to the tool result telling the model the user can already see the widget, so it should not repeat the data in text.
- **The widget lives at a fixed origin on Claude**, `https://<hash>.claudemcpcontent.com`, and cookies and `localStorage` worked there. Anything a widget stores can outlive the chat. Don't put secrets there.

## The decisions I would make explicitly

| Decision | Options | What I would pick |
| --- | --- | --- |
| Which answers render a widget | Everything, or only answers that need comparing or confirming | Only compare and confirm. Single values, errors, and status stay text |
| Where business logic lives | In the MCP server, or behind it | Behind it. The server is a thin controller |
| Inbound identity | Edge controls only, or a real login at the gateway | A real login for anything with users or tenants |
| Argument checks | Once, in the server | Twice: strict schema in the server, again in the business layer |
| Widget CSP | Declare broad domains, or the minimum | The minimum. Remember `resourceDomains` also allows scripts |
| Widget HTML changes | Assume every call gets the new HTML | Assume an open connection keeps the old HTML. Keep the data format backward compatible |
| Testing | Local host only, or every target host | Local for the wiring, then every host you ship to for the sandbox |

## When I would not do this

If your users already have your app open, a widget in a chat host is a second, smaller interface to maintain. If you need exact control of layout, this is the wrong surface. And if the answer is a number or a status, a sentence beats a card. The AWS reference already follows that last rule.

## What I have not tested

- **A remote server.** Both runs used stdio, where a deploy is a process restart. The real case, a long-lived host connection to a server that gets redeployed, is still untested.
- **Inbound identity.** A stdio server has no network port, so there was no front door to test.
- **Other hosts.** No ChatGPT, no VS Code.
- **Caching across chats or users,** and caching of the resource list (I only changed the tool list).
- **The AWS sample itself.** My server is my own. I did not deploy Unicorn Rentals.

## What to do

Before you ship a widget into someone else's AI host, answer these:

1. Which of your answers really need comparing or confirming, rather than a sentence?
2. If the gateway got a request with no identity, what would stop it, and do you control that thing?
3. What does your widget's CSP actually allow on each host you target? Did you read the browser's violation events, or your own load checks?
4. If a user's open chat kept your old widget HTML for an hour after you deployed, would it still work with the new data?

If the answer to the first is "most of them", you are building a product inside someone else's product, and the second question is where to spend the review.

## Related posts

- [MCP clients on AgentCore Gateway need the OAuth authorization code flow](/blog/2026-06-03-agentcore-gateway-mcp-oauth-auth-code.html): the identity question this reference skips.
- [WAF for AgentCore Gateway](/blog/2026-07-02-waf-for-agentcore-gateway.html): what edge rules catch, and what they don't.
- [MCP and A2A as different contracts on AgentCore](/blog/2026-08-01-mcp-and-a2a-boundaries-on-agentcore.html).
- [What changed when MCP went stateless](/blog/2026-08-09-mcp-goes-stateless.html).
- [Your agent's refusal only covers the rules you wrote down](/blog/2026-09-26-where-should-agent-refusals-live.html): why the layer that owns the data makes the final check.

## Sources

- AWS Machine Learning Blog, [Build interactive MCP Apps using Amazon Bedrock AgentCore](https://aws.amazon.com/blogs/machine-learning/build-interactive-mcp-apps-using-amazon-bedrock-agentcore/), September 11, 2026.
- Sample application, [aws-samples/sample-agentcore-mcp-apps](https://github.com/aws-samples/sample-agentcore-mcp-apps).
- MCP Apps extension overview, [modelcontextprotocol.io/extensions/apps/overview](https://modelcontextprotocol.io/extensions/apps/overview).
- MCP Apps specification, [SEP-1865](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx), stable 2026-01-26.

The reading of the AWS reference is from its published article and code. The findings come from my own runs: MCP Inspector 2.8.0 on 2026-09-23 and Claude Desktop 2.9939.2 on 2026-09-26, both with a local stdio server built on `@modelcontextprotocol/ext-apps` 2.0.0. No AWS deployment was made for this post.
