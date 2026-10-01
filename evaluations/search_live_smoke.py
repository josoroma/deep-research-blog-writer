"""Opt-in, one-request page-2 provider check; no model call and no secret logging."""

from schemas.config import RunSettings
from schemas.search import SearchCall
from services.search_provider import MissingSearchKey, SearchProviderError, create_search_provider


def main(settings: RunSettings | None = None) -> int:
    resolved = settings if settings is not None else RunSettings()
    call = SearchCall(query="2026 agentic AI frameworks", page=2, per_page=10)
    try:
        provider = create_search_provider(resolved)
        results = provider.search(call)
        if not results or any(not 11 <= result.rank <= 20 for result in results):
            raise SearchProviderError("Live page-2 check requires nonempty results ranked 11–20")
    except MissingSearchKey as error:
        print(f"Live search smoke unavailable: {error}")
        return 2
    except SearchProviderError as error:
        print(f"Live search smoke failed: {error}")
        return 1
    print(f"Provider: {provider.name}")
    print(f"Query: {call.query}")
    print("Page: 2; per_page: 10; provider requests: 1; model requests: 0")
    print(f"Result count: {len(results)}")
    print(f"Ranks: {[result.rank for result in results]}")
    print("Live search smoke passed: organic URL/title/snippet/query/rank contracts validated.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
