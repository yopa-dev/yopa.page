# Article Maintenance: 2026-11

Reviewed: 2026-11-01

This ledger records article maintenance in November 2026. It follows the conventions of the [2026-10 freshness pass](article-maintenance-2026-10.md).

## Removed at the owner's request

The owner asked to take these two articles off the site. They are deleted outright rather than archived.

| Article | Former URL | Successor |
| --- | --- | --- |
| `2026-10-30-mlflow-scorer-allowlist-prefix.en.md` | `/blog/2026-10-30-mlflow-scorer-allowlist-prefix.html` | None |
| `2026-10-23-git-cliffs-before-scion.en.md` | `/blog/2026-10-23-git-cliffs-before-scion.html` | None |

- Neither article has a suitable replacement, so per [search-indexing.md](search-indexing.md) both URLs stay genuine 404s. No edge 301 or Hugo alias was added, and `terraform/` is unchanged.
- No other article, layout, data file or test referenced either slug, so no links needed editing.
- The experiment code in `ypark9/yopa-experiments` is left in place; only the articles that linked to it were removed.
- After the deploy, the article list, tag pages, RSS feed and sitemap no longer include either URL. The sitemap is resubmitted in Search Console so Google recrawls it. Faster removal from search results is a manual Search Console Removals request.

## Validation

`python3 scripts/validate_frontmatter.py`, `python3 scripts/validate_article_tags.py`, `python3 scripts/validate_expeditions.py`, `python3 -m unittest discover -s tests`, `node --test terraform/modules/website/draw_rewrite.test.mjs`, and `hugo --gc --minify` ran locally before the pull request was pushed.

## Cost and environment

- Local work made no AWS calls and used no paid APIs.
- GitHub CI on the pull request runs the repository's `plan (global)` and `plan (prod)` jobs, which assume the read-only plan role through OIDC. The actual AWS bill for those runs was not checked and is unconfirmed.
