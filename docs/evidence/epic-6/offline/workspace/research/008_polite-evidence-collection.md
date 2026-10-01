---
source_id: S-08
url: https://fixture.test/canonical?id=7
title: Polite Evidence Collection
author: Alex Researcher
published: '2026-09-01'
fetched: '2026-10-01T17:26:34Z'
word_count: 288
---
# Polite Evidence Collection

Public research depends on clear evidence and careful attribution. A collection service records each source before analysis begins. Readers can inspect the original publication and compare it with the extracted text. The resulting document should preserve meaningful paragraphs while removing repeated navigation links and promotional panels.

Fetching a page involves several independent decisions. The crawler identifies its purpose through a contact address. It reads the published access policy before requesting the article itself. Transient connection problems deserve a bounded retry, while a permanent missing page receives a recorded failure that leaves other sources available.

Rate limits protect both the source server and the research process. Concurrent requests share a single limit across the run. Requests for one host start at a measured interval, and longer published delays take precedence. Other hosts can continue making progress while one host waits for its next allowed request.

Extraction separates the main article from the surrounding interface. A primary parser handles structured documents, then another parser can recover content from different layouts. A final implementation uses semantic article elements when available. Every candidate must contain enough visible words to support useful analysis without inflating its length with URLs.

Metadata makes a source attributable. The title identifies the subject, the author describes responsibility, and the publication date supplies temporal context. Missing optional fields remain absent rather than becoming invented values. Canonical links provide a stable reference, and tracking parameters are removed without deleting meaningful query arguments.

Finally, a repeatable demonstration provides evidence for review. Local fixtures cover ordinary articles, thin pages, missing metadata, and substantial boilerplate. Saved outcomes explain skipped sources and successful extractions. Automated checks verify behavior, and a separate live request confirms that the configured crawler can retrieve a public document.
