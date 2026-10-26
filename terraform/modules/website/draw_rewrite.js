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
// - /tags/page/N/ and /categories/page/N/ were copies of the first page of
//   the tag and category indexes and are no longer built.
function duplicateListTarget(uri) {
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
