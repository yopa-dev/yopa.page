# Search indexing policy and deployment checks

## Publishing policy

- English articles are the maintained article corpus. The Korean home and
  localized non-article features remain available and indexable where useful.
- Tag and category term pages with fewer than two visible, non-archived posts
  receive `noindex, follow` and are omitted from the sitemap. This is a local
  publishing policy, not a Google threshold. Review Search Console performance
  before expanding it or removing useful topic pages. Merge synonymous tags
  only when they describe the same topic and have an appropriate destination.
- Sections do not inherit that threshold. Dispatch and Expedition list pages
  explicitly opt out in their `_index` front matter, so adding a second child
  does not silently change their indexing policy. Their substantive pages can
  remain indexable. Subscription confirmations are also excluded explicitly.
- Keep excluded HTML pages crawlable so Google can read their `noindex`. Do
  not add a matching robots.txt disallow as a second indexing control.
- Every retained pager uses its own canonical URL. The home page itself uses
  `/` or `/ko/`; later English home pagers have no Korean pager alternate.
  Unused later home URLs (`/page/2/`, `/page/2/index.html` and later numbers)
  permanently redirect to `/articles.html` at CloudFront. Their generated
  origin HTML is not an independently served search landing page.
  Head and body call the same paginator partial because Hugo caches the first
  pagination invocation. Sitemap and translation URLs do not initialize it.
  HTML and sitemap hreflang clusters omit noindex or sitemap-disabled locales.
- `/blog/` and its list pages permanently redirect to `/articles.html`.
  The origin list HTML is also noindex as a fallback. A viewer receiving the
  edge 301 does not read that HTML. Keep `/articles.html` indexable, 200 and
  self-canonical, and preserve individual article URLs and `/blog/index.xml`.
- Exact deleted article URLs with established successors receive edge 301s.
  Hugo aliases provide matching zero-second meta-refresh fallbacks at the
  origin. Two historical successors were themselves archived, so those old
  deleted URLs go directly to the current guides named by their replacement
  metadata. Existing archived article URLs remain available for reference.
- Deleted pages with no suitable replacement remain genuine 404s. Do not send
  them all to the home page or an unrelated topic.

## Evidence boundaries

The October 18, 2026 Search Console counts were supplied by the site owner.
The October 25 warning email names a new canonical-selection reason. The email
does not identify the 90 soft 404 URLs, the 11 missing URLs or the 55 crawled but
not indexed URLs. The thin term pages are candidates for the soft 404s until
the actual example URLs are compared. Sitemap cleanup and passing build tests
do not establish that Google has recrawled, selected the requested canonicals,
or indexed any additional articles.

The existing `/ko/tags/agentcore.html` redirect to `/tags/agentcore.html` is
consistent with the intended canonical. Recheck Google's stored selection
after recrawl; do not promise that the warning will disappear immediately.

## After deployment

1. Confirm the content promotion, CloudFront Function update and invalidation
   succeeded. PR CI plans the infrastructure change; it does not deploy it.
2. Check actual responses, using the generated pager URL spellings:

   | URL | Expected result |
   | --- | --- |
   | `/`, `/ko/` | 200, self-canonical directory URL, indexable |
   | `/dimly/` | 200, standalone page; its custom head currently has no canonical tag |
   | `/tags/python/page/2.html` | 200, self-canonical, next set of visible posts |
   | `/categories/python/page/2.html` | 200, self-canonical |
   | `/blog/`, `/blog/page/2/index.html` | 301 directly to `/articles.html` |
   | `/page/2/`, `/page/28/index.html` | 301 directly to `/articles.html` |
   | `/tags/page/2/index.html` | 301 to `/tags/index.html` |
   | `/ko/tags/agentcore.html` | 301 to `/tags/agentcore.html`, then 200 |
   | `/blog/2025-12-10-agent-factory-scaling-ai-employee-creation.html` | 301 to `/blog/2026-08-01-build-a-governed-agent-platform-on-aws.html` |
   | `/blog/index.xml`, a current article | 200, no unintended redirect |
   | A deliberately nonexistent article | 404, not a 200 error page |

   Check the remaining retired article mappings and query-string preservation
   against `draw_rewrite.test.mjs`. Check that utility pages and thin terms
   return noindex, while important articles and redirect targets do not.
3. Fetch `/sitemap.xml` and its English and Korean children. Verify every
   listed URL is a desired canonical, with no redirect or noindex entries.
   Resubmit the sitemap index once; repeated unchanged submissions do not
   guarantee faster crawling. Check that robots.txt permits these resources.
4. Export or record Search Console's affected example URLs. Separate unwanted
   pages from live pages that should be indexed. In particular, determine
   whether the 55 crawled-but-not-indexed URLs are articles or utility pages.
5. Use URL Inspection's live test on representative corrected URLs to verify
   fetch, rendering and indexing directives. Its live test does not verify
   Google's chosen canonical. Check that field in the stored indexing report
   after recrawl, alongside the last crawl date and declared canonical.
6. Start Validate fix for an issue group after checking its affected examples.
   Do not assume all intentionally deleted URLs must stop reporting 404s.
   Request indexing selectively for important corrected indexable URLs, not
   for redirects or deliberately excluded pages.
7. Record a baseline for important articles: indexing state, impressions and
   clicks. Compare after recrawl using comparable periods. Expected noindex,
   redirect and intentional 404 exclusions are not a failure; the goal is
   healthy indexing of useful pages rather than zero excluded URLs.

## References

- [Google pagination guidance](https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading)
- [Google redirects guidance](https://developers.google.com/search/docs/crawling-indexing/301-redirects)
- [Google noindex guidance](https://developers.google.com/search/docs/crawling-indexing/block-indexing)
- [Search Console Page indexing report](https://support.google.com/webmasters/answer/7440203?hl=en)
- [Hugo pagination caching](https://gohugo.io/templates/pagination/)
