// Korean URLs that no longer have a Korean page. Each entry is
// [prefix, index target]. A request for the bare prefix (with or without a
// trailing slash) goes to the index target; anything below the prefix keeps
// its remaining path and drops the leading "/ko".
var RETIRED_KOREAN_PREFIXES = [
  ['/ko/blog', '/articles.html'],
  ['/ko/tags', '/tags/index.html'],
  ['/ko/categories', '/categories/index.html'],
  ['/ko/page', '/articles.html']
];

// Korean pages that were never built or were retired with the blog.
var RETIRED_KOREAN_PAGES = {
  '/ko/articles.html': '/articles.html',
  '/ko/explore': '/explore/',
  '/ko/explore/': '/explore/'
};

// Exact retired article URLs with an established current successor. Matching
// Hugo aliases remain an origin fallback; unrelated deleted URLs stay 404.
var RETIRED_ARTICLES = {
  '/blog/2025-12-10-agent-factory-scaling-ai-employee-creation.html': '/blog/2026-08-01-build-a-governed-agent-platform-on-aws.html',
  '/blog/2026-05-30-personal-aws-cost-guardrails.html': '/blog/2026-03-30-personal-aws-cost-guardrails.html',
  '/blog/2026-08-10-deprecating-agent-pingpong.html': '/blog/2026-08-10-claude-code-cross-session-messaging.html',
  '/blog/2026-08-10-claude-code-agent-teams.html': '/blog/2026-08-10-claude-code-cross-session-messaging.html',
  '/blog/2026-09-21-should-your-service-render-inside-the-ai-host.html': '/blog/2026-09-26-should-your-service-render-inside-the-ai-host.html',
  '/blog/2026-09-21-where-should-agent-refusals-live.html': '/blog/2026-09-26-where-should-agent-refusals-live.html',
  '/blog/2026-09-23-ecs-deployment-observability.html': '/blog/2026-09-27-ecs-deployment-observability.html',
  '/blog/2026-09-24-agent-observability-correctness-not-uptime.html': '/blog/2026-09-28-would-the-evaluator-catch-the-wrong-refund.html',
  '/blog/2024-01-19-mastering-chatgpt-for-efficient-software-development.html': '/blog/2026-08-01-evidence-driven-ai-assisted-software-development.html'
};

function englishTarget(uri) {
  if (RETIRED_KOREAN_PAGES[uri]) {
    return RETIRED_KOREAN_PAGES[uri];
  }
  for (var i = 0; i < RETIRED_KOREAN_PREFIXES.length; i++) {
    var prefix = RETIRED_KOREAN_PREFIXES[i][0];
    if (uri === prefix || uri === prefix + '/') {
      return RETIRED_KOREAN_PREFIXES[i][1];
    }
    if (uri.indexOf(prefix + '/') === 0) {
      // Paginated Korean home pages have no English equivalent path.
      return prefix === '/ko/page' ? '/articles.html' : uri.substring('/ko'.length);
    }
  }
  return undefined;
}

// List URLs that only duplicate another page, so they redirect to it
// instead of competing with it in search results:
// - the /blog/ section list and its pages copy /articles.html, the full
//   article index (article URLs and the /blog/index.xml feed are untouched);
// - later home pagers are unused article lists with no navigation to them;
// - /tags/page/N/ and /categories/page/N/ were copies of the first page of
//   the tag and category indexes and are no longer built.
function duplicateListTarget(uri) {
  var homePager = /^\/page\/([1-9][0-9]*)(?:\/(?:index\.html)?)?$/.exec(uri);
  if (homePager && Number(homePager[1]) > 1) {
    return '/articles.html';
  }
  if (uri === '/blog' || uri === '/blog/' || uri === '/blog/index.html' ||
      uri === '/blog/page' || uri.indexOf('/blog/page/') === 0) {
    return '/articles.html';
  }
  if (uri === '/tags/page' || uri.indexOf('/tags/page/') === 0) {
    return '/tags/index.html';
  }
  if (uri === '/categories/page' || uri.indexOf('/categories/page/') === 0) {
    return '/categories/index.html';
  }
  return undefined;
}

// Directory URLs that CloudFront must serve from their index.html. Only the
// site root has a default root object, so without this a request for /ko/
// or /dimly/ returns 404.
var DIRECTORY_INDEXES = {
  '/draw': '/draw/index.html',
  '/draw/': '/draw/index.html',
  '/explore': '/explore/index.html',
  '/explore/': '/explore/index.html',
  '/dimly': '/dimly/index.html',
  '/dimly/': '/dimly/index.html',
  '/ko': '/ko/index.html',
  '/ko/': '/ko/index.html'
};

function handler(event) {
  var request = event.request;
  var uri = request.uri;

  var target = englishTarget(uri);
  // Resolve in one hop, including Korean URLs that map to a duplicate list.
  var listTarget = duplicateListTarget(target === undefined ? uri : target);
  if (listTarget !== undefined) {
    target = listTarget;
  }
  // Resolve Korean retirement and article renames in the same response.
  var articlePath = target === undefined ? uri : target;
  if (RETIRED_ARTICLES.hasOwnProperty(articlePath)) {
    target = RETIRED_ARTICLES[articlePath];
  }
  if (target !== undefined) {
    var rawQueryString = request.rawQueryString();
    var querySuffix = rawQueryString === undefined ? '' : '?' + rawQueryString;
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        location: {
          value: 'https://www.yopa.page' + target + querySuffix
        }
      }
    };
  }

  if (DIRECTORY_INDEXES.hasOwnProperty(uri)) {
    request.uri = DIRECTORY_INDEXES[uri];
  }

  return request;
}
