"""Build-output checks for the Search Console indexing fixes.

Thin tag and category pages are candidates for the reported soft 404s;
the exact Search Console URL mapping is unverified. These tests verify the
publishing policy and the concrete list/canonical/redirect regressions.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
ROBOTS = re.compile(r'<meta name="?robots"? content="([^"]+)"')
POST_LINK = re.compile(r"<div class=post><a href=([^ >]+)")
COUNT = re.compile(r"class=count>(\d+)<")


class HeadLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.canonicals = []
        self.languages = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonicals.append(attrs.get("href"))
        if tag == "link" and attrs.get("hreflang"):
            self.languages.append(attrs)


class SearchIndexingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix="yopa-indexing-test-"))
        # A useful section with one child must not inherit the term-count policy.
        content = cls.out / "fixture-content"
        shutil.copytree(ROOT / "content", content)
        (content / "reference").mkdir()
        (content / "reference/_index.en.md").write_text("---\ntitle: Reference\n---\n")
        (content / "reference/_index.ko.md").write_text(
            '---\ntitle: Reference\nrobots: "noindex, follow"\n---\n')
        (content / "reference/guide.en.md").write_text("---\ntitle: Reference guide\n---\nA useful guide.\n")
        # Explicitly excluded utility sections stay excluded as they grow.
        (content / "dispatch/another.en.md").write_text("---\ntitle: Another utility page\n---\n")
        subprocess.run(
            ["hugo", "--gc", "--minify", "--cacheDir", str(cls.out / ".hugo-cache"),
             "--contentDir", str(content), "--destination", str(cls.out)],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        cls.sitemap = set()
        for name in ("en/sitemap.xml", "ko/sitemap.xml"):
            xml = (cls.out / name).read_text()
            cls.sitemap.update(re.findall(r"<loc>https://www\.yopa\.page/([^<]*)</loc>", xml))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out)

    def html(self, rel):
        return (self.out / rel).read_text()

    def robots(self, rel):
        match = ROBOTS.search(self.html(rel))
        return match.group(1) if match else ""

    def term_pages(self):
        for kind in ("tags", "categories"):
            for page in sorted((self.out / kind).glob("*.html")):
                text = page.read_text()
                if page.name == "index.html" or "http-equiv=refresh" in text[:400]:
                    continue
                yield f"{kind}/{page.name}", text

    def test_thin_term_pages_are_noindex_and_left_out_of_the_sitemap(self):
        thin = 0
        for rel, text in self.term_pages():
            count = int(COUNT.search(text).group(1))
            with self.subTest(page=rel, posts=count):
                if count < 2:
                    thin += 1
                    self.assertEqual(self.robots(rel), "noindex, follow")
                    self.assertNotIn(rel, self.sitemap)
                else:
                    self.assertEqual(self.robots(rel), "")
                    self.assertIn(rel, self.sitemap)
        self.assertGreater(thin, 0)

    def test_header_count_matches_the_posts_listed(self):
        for rel, text in self.term_pages():
            count = int(COUNT.search(text).group(1))
            with self.subTest(page=rel):
                if count == 0:
                    self.assertIn("There are no current posts here", text)
                    self.assertEqual(POST_LINK.findall(text), [])
                else:
                    self.assertNotIn("There are no current posts here", text)
                    self.assertGreater(len(POST_LINK.findall(text)), 0)
                self.assertNotIn("1 posts", text)

    def test_page_two_lists_different_posts_than_page_one(self):
        first = set(POST_LINK.findall(self.html("blog/index.html")))
        second = set(POST_LINK.findall(self.html("blog/page/2/index.html")))
        first = {link.rsplit("/", 1)[-1] for link in first}
        second = {link.rsplit("/", 1)[-1] for link in second}
        self.assertTrue(first and second)
        self.assertEqual(first & second, set())

    def test_tag_and_category_indexes_have_one_page(self):
        self.assertFalse((self.out / "tags/page/2").exists())
        self.assertFalse((self.out / "categories/page/2").exists())

    def test_retained_taxonomy_pagers_are_self_canonical(self):
        checked = {"tags": 0, "categories": 0}
        for kind in checked:
            for page in (self.out / kind).glob("*/page/*.html"):
                if int(page.stem) < 2:
                    continue
                rel = page.relative_to(self.out).as_posix()
                with self.subTest(page=rel):
                    self.assertEqual(HeadLinks(page.read_text()).canonicals,
                                     [f"https://www.yopa.page/{rel}"])
                    self.assertEqual(self.robots(rel), "")
                    self.assertGreater(len(POST_LINK.findall(page.read_text())), 0)
                checked[kind] += 1
        self.assertTrue(all(checked.values()))

    def test_later_home_pager_has_no_first_page_canonical_or_language_alternate(self):
        links = HeadLinks(self.html("page/2/index.html"))
        self.assertEqual(links.canonicals, ["https://www.yopa.page/page/2/index.html"])
        self.assertEqual(links.languages, [])

    def test_head_pagination_does_not_reintroduce_archived_posts(self):
        archived = {
            "https://www.yopa.page/blog/" + re.sub(r"(?:\.en)?\.md$", ".html", page.name)
            for page in (ROOT / "content/blog").glob("*.md")
            if re.search(r"^maintenance_status: archived$", page.read_text(), re.M)
        }
        self.assertTrue(archived)
        pages = [self.out / "index.html", self.out / "page/2/index.html"]
        for kind in ("tags", "categories"):
            pages.extend((self.out / kind).rglob("*.html"))
        for page in pages:
            rel = page.relative_to(self.out).as_posix()
            links = {urljoin(f"https://www.yopa.page/{rel}", link)
                     for link in POST_LINK.findall(page.read_text())}
            with self.subTest(page=rel):
                self.assertFalse(links & archived)
                self.assertLessEqual(len(links), 8)

    def test_single_child_sections_are_indexable_unless_explicitly_excluded(self):
        self.assertEqual(self.robots("reference/index.html"), "")
        self.assertIn("reference/index.html", self.sitemap)
        self.assertEqual(self.robots("dispatch/index.html"), "noindex, follow")
        self.assertNotIn("dispatch/index.html", self.sitemap)

    def test_language_alternates_do_not_advertise_excluded_pages(self):
        self.assertEqual(HeadLinks(self.html("dispatch/index.html")).languages, [])
        self.assertEqual(HeadLinks(self.html("reference/index.html")).languages, [])
        self.assertNotIn("https://www.yopa.page/ko/reference/index.html",
                         (self.out / "en/sitemap.xml").read_text())

    def test_home_pages_use_directory_urls(self):
        for rel, url in (("index.html", "https://www.yopa.page/"),
                         ("ko/index.html", "https://www.yopa.page/ko/")):
            with self.subTest(page=rel):
                self.assertIn(f"rel=canonical href={url}>", self.html(rel))
        self.assertIn("", self.sitemap)
        self.assertIn("ko/", self.sitemap)
        self.assertNotIn("index.html", self.sitemap)
        self.assertNotIn("ko/index.html", self.sitemap)

    def test_duplicate_and_thank_you_pages_are_noindex_and_not_in_sitemap(self):
        for rel in ("blog/index.html", "dispatch/index.html", "ko/dispatch/index.html",
                    "expeditions/index.html", "ko/expeditions/index.html",
                    "dispatch/confirmed.html", "ko/dispatch/confirmed.html"):
            with self.subTest(page=rel):
                self.assertEqual(self.robots(rel), "noindex, follow")
                self.assertNotIn(rel, self.sitemap)
        for rel in ("articles.html", "about.html", "tags/index.html"):
            with self.subTest(page=rel):
                self.assertEqual(self.robots(rel), "")
                self.assertIn(rel, self.sitemap)

    def test_old_article_urls_forward_to_their_successors(self):
        for old, new in (
            ("2025-12-10-agent-factory-scaling-ai-employee-creation", "2026-08-01-build-a-governed-agent-platform-on-aws"),
            ("2026-05-30-personal-aws-cost-guardrails", "2026-03-30-personal-aws-cost-guardrails"),
            ("2026-08-10-claude-code-agent-teams", "2026-08-10-claude-code-cross-session-messaging"),
            ("2026-08-10-deprecating-agent-pingpong", "2026-08-10-claude-code-cross-session-messaging"),
            ("2026-09-21-should-your-service-render-inside-the-ai-host", "2026-09-26-should-your-service-render-inside-the-ai-host"),
            ("2026-09-21-where-should-agent-refusals-live", "2026-09-26-where-should-agent-refusals-live"),
            ("2026-09-23-ecs-deployment-observability", "2026-09-27-ecs-deployment-observability"),
            ("2026-09-24-agent-observability-correctness-not-uptime", "2026-09-28-would-the-evaluator-catch-the-wrong-refund"),
            ("2024-01-19-mastering-chatgpt-for-efficient-software-development", "2026-08-01-evidence-driven-ai-assisted-software-development"),
        ):
            with self.subTest(old=old):
                text = self.html(f"blog/{old}.html")
                self.assertIn(f"url=https://www.yopa.page/blog/{new}.html", text)
                self.assertTrue((self.out / f"blog/{new}.html").is_file())
                self.assertNotIn(f"blog/{old}.html", self.sitemap)


if __name__ == "__main__":
    unittest.main()
