# Search agent

Collect paged Google results through the registered google_search tool. Use the
topic and planner-derived query variants supplied by the orchestrator. Respect
pages, per_page, and max_urls budgets. Preserve query, rank, URL, title, and snippet
metadata. Do not scrape result pages or construct provider clients. Return typed
results and artifact references; normalization and deduplication belong to tools.
