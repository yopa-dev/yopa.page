"""Build-output checks for the Search Console indexing fixes.

Google reported thin tag and category pages as soft 404s and saw copies of
list pages at /page/N/. These tests keep those problems from coming back.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROBOTS = re.compile(r'<meta name="?robots"? content="([^"]+)"')
POST_LINK = re.compile(r"<div class=post><a href=([^ >]+)")
COUNT = re.compile(r"class=count>(\d+)<")


class SearchIndexingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix="yopa-indexing-test-"))
        subprocess.run(
            ["hugo", "--gc", "--minify", "--cacheDir", str(cls.out / ".hugo-cache"),
             "--destination", str(cls.out)],
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
            ("2025-12-10-agent-factory-scaling-ai-employee-creation", "2025-12-20-building-agent-factory-with-agentcore"),
            ("2026-05-30-personal-aws-cost-guardrails", "2026-03-30-personal-aws-cost-guardrails"),
            ("2026-08-10-claude-code-agent-teams", "2026-08-10-claude-code-cross-session-messaging"),
            ("2026-08-10-deprecating-agent-pingpong", "2026-08-10-claude-code-cross-session-messaging"),
            ("2026-09-21-should-your-service-render-inside-the-ai-host", "2026-09-26-should-your-service-render-inside-the-ai-host"),
            ("2026-09-21-where-should-agent-refusals-live", "2026-09-26-where-should-agent-refusals-live"),
            ("2026-09-23-ecs-deployment-observability", "2026-09-27-ecs-deployment-observability"),
            ("2026-09-24-agent-observability-correctness-not-uptime", "2026-09-28-would-the-evaluator-catch-the-wrong-refund"),
            ("2024-01-19-mastering-chatgpt-for-efficient-software-development", "2024-08-12-mastering-generative-ai-for-efficient-software-development"),
        ):
            with self.subTest(old=old):
                text = self.html(f"blog/{old}.html")
                self.assertIn(f"url=https://www.yopa.page/blog/{new}.html", text)
                self.assertTrue((self.out / f"blog/{new}.html").is_file())
                self.assertNotIn(f"blog/{old}.html", self.sitemap)


if __name__ == "__main__":
    unittest.main()
