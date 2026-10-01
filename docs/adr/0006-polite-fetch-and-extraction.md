# ADR 0006: Run-owned polite fetching and replaceable extraction

Date: 2026-10-01

Status: Accepted

## Context

US-5.1–US-5.3 require bounded fetching, robots compliance, a shared limit of five fetches, per-host spacing, and trafilatura → readability-lxml → beautifulsoup4 extraction. Agent code must stay independent of HTTP/parsers. A separate client per tool call would lose shared limits and robots caching.

## Decision

Bind a synchronous `fetch_url` tool to one run-owned `FetchService`. A background event loop owns one HTTPX asynchronous client, a semaphore of five, host locks, and cached robots policies. Concurrent tool callers submit to the same loop. Close the service at the end of the run. No client, contact configuration, or credentials enter agent/checkpoint state.

Each page attempt has a cumulative 15-second network/body budget across redirects, enforced with a wall-clock timeout and HTTPX phase timeouts. Robots requests each have their own 15-second bound. Robots checks and deliberate rate-limit/backoff waits add to total URL processing time. Retry only timeout/network connection errors, 429, and 5xx: initial attempt plus at most three retries, with 1/2/4 seconds and up to 0.25 seconds of jitter. Permanent HTTP errors and malformed redirects are terminal. Limit redirects to five, HTML to 4 MiB, and robots to 512 KiB. Stream decoded bytes so size checks also cover decompressed responses.

Manually follow page redirects and check every destination's robots policy before requesting its page. Cache robots per origin for the run; all requests share the hostname limiter across ports/schemes. Robots 404/410 permits access, 401/403 denies access, and unavailable robots fails closed after applicable retries. Protego implements Allow/Disallow precedence, wildcards, and fractional Crawl-delay. Missing contact fails before HTTP. Every request carries `DeepResearchBlogWriter/<installed-version> (+<configured-contact>)`.

Implement an `Extractor` protocol with the required three libraries. Try the next candidate after errors, empty content, or fewer than 200 visible body words. Remove page chrome and trafilatura-generated metadata front-matter before counting words. Preserve metadata separately, resolve/normalize an explicit canonical URL, and retain null optional metadata. Publication dates require explicit meta tags, Article JSON-LD, or marked publication time elements; parser date guesses are not treated as publication dates. Configure `EXTRACTOR_STRATEGY` as `fallback`, `trafilatura`, `readability`, or `beautifulsoup`; callers can inject another implementation through `ExtractionService` without editing agents.

Expose `--fetch-only --workspace <EPIC-4 run>` to process validated clean URLs through the registered internal tools. Save ordered fetch metadata, extraction previews, and typed state. Raw HTML remains an internal hand-off. Existing agent tool assignments remain intact; production `collect_source`, immutable source files, and indexing belong to EPIC-6. The skeleton's collection stub is explicitly labelled and uses only private fake helpers.

## Consequences

All concurrent fetch callers within a service share limits and cached rules. Multiple independent processes/services have independent limits. Fetch-only re-execution makes new requests and replaces milestone JSON artifacts; it is not durable resume or an immutable corpus. HTML requiring browser JavaScript, PDFs, OCR, and semantic metadata verification are outside this epic. Metadata inferred by a parser may need editorial verification; optional fields are never supplied with application-invented defaults.

Offline tests use mock HTTP and virtual monotonic time; a separate live smoke verifies real HTTP/robots/User-Agent and extraction. The PM demo labels virtual timing and forced fallback candidates explicitly. Coverage/gates do not depend on public network availability.

## References

- [HTTPX phase timeouts](https://www.python-httpx.org/advanced/timeouts/) and [Python asyncio timeout](https://docs.python.org/3.12/library/asyncio-task.html#asyncio.timeout)
- [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html) and [Protego](https://github.com/scrapy/protego)
- [trafilatura API](https://trafilatura.readthedocs.io/en/latest/corefunctions.html), [readability-lxml](https://github.com/buriy/python-readability), [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), [markdownify](https://github.com/matthewwithanm/python-markdownify)
