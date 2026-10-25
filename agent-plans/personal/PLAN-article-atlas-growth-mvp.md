# Article Atlas Growth MVP

Status: deployed; four-week measurement window active
Last updated: 2026-08-09
Release date: 2026-08-09
First four-week evaluation: 2026-09-06

Fresh-session context: `SESSION_HANDOFF.md`

This is the source of truth for the first Article Atlas growth release. Update
the checkbox and its evidence in the same change that completes each item.
Unchecked owner tasks must never be inferred as complete from code changes.

## Outcome

Ship one bilingual, measurable Expedition that moves a useful article visit
toward deeper discovery and an optional monthly relationship, without accounts,
personal visitor tracking, or gated world features.

## Working rule

- `[x]` means implemented and verified. Add the verification evidence inline.
- `[~]` means implemented but waiting for owner or production verification.
- `[ ]` means not started or blocked.
- Every implementation turn updates this file before handoff.
- Maker's Road, Workshop, App Garden, and Presence remain outside this MVP.

## A. Utility and portfolio layer

- [x] Homepage offers `Solve a problem`, `See what I am learning`, and
  `Explore the Atlas`. Evidence: Hugo production build and EN/KO browser smoke.
- [x] About pages explain purpose, expertise, proof of work, and contact paths
  in English and Korean. Evidence: `content/about.md`, `content/about.ko.md`.
- [x] Journey articles expose a normal article URL and an Expedition CTA.
  Evidence: Hugo output smoke test.
- [x] Article metadata records region, journey, evidence, and era for all five
  bilingual stops. Evidence: `scripts/validate_expeditions.py`.

## B. First Expedition

- [x] `safe-agent-operations` has the same five-stop structure in English and
  Korean. Evidence: expedition validator passes.
- [x] All stops remain reachable without JavaScript. Evidence: static ordered
  list and `<noscript>` fallback in the expedition template.
- [x] Progress is local-only and fails open when storage is unavailable or
  damaged. Evidence: unknown stop IDs are discarded and storage calls are
  guarded.
- [x] Start, stop, and first completion interactions emit coarse GA events.
  Evidence: client tests and browser completion smoke.
- [x] Completion shows principles, checklist, related route, and optional
  Dispatch CTA. Evidence: 5/5 browser interaction smoke.
- [x] Expedition pages contain no article ad or Ko-fi trap. Evidence: EN/KO
  browser DOM smoke.
- [x] Keyboard focus moves to the completion result and progress has an
  accessible label. Evidence: browser completion smoke.
- [x] Responsive mobile browser smoke passes at 390×844 with no horizontal
  overflow and a 52px start action. Evidence: EN Expedition and EN/KO confirmed
  pages in the local browser.
- [x] Reduced-motion behavior selects non-animated scrolling. Evidence:
  `matchMedia("(prefers-reduced-motion: reduce)")` client path and syntax tests.
- [x] Storage failures are handled as an optional-progress condition: reads and
  writes are guarded, and the Expedition remains usable without persisted
  progress. Evidence: client contract and unit checks. A browser-enforced smoke
  is useful but is not a release blocker for this MVP.
- [ ] Screen-reader and physical-mobile acceptance are non-blocking follow-up
  checks for this MVP. Responsive browser and keyboard-focus checks remain the
  release evidence.

## C. GA4 aggregate baseline

- [x] Integration decision: use Google's experimental Analytics MCP for
  conversational read-only investigation, while retaining
  `scripts/ga4_baseline.py` for reproducible fixed monthly snapshots.
- [x] Read-only aggregate reporting script exists with four fixed report groups.
- [x] Credential and analytics output paths are ignored by Git.
- [x] Tests exclude user ID, pseudo ID, city, and individual session dimensions.
- [x] Growth funnel includes anonymous page views for only the two language
  confirmation paths; it does not create a subscriber event or identifier.
- [x] **Owner:** created a dedicated Google Cloud project.
- [x] **Owner:** enabled Google Analytics Data API v1 and Google Analytics Admin
  API in that project. The MCP exposes read-only property metadata as well as
  Data API reports.
- [x] **Owner:** created a dedicated service account and stored its JSON key at
  `.secrets/ga4-viewer.json`, outside Git tracking, with mode `600`.
- [x] **Owner:** added the service-account identity to the yopa.page property
  with `Viewer` only; no account-level, Analyst, Editor, or Administrator access.
- [x] **Owner:** recorded the numeric GA4 property ID privately in the ignored
  `.secrets/ga4.env`; no credential value was written to Codex, GitHub, cxdoc,
  logs, or this document.
- [x] **Joint:** installed `analytics-mcp` 0.7.0 with `pipx` and configured the
  local Codex client through an ignored credential wrapper. A new Codex task
  may be required before the server appears as a tool.
- [x] **Joint:** verified the MCP sees only the intended yopa.page property with
  `can_edit: false`; a host-filtered seven-day aggregate `run_report` returned
  successfully with no sampling metadata. Evidence: fresh Codex task on
  2026-08-09; no user/session identifiers queried.
- [~] **Joint:** generated the first unsampled 12-month aggregate baseline for
  2025-08-09 through 2026-08-08. A host-filtered totals report now exposes
  sessions, active users, and views for direct GA UI comparison; owner UI
  comparison remains pending and is not a deployment blocker.
- [x] Development builds omit GA entirely and all baseline reports filter to
  `www.yopa.page` or `yopa.page`, preventing localhost preview pollution.
- [~] **Joint:** release date recorded as 2026-08-09. Repeat the same report on
  2026-09-06 after the first 28-day measurement window.

GA4 owner handoff completed on 2026-08-09. Never paste the JSON contents into a
task, issue, log, or knowledge note.

## D. Field Dispatch

- [x] beehiiv remote MCP is registered and OAuth-authorized in the local Codex
  client. Evidence: `codex mcp get beehiiv` reports the streamable HTTP endpoint
  enabled and the login command completed successfully.
- [x] **Joint:** verified beehiiv MCP tools in a fresh Codex task by listing the
  accessible publication and reading publication-level settings. Evidence:
  successful read-only calls on 2026-08-09; no subscriber email addresses,
  custom fields, or individual subscriber records retrieved.
- [x] **Owner:** reused the existing publication as
  `Field Dispatch — English`, preserving its public URL. Evidence: MCP settings
  write and read-back on 2026-08-09.
- [x] **Owner:** created `Field Dispatch — 한국어` at the approved
  `yopa-field-dispatch-ko` subdomain. Evidence: browser creation and public-page
  verification on 2026-08-09.
- [x] **Owner:** enabled Double Opt-in Email and Smart Nudge for both
  publications and set language-specific sender names. Evidence: MCP read-back
  for English and browser reload verification for Korean on 2026-08-09.
- [x] **Owner:** each publication has a public home signup form and passed the
  end-to-end signup flow with owner-controlled addresses on 2026-08-09.
- [x] **Owner:** set confirmed opt-in redirects to the matching yopa.page
  English and Korean confirmation pages. Evidence: English MCP read-back and
  Korean browser reload verification on 2026-08-09.
- [x] **Owner:** verified confirmation, welcome email, and unsubscribe using two
  owner-controlled test addresses, one per publication. Evidence: owner
  acceptance signal on 2026-08-09; no subscriber data was shared with Codex.
- [x] **Owner:** verified and recorded both public hosted subscribe URLs. Each
  public page rendered its own email form; no subscriber data was accessed.
- [x] **Joint:** added both public URLs to `params.fieldDispatch` and enabled
  both language CTAs after owner end-to-end acceptance passed.
- [x] **Joint:** confirmed a Korean signup never enters the English publication,
  and vice versa. Evidence: owner acceptance in the beehiiv UI on 2026-08-09;
  no subscriber records were queried by Codex.
- [ ] **Joint:** verify `dispatch_cta` plus anonymous thank-you page measurement
  without sending email or subscriber identifiers to GA. The local pages and
  aggregate report filter are complete; production measurement is pending.
- [~] First monthly EN/KO Dispatch drafts are prepared under
  `docs/field-dispatch/`; owner editorial approval and sending remain pending.
  Automatic machine translation is not sent.

Owner handoff signal: say `beehiiv 준비 완료` and send only the two public
subscribe URLs. Do not send subscriber exports or account credentials.

## E. Release and measurement gates

- [x] JavaScript syntax checks pass.
- [x] Frontmatter validation passes for 306 articles.
- [x] Expedition validation passes.
- [x] Unit suite passes: 66 tests. Evidence: full discovery run on 2026-08-09.
- [x] Hugo production build passes: EN 956 pages, KO 408 pages. Evidence:
  Hugo 0.155.1 production build on 2026-08-09.
- [x] Development HTML omits GA while production HTML includes it. Evidence:
  isolated destination builds and exact Google-tag scan on 2026-08-09.
- [x] `git diff --check` passes. Evidence: 2026-08-09 release-candidate run.
- [x] Scoped Article Atlas Growth changes were reviewed and merged through PRs
  #69–#71. Final release merge: `28bfd4d` on 2026-08-09.
- [x] MVP deployment passed GitHub Actions and production smoke on 2026-08-09.
  Evidence: yopa.page CI run `31337894255`; EN/KO CTA, confirmation pages,
  5/5 completion focus, header/footer, 320px overflow, and no Expedition ads or
  Ko-fi verified on production.
- [~] Collect four weeks of baseline data through 2026-09-06.
- [ ] Gate: Expedition CTA exposure-to-start rate is at least 3%.
- [ ] Gate: Expedition start-to-completion rate is at least 25%.
- [ ] Gate: confirmed subscription among completers is at least 5%.
- [ ] Gate: Atlas visitors' additional article discovery improves over baseline.
- [ ] Gate: no Dispatch is missed for two consecutive months.

If a gate fails, revise entry-page choice, CTA, route length, or stop value. Do
not add new world systems to compensate for an unproven visitor loop.
