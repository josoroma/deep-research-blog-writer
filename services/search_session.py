"""Per-run request budget, stable merge, URL normalization, and atomic artifacts."""

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import HttpUrl, ValidationError

from schemas.requests import ResearchRequest
from schemas.responses import SearchResult
from schemas.search import (
    NormalizationCounts,
    NormalizedResults,
    QueryVariants,
    SearchCall,
    SearchPlan,
)
from schemas.workspace import RunWorkspace
from services.search_provider import SearchProvider, SearchProviderError

DENIED_HOSTS = (
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "pinterest.com",
    "reddit.com",
    "linkedin.com",
    "quora.com",
    "youtube.com",
    "youtu.be",
    "vimeo.com",
)
TRACKING_PARAMETERS = frozenset({"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid"})


def canonicalize_url(url: HttpUrl) -> str:
    parts = urlsplit(str(url))
    meaningful = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path.rstrip("/"), urlencode(meaningful), "")
    )


def normalize_results(results: list[SearchResult], max_urls: int) -> NormalizedResults:
    if max_urls < 1:
        raise ValueError("max_urls must be positive")
    unique: list[SearchResult] = []
    seen: set[str] = set()
    denied = duplicates = 0
    for result in results:
        canonical = HttpUrl(canonicalize_url(result.url))
        host = (canonical.host or "").rstrip(".").lower()
        if any(host == blocked or host.endswith(f".{blocked}") for blocked in DENIED_HOSTS):
            denied += 1
            continue
        identity = str(canonical)
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        unique.append(
            SearchResult.model_validate(
                {**result.model_dump(), "url": identity, "rank": len(unique) + 1}
            )
        )
    kept = unique[:max_urls]
    return NormalizedResults(
        clean_results=kept,
        counts=NormalizationCounts(
            raw=len(results),
            denied=denied,
            duplicates=duplicates,
            capped=len(unique) - len(kept),
            kept=len(kept),
        ),
    )


def _write_json(path: Path, payload: object) -> None:
    """Replace a fixed artifact atomically, without following destination symlinks."""
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class SearchSession:
    """Shared by this run's tools; never shared between run registries."""

    def __init__(
        self, request: ResearchRequest, workspace: RunWorkspace, provider: SearchProvider
    ) -> None:
        provider.preflight(request.per_page)
        self.request = ResearchRequest.model_validate(request)
        self.workspace = workspace
        self.provider = provider
        self._plan: SearchPlan | None = None
        self._pages: dict[tuple[str, int], list[SearchResult]] = {}
        self._attempted: set[tuple[str, int]] = set()
        self._lock = RLock()

    def plan(self, variants: QueryVariants) -> SearchPlan:
        with self._lock:
            if any(
                query.casefold() == self.request.topic.casefold() for query in variants.variants
            ):
                raise ValueError("variants must differ from the topic")
            if (
                self._plan is not None
                and self._attempted
                and self._plan.variants != variants.variants
            ):
                raise ValueError("Cannot change the plan after searching")
            sequence = [(self.request.topic, 1)]
            sequence.extend((query, 1) for query in variants.variants)
            sequence.extend((self.request.topic, page) for page in range(2, self.request.pages + 1))
            plan = SearchPlan(
                topic=self.request.topic,
                variants=variants.variants,
                provider=self.provider.name,
                max_urls=self.request.max_urls,
                calls=[
                    SearchCall(query=query, page=page, per_page=self.request.per_page)
                    for query, page in sequence
                ],
            )
            _write_json(self.workspace.root / "search_plan.json", plan.model_dump())
            self._plan = plan
            return SearchPlan.model_validate(plan)

    @property
    def complete(self) -> bool:
        with self._lock:
            return self._plan is not None and all(
                (call.query, call.page) in self._pages for call in self._plan.calls
            )

    @property
    def results(self) -> list[SearchResult]:
        with self._lock:
            if self._plan is None:
                return []
            return [
                SearchResult.model_validate(result)
                for call in self._plan.calls
                for result in self._pages.get((call.query, call.page), [])
            ]

    def search(self, query: str, page: int) -> list[SearchResult]:
        with self._lock:
            if self._plan is None:
                raise ValueError("Call plan_search before google_search")
            call = next(
                (call for call in self._plan.calls if (call.query, call.page) == (query, page)),
                None,
            )
            if call is None:
                raise ValueError("Search call is outside the planned query/page budget")
            key = (query, page)
            if key not in self._pages:
                if key in self._attempted:
                    raise SearchProviderError(
                        "Planned search previously failed; start a new run to retry"
                    )
                self._attempted.add(key)
                try:
                    results = [
                        SearchResult.model_validate(result) for result in self.provider.search(call)
                    ]
                except ValidationError:
                    raise SearchProviderError(
                        "Provider results violate the search contract"
                    ) from None
                lower = (page - 1) * call.per_page
                ranks = [result.rank for result in results]
                if (
                    len(results) > call.per_page
                    or len(set(ranks)) != len(ranks)
                    or any(
                        result.query != query or not lower < result.rank <= lower + call.per_page
                        for result in results
                    )
                ):
                    raise SearchProviderError("Provider results violate the query/page contract")
                self._pages[key] = sorted(results, key=lambda result: result.rank)
            _write_json(
                self.workspace.root / "search_results.json",
                [result.model_dump() for result in self.results],
            )
            return [SearchResult.model_validate(result) for result in self._pages[key]]

    def normalize(self, max_urls: int) -> NormalizedResults:
        with self._lock:
            if not self.complete:
                raise ValueError("All planned searches must complete before normalization")
            if max_urls > self.request.max_urls:
                raise ValueError("max_urls exceeds the run budget")
            _write_json(
                self.workspace.root / "search_results.json",
                [result.model_dump() for result in self.results],
            )
            normalized = normalize_results(self.results, max_urls)
            _write_json(
                self.workspace.root / "clean_results.json",
                [result.model_dump() for result in normalized.clean_results],
            )
            return normalized
