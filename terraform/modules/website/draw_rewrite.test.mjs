import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "../../..");
const handlerSource = readFileSync(path.join(here, "draw_rewrite.js"), "utf8");
const handler = vm.runInNewContext(`${handlerSource}\nhandler`, {});
const redirects = readFileSync(
  path.join(repo, "tests/fixtures/retired-korean-article-redirects.csv"),
  "utf8",
)
  .trim()
  .split(/\r?\n/)
  .slice(1)
  .map((line) => {
    const [oldPath, englishPath] = line.split(",");
    return { oldPath, englishPath };
  });

function request(uri, rawQueryString) {
  return {
    uri,
    rawQueryString: () => rawQueryString,
  };
}

test("retired English URLs redirect directly to current guides with alias fallbacks", () => {
  for (const [oldSlug, newSlug] of [
    ["2025-12-10-agent-factory-scaling-ai-employee-creation", "2026-08-01-build-a-governed-agent-platform-on-aws"],
    ["2026-05-30-personal-aws-cost-guardrails", "2026-03-30-personal-aws-cost-guardrails"],
    ["2026-08-10-deprecating-agent-pingpong", "2026-08-10-claude-code-cross-session-messaging"],
    ["2026-08-10-claude-code-agent-teams", "2026-08-10-claude-code-cross-session-messaging"],
    ["2026-09-21-should-your-service-render-inside-the-ai-host", "2026-09-26-should-your-service-render-inside-the-ai-host"],
    ["2026-09-21-where-should-agent-refusals-live", "2026-09-26-where-should-agent-refusals-live"],
    ["2026-09-23-ecs-deployment-observability", "2026-09-27-ecs-deployment-observability"],
    ["2026-09-24-agent-observability-correctness-not-uptime", "2026-09-28-would-the-evaluator-catch-the-wrong-refund"],
    ["2024-01-19-mastering-chatgpt-for-efficient-software-development", "2026-08-01-evidence-driven-ai-assisted-software-development"],
  ]) {
    const oldPath = `/blog/${oldSlug}.html`;
    const targetPath = `/blog/${newSlug}.html`;
    const content = readFileSync(path.join(repo, "content/blog", `${newSlug}.en.md`), "utf8");
    assert.ok(content.includes(`  - ${oldPath}\n`), oldPath);
    assert.ok(!content.includes("maintenance_status: archived"), targetPath);
    for (const prefix of ["", "/ko"]) {
      const response = handler({ request: request(`${prefix}${oldPath}`, "tag=a&tag=b&next=%2F") });
      assert.equal(response.statusCode, 301, oldPath);
      assert.equal(response.headers.location.value, `https://www.yopa.page${targetPath}?tag=a&tag=b&next=%2F`);
      const target = request(targetPath, undefined);
      assert.equal(handler({ request: target }), target, targetPath);
    }
  }
});

test("deleted URLs without successors and near matches stay available for origin 404s", () => {
  for (const uri of [
    "/blog/how-to-split-a-string-in-bash.html",
    "/blog/2024-03-07-solving-dynamodb-conditional-update-challenges-with-aws-cdk.html",
    "/blog/2026-08-10-claude-code-agent-teams.html-extra",
  ]) {
    const incoming = request(uri, undefined);
    assert.equal(handler({ request: incoming }), incoming, uri);
  }
});

test("every retired Korean article redirects to its existing English source", () => {
  assert.equal(redirects.length, 76);
  for (const { oldPath, englishPath } of redirects) {
    const slug = path.basename(englishPath, ".html");
    assert.ok(existsSync(path.join(repo, "content/blog", `${slug}.en.md`)));
    const response = handler({ request: request(oldPath, undefined) });
    assert.equal(response.statusCode, 301, oldPath);
    assert.equal(response.statusDescription, "Moved Permanently", oldPath);
    assert.equal(
      response.headers.location.value,
      `https://www.yopa.page${englishPath}`,
      oldPath,
    );
  }
});

test("redirect preserves the raw query string including duplicates and encoding", () => {
  const query = "source=retirement-check&tag=a&tag=b&next=%2Fko%2Fabout.html";
  const response = handler({
    request: request("/ko/blog/2026-09-23-tokenomics-on-aws-attribution-decisions.html", query),
  });
  assert.equal(response.statusCode, 301);
  assert.equal(
    response.headers.location.value,
    `https://www.yopa.page/blog/2026-09-23-tokenomics-on-aws-attribution-decisions.html?${query}`,
  );
});

test("blog section paths redirect to the English article index", () => {
  assert.ok(existsSync(path.join(repo, "content/articles.md")));
  for (const oldPath of ["/ko/blog", "/ko/blog/"]) {
    const response = handler({ request: request(oldPath, undefined) });
    assert.equal(response.statusCode, 301);
    assert.equal(
      response.headers.location.value,
      "https://www.yopa.page/articles.html",
    );
  }
});

test("retired Korean taxonomy, pagination, and archive routes redirect to English", () => {
  for (const [oldPath, englishPath] of [
    ["/ko/articles.html", "/articles.html"],
    ["/ko/explore", "/explore/"],
    ["/ko/explore/", "/explore/"],
    ["/ko/tags", "/tags/index.html"],
    ["/ko/tags/", "/tags/index.html"],
    ["/ko/tags/index.html", "/tags/index.html"],
    ["/ko/tags/aws.html", "/tags/aws.html"],
    ["/ko/tags/security/page/2/", "/tags/security/page/2/"],
    // The English tag index has a single page, so its old page URLs
    // redirect to the first page in one hop.
    ["/ko/tags/page/3/index.html", "/tags/index.html"],
    ["/ko/categories", "/categories/index.html"],
    ["/ko/categories/", "/categories/index.html"],
    ["/ko/categories/aws.html", "/categories/aws.html"],
    ["/ko/categories/aws/page/2/index.html", "/categories/aws/page/2/index.html"],
    ["/ko/page", "/articles.html"],
    ["/ko/page/2/", "/articles.html"],
    ["/ko/page/10/index.html", "/articles.html"],
  ]) {
    const response = handler({ request: request(oldPath, undefined) });
    assert.equal(response.statusCode, 301, oldPath);
    assert.equal(
      response.headers.location.value,
      `https://www.yopa.page${englishPath}`,
      oldPath,
    );
  }
});

test("unrelated Korean routes pass through unchanged", () => {
  for (const uri of [
    "/ko/index.html",
    "/ko/index.xml",
    "/ko/about.html",
    "/ko/expeditions/safe-agent-operations.html",
    "/ko/dispatch/confirmed.html",
    "/ko/blogger/example.html",
    "/ko/tagsmith.html",
    "/ko/pages/example.html",
    "/tags/aws.html",
  ]) {
    const incoming = request(uri, undefined);
    assert.equal(handler({ request: incoming }), incoming);
  }
});

test("directory URLs rewrite to their index pages", () => {
  for (const [uri, expected] of [
    ["/draw", "/draw/index.html"],
    ["/draw/", "/draw/index.html"],
    ["/explore", "/explore/index.html"],
    ["/explore/", "/explore/index.html"],
    // The Korean logo link and the Korean home canonical URL point here.
    ["/ko", "/ko/index.html"],
    ["/ko/", "/ko/index.html"],
    // The sitemap lists Dimly at its url front matter value, /dimly/.
    ["/dimly", "/dimly/index.html"],
    ["/dimly/", "/dimly/index.html"],
  ]) {
    const incoming = request(uri, undefined);
    assert.equal(handler({ request: incoming }), incoming);
    assert.equal(incoming.uri, expected);
  }
});

test("the blog section list and its pages redirect to the article index", () => {
  for (const [uri, query, expected] of [
    ["/blog", undefined, "/articles.html"],
    ["/blog/", undefined, "/articles.html"],
    ["/blog/index.html", undefined, "/articles.html"],
    ["/blog/page", undefined, "/articles.html"],
    ["/blog/page/2/", undefined, "/articles.html"],
    ["/blog/page/27/index.html", "utm_source=x", "/articles.html?utm_source=x"],
  ]) {
    const response = handler({ request: request(uri, query) });
    assert.equal(response.statusCode, 301, uri);
    assert.equal(response.headers.location.value, `https://www.yopa.page${expected}`, uri);
  }
});

test("unused later home pagers redirect directly to the article index", () => {
  for (const page of [2, 3, 28, 29, 100]) {
    for (const suffix of ["", "/", "/index.html"]) {
      const uri = `/page/${page}${suffix}`;
      const response = handler({ request: request(uri, "tag=a&tag=b&next=%2F") });
      assert.equal(response.statusCode, 301, uri);
      assert.equal(response.headers.location.value,
        "https://www.yopa.page/articles.html?tag=a&tag=b&next=%2F", uri);
    }
  }
  for (const uri of ["/page", "/page/1/", "/page/1/index.html", "/page/0/",
    "/page/02/", "/page/two/", "/page/2/feed.xml", "/page/2.html",
    "/page/2/index.html-extra", "/pages/2/", "/tags/python/page/2.html"]) {
    const incoming = request(uri, undefined);
    assert.equal(handler({ request: incoming }), incoming, uri);
  }
});

test("old tag and category index page URLs redirect to the first page", () => {
  for (const [uri, expected] of [
    ["/tags/page", "/tags/index.html"],
    ["/tags/page/2/", "/tags/index.html"],
    ["/tags/page/35/index.html", "/tags/index.html"],
    ["/categories/page/2/index.html", "/categories/index.html"],
    ["/categories/page/14/", "/categories/index.html"],
  ]) {
    const response = handler({ request: request(uri, undefined) });
    assert.equal(response.statusCode, 301, uri);
    assert.equal(response.headers.location.value, `https://www.yopa.page${expected}`, uri);
  }
});

test("articles, the blog feed, and look-alike paths are not redirected", () => {
  for (const uri of [
    "/blog/2026-09-27-ecs-deployment-observability.html",
    "/blog/index.xml",
    "/blog/pages.html",
    "/blog/page-two.html",
    "/blogroll.html",
    "/index.html",
    "/",
    "/kofi.html",
    "/dimlylit.html",
    "/tags/page.html",
    "/tags/aws.html",
    "/tags/github/page/2.html",
    "/categories/aws/page/2.html",
  ]) {
    const incoming = request(uri, undefined);
    assert.equal(handler({ request: incoming }), incoming, uri);
    assert.equal(incoming.uri, uri, uri);
  }
});
