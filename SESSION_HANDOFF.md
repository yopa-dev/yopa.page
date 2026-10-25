# Article Atlas Growth MVP — Session Handoff

Last updated: 2026-08-09
Repository: yopa.page repository root
Status: deployed on 2026-08-09; four-week measurement window active

## Start here

Continue the Article Atlas Growth MVP from the existing working tree. Read, in
order:

1. `AGENTS.md`
2. `agent-plans/personal/PLAN-article-atlas-growth-mvp.md`
3. `docs/ATLAS_GROWTH_OPERATIONS.md`
4. this handoff

Run `cxdoc current . --json` and search yopa.page knowledge before relying on
older session memory. Do not discard or overwrite the current working tree.
The MVP was merged through PRs #69–#71 and deployed on 2026-08-09. The release
merge is `28bfd4d`.

## Product decision

Article Atlas is:

> Public evidence of one developer's continued growth, and a living knowledge
> world where working engineers solve a problem and find a reason to return.

The first six-month loop is:

```text
search or direct link
→ useful article
→ safe-agent-operations Expedition
→ practical result
→ language-specific Field Dispatch
→ monthly return
```

World expansion is gated. Do not implement Maker's Road, Workshop, App Garden,
Presence, accounts, inventory, currency, streaks, leaderboards, or AI NPCs until
the first Expedition has four weeks of trustworthy evidence.

## Implemented

### Utility and portfolio

- Homepage entrances: Solve a problem, See what I am learning, Explore Atlas.
- English and Korean About pages.
- Journey CTA on five bilingual agent-operation articles.
- Explicit `atlas` frontmatter for region, object, journey, evidence, and era.

### First Expedition

- Journey ID: `safe-agent-operations`.
- English: `/expeditions/safe-agent-operations.html`.
- Korean: `/ko/expeditions/safe-agent-operations.html`.
- Five matching stops with normal article URLs and static HTML fallback.
- Local-only progress with damaged-storage sanitization.
- Coarse events: `expedition_view`, `expedition_start`,
  `expedition_stop_complete`, `expedition_complete`, and `dispatch_cta`.
- First-completion deduplication and implicit start tracking.
- Accessible progress label and completion focus.
- No AdSense or Ko-fi surface inside an Expedition.

### yopa.page email preparation

- English and Korean CTA configuration is enabled in `config.yaml` after owner
  end-to-end acceptance passed on 2026-08-09.
- Both verified public beehiiv URLs are recorded.
- Confirmation pages:
  - `/dispatch/confirmed.html`
  - `/ko/dispatch/confirmed.html`
- First English and Korean monthly drafts in `docs/field-dispatch/`.
- beehiiv remote MCP registered and OAuth-authorized in Codex:
  `https://mcp.beehiiv.com/mcp`.

### GA4 and analytics

- Google Cloud project, Data API, Admin API, service account, property-level
  Viewer access, and numeric property ID are owner-configured.
- Secrets are ignored and mode `600`:
  - `.secrets/ga4-viewer.json`
  - `.secrets/ga4.env`
- Never print, commit, paste, or store their contents in cxdoc.
- Google `analytics-mcp` 0.7.0 is installed with pipx and registered in Codex
  through `.secrets/run-analytics-mcp`.
- `.venv-analytics` holds the pinned client for deterministic snapshot reports.
- `scripts/ga4_baseline.py` produces aggregate JSON, CSV, and Markdown under the
  ignored `analytics-output/` directory.
- All reports filter to `www.yopa.page` and `yopa.page`.
- Development Hugo builds do not load GA.
- Empty report runs remove stale CSV files.

## GA4 baseline status

Generated at `analytics-output/2026-08-09/` for:

- current: 2025-08-09 through 2026-08-08;
- prior: 2024-08-09 through 2025-08-08.

All reports were unsampled. After excluding localhost preview traffic:

- Acquisition: 200 aggregate rows in each period, limited by the fixed query.
- Content language: 500 aggregate rows in each period, limited by the query.
- Atlas discovery: 35 current aggregate rows, 0 prior rows.
- Growth funnel: 0 current rows, 0 prior rows.

The first run exposed that local Hugo previews were sending events to the
production property. Those local Expedition and confirmation-page events were
not real visitor conversions. The template and report host filters now prevent
future pollution. Do not use the earlier contaminated funnel rows.

GA UI total comparison is still pending. The baseline output is private and
ignored; do not commit it.

## MCP status for the new session

Both servers are configured globally but must be verified as callable in a
fresh Codex task:

```sh
codex mcp get analytics-mcp
codex mcp get beehiiv
codex mcp list
```

Expected:

- `analytics-mcp`: enabled stdio command pointing to
  `.secrets/run-analytics-mcp`.
- `beehiiv`: enabled streamable HTTP endpoint at
  `https://mcp.beehiiv.com/mcp`.

Privacy policy for both MCPs:

- use aggregate reports only;
- do not request individual session timelines;
- do not query user IDs, pseudo IDs, city-level location, subscriber email,
  subscriber custom fields, or individual subscriber records;
- require user confirmation before beehiiv write actions;
- publishing or sending remains an owner-final action.

If OAuth approval is needed again, print the URL for the owner to open in the
system browser. The Codex in-app browser may lose the localhost OAuth callback.

## beehiiv account state and next owner-assisted work

Completed on 2026-08-09:

- Reused and renamed `yopa.page` to `Field Dispatch — English`; preserved
  `https://yopapage.beehiiv.com/`.
- Created `Field Dispatch — 한국어` at
  `https://yopa-field-dispatch-ko.beehiiv.com/`.
- Enabled Double opt-in and Smart Nudge for both publications.
- Set the sender name to the matching publication name.
- Verified that both public home pages render an email signup form.
- Set confirmed opt-in redirects:
   - English: `https://www.yopa.page/dispatch/confirmed.html`
   - Korean: `https://www.yopa.page/ko/dispatch/confirmed.html`

Owner acceptance completed on 2026-08-09:

1. Required publication details were completed privately in beehiiv; no postal
   address or subscriber data was shared with Codex.
2. Confirmation, welcome, and unsubscribe passed with separate
   owner-controlled addresses.
3. English and Korean publication isolation passed in the beehiiv UI.
4. Both languages are enabled in `config.yaml`.

The beehiiv MCP OAuth view was stale immediately after creating the Korean
publication: it returned only the pre-existing publication and its old name.
Refresh or reauthorize the MCP before relying on it for Korean publication
reads; browser state is the current evidence.

## Verification already completed

- `python3 scripts/validate_frontmatter.py`: 306 articles passed.
- `python3 scripts/validate_expeditions.py`: passed.
- `python3 -m unittest discover -s tests`: 66 tests passed.
- `hugo --gc --minify`: passed (EN 956 pages, KO 408 pages).
- Development build contains no Google tag.
- Production build contains the Google tag.
- English and Korean mobile browser smoke at 390×844 passed with no horizontal
  overflow.
- English 5/5 Expedition completion and result focus passed.
- English and Korean confirmation pages rendered without ads or browser errors.
- JavaScript-off output retains every Expedition stop link.
- `git diff --check`: passed.
- PR #71 merge commit `28bfd4d`: Secret scan and yopa.page CI passed.
- Production smoke on 2026-08-09: header/footer present; 320px navigation has
  no horizontal overflow; About has no Copy for AI button; EN/KO Expedition
  CTAs target the matching beehiiv publications; 5/5 completion focuses the
  result; EN/KO confirmation pages render without ads; Expedition contains no
  AdSense or Ko-fi surface.

Remaining acceptance priorities:

- GA UI versus API totals comparison is required before interpreting the
  four-week growth result, but does not block deployment.
- A browser-enforced blocked-local-storage smoke is useful but non-blocking;
  guarded read/write behavior is already verified structurally.
- Screen-reader and physical-mobile checks are non-blocking follow-up work for
  this MVP; responsive browser and keyboard-focus evidence already passed.

## Release and measurement boundary

The MVP was released on 2026-08-09. Keep the visitor loop stable through the
first evaluation on 2026-09-06 except for production defects. Do not begin
Maker's Road, Workshop, App Garden, or Presence during this window.

The existing personal world plan remains at
`agent-plans/personal/PLAN-article-atlas-world.md`. The actionable MVP source of
truth is `agent-plans/personal/PLAN-article-atlas-growth-mvp.md`; update its
checkboxes and evidence in the same change that completes an item.

## Recommended next sequence

1. Verify the two MCP servers are callable in the fresh session.
2. Use Analytics MCP only to confirm the service account sees the intended
   yopa.page property and run one harmless aggregate query.
3. Use beehiiv MCP only for read-only state confirmation; do not inspect
   subscriber identity data.
4. Generate the host-filtered API totals and compare them with the same GA UI
   date range when convenient.
5. Repeat the aggregate baseline on 2026-09-06 and evaluate the MVP gates.

## Validation commands

```sh
node --check static/js/atlas-growth.js
node --check static/js/expedition.js
python3 scripts/validate_frontmatter.py
python3 scripts/validate_expeditions.py
python3 -m unittest discover -s tests
hugo --gc --minify
git diff --check
git status --short
```

To regenerate the private aggregate baseline:

```sh
source .secrets/ga4.env
.venv-analytics/bin/python scripts/ga4_baseline.py \
  --as-of YYYY-MM-DD \
  --output-dir analytics-output/YYYY-MM-DD
```
