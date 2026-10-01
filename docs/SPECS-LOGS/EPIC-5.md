# EPIC-5: Fetch and Extraction

Date: 2026-10-01

Status: Completed and verified. This plan was written before implementation; successful commands and PM evidence are in [EPIC-5-RUNBOOK.md](EPIC-5-RUNBOOK.md).

## Objective

Implement US-5.1–US-5.3 from [SPECS.md](../../SPECS.md#epic-5-fetch-and-extraction), using the completed EPIC-4 ranked clean URLs. Fetch permitted HTML politely, recover only from transient failures, extract attributable Markdown through the specified parser chain, and record a typed outcome for every URL without aborting on an individual failure.

Immutable `research/NNN_<slug>.md` files, front-matter, corpus indexing, and the production `collect_source` implementation remain in EPIC-6. This milestone saves inspectable extraction artifacts and typed progress without claiming that those corpus files or a production blog exist.

## Implementation sequence

1. **Contracts and setup.** Preserve the existing `FetchedPage` and `Source` hand-offs. Add typed fetch/extraction results and parser-attempt metadata so failures do not become empty successes. Add locked dependencies for trafilatura, readability-lxml, beautifulsoup4, Markdown conversion, and robots parsing. Configure crawler contact and extractor strategy through `RunSettings`; reject missing contact before live HTTP. Keep API credentials out of fetch headers and saved artifacts.
2. **US-5.1: HTTP fetching.** Replace `fetch_url` with an injected fetch service behind the typed registry. Use a 15-second timeout, including a cumulative wall-clock network/body budget across page redirects and a separate bound for robots requests. Retry only timeouts, connection errors, HTTP 429 and 5xx, at most three retries after the initial attempt, with 1/2/4-second exponential backoff and jitter. Follow bounded redirects manually so each destination passes its own robots check and host limiter. Return actual HTML/status/final URL on success. Record permanent failures without retry and skip non-HTML before extraction. Bound response size and redirect count explicitly.
3. **US-5.1: Robots and identity.** Fetch/cache robots rules per origin, including concurrent requests for the same origin. Identify every page/robots/redirect/retry request with `DeepResearchBlogWriter/<version> (+<configured-contact>)`. Missing robots (404/410) allow access; 401/403 deny access; transient/unavailable robots fail closed after the bounded retry budget. Use a parser supporting specific rules, wildcard/Allow precedence, and fractional Crawl-delay. Record `robots_disallowed`, `unsupported_content`, and `unreachable` with reasons.
4. **US-5.2: Shared politeness controls.** Use one run-owned event loop/client and semaphore, with at most five URL fetches active even when registered tools are invoked concurrently. Rate-limit all HTTP request starts per hostname to at least one second; apply a longer robots Crawl-delay to subsequent requests. Use monotonic time and injected timing dependencies for deterministic offline tests. Cache robots without duplicate simultaneous downloads; avoid holding one host's wait lock across unrelated hosts.
5. **US-5.3: Extraction.** Define an extractor interface returning validated candidate content/metadata. Default to trafilatura → readability-lxml → beautifulsoup4, trying the next parser after errors, empty content, or fewer than 200 words. Strip navigation, footer, scripts and other page chrome, convert to Markdown, preserve title/author/publication/canonical URL, and allow absent optional metadata. Return `Source` inside a typed successful extraction result. Record all-thin results as `too_thin`, all-parser errors as `extraction_failed`, and never create source files for failures. Select alternate parser implementations through configuration/injection without agent edits.
6. **Run integration and demo.** Register actual `fetch_url`/`extract_markdown` as internal tools, keeping PD-005 agent assignments. Retain only clearly labelled future-epic stubs. Add `--fetch-only --workspace <existing-search-run>` to consume validated request/clean artifacts, execute registered tools concurrently, and save `fetch_outcomes.json`, `extraction_results.json`, and `fetch_state.json`. Persist outcomes in clean-rank order; raw HTML stays within tools/services. Add `make demo-epic-5` with mocked HTTP, actual extraction libraries, fixtures, and explicit virtual-time evidence for retries/throttling. Add a bounded opt-in live fetch smoke when a valid contact is configured.
7. **Verification and delivery.** Test redirect/robots handling, 15-second timeouts, every retry class and permanent failures, content skipping, UA headers, cached robots, five-way concurrency, one-second spacing, longer Crawl-delay, parser fallback, 200-word boundary, metadata/canonical URLs, configuration swaps, malformed contracts, and failure continuation. Add article, missing-metadata, boilerplate-heavy, and thin HTML fixtures. Run locked setup, strict quality/coverage checks, hooks, prior demos, the new demo, wheel/sdist build, installed-wheel checks, and committed fresh-checkout verification. Record exact successful command outputs, PM artifact snapshots, coverage and source hashes. Update only verified EPIC-5 story/task statuses and commit with hooks active.

## Acceptance matrix

| Story | Evidence |
| --- | --- |
| US-5.1 | Typed registered fetch tool; redirect final URL; 15-second timeout; recovery and max-three retries; 404 no retry; robots prevents page request; PDF never extracted; identifying UA; failure outcomes and continuation |
| US-5.2 | Thirty-host concurrency probe shows at most five active fetches; host request starts at least one second apart; longer Crawl-delay respected, including requests after redirects/retries |
| US-5.3 | Real HTML fixtures produce clean Markdown and metadata; missing metadata stays null; ordered fallback on empty/thin/error; all-thin pages recorded with no source file; configurable/injected extractor swap |

## Completion checklist

- [x] Contracts, dependencies, crawler configuration, and ADR documented.
- [x] US-5.1 implemented and verified.
- [x] US-5.2 implemented and verified.
- [x] US-5.3 implemented and verified.
- [x] Runnable fetch-only workflow and offline PM demo pass.
- [x] Strict gates/hooks, prior demos, installed wheel, and fresh checkout pass.
- [x] Actual live check outcome recorded separately from offline evidence.
- [x] Runbook, command transcripts, artifact snapshots, coverage and source hashes saved.
- [x] Implementation and final evidence committed.

## Technical references

Use primary documentation and the installed locked APIs: [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/), [RFC 9309 robots rules](https://www.rfc-editor.org/rfc/rfc9309.html), [trafilatura core functions](https://trafilatura.readthedocs.io/en/latest/corefunctions.html), [readability-lxml](https://github.com/buriy/python-readability), [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), [markdownify](https://github.com/matthewwithanm/python-markdownify), and [Protego](https://github.com/scrapy/protego).
