"""Swappable, typed Google API providers; HTTP belongs in services."""

from collections.abc import Mapping
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, ValidationError

from schemas.config import RunSettings
from schemas.errors import UnavailableError
from schemas.responses import SearchResult
from schemas.search import SearchCall


class SearchProviderError(UnavailableError, ValueError):
    """Credential-safe search failure, without provider bodies or request URLs.

    Kept a ``ValueError`` because the CLI reports provider failures as rejected
    input (exit 2) before any run work starts.
    """

    code = "search_provider_error"


class MissingSearchKey(SearchProviderError):
    """The selected search provider has no configured key."""

    code = "missing_search_key"


class SearchProvider(Protocol):
    @property
    def name(self) -> str: ...
    def preflight(self, per_page: int) -> None: ...
    def search(self, call: SearchCall) -> list[SearchResult]: ...


class OrganicResult(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)

    link: HttpUrl
    title: str
    snippet: str = ""
    position: int = Field(ge=1)


class OrganicResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)

    organic: list[OrganicResult] = Field(default_factory=list)


def _parse_organic(payload: object, call: SearchCall, *, field: str) -> list[SearchResult]:
    if not isinstance(payload, dict) or payload.get("error"):
        raise SearchProviderError("Search provider returned an error or malformed response")
    if field not in payload and "search_information" not in payload:
        raise SearchProviderError("Search provider response is missing organic results")
    try:
        organic = OrganicResponse.model_validate({"organic": payload.get(field, [])}).organic
    except ValidationError:
        raise SearchProviderError(
            "Search provider returned invalid organic-result fields"
        ) from None
    positions: set[int] = set()
    results: list[SearchResult] = []
    offset = (call.page - 1) * call.per_page
    for item in sorted(organic, key=lambda item: item.position):
        if item.position > call.per_page:
            continue
        if item.position in positions:
            raise SearchProviderError("Search provider returned duplicate organic positions")
        positions.add(item.position)
        results.append(
            SearchResult(
                url=item.link,
                title=item.title,
                snippet=item.snippet,
                rank=offset + item.position,
                query=call.query,
            )
        )
    return results


class GoogleAPIProvider:
    """Shared lifecycle; a supplied HTTPX client enables real transport-contract tests."""

    def __init__(
        self, key: SecretStr | None, *, key_name: str, timeout: int, client: httpx.Client | None
    ) -> None:
        if key is None or not key.get_secret_value().strip():
            raise MissingSearchKey(f"Set {key_name} for the selected search provider")
        self._key = key
        self._timeout = timeout
        self._client = client

    def preflight(self, per_page: int) -> None:
        if per_page < 1:
            raise SearchProviderError("per_page must be positive")

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | int] | None = None,
        payload: dict[str, str | int] | None = None,
    ) -> object:
        try:
            if self._client is None:
                # No automatic retries: the run owns its request budget.
                with httpx.Client(timeout=self._timeout, follow_redirects=False) as client:
                    response = client.request(
                        method, url, headers=headers, params=params, json=payload
                    )
            else:
                response = self._client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=payload,
                    timeout=self._timeout,
                    follow_redirects=False,
                )
            if response.status_code != 200:
                raise SearchProviderError(f"Search provider returned HTTP {response.status_code}")
            return response.json()
        except httpx.HTTPError:
            raise SearchProviderError(
                "Search provider request failed (network or timeout)"
            ) from None
        except ValueError as error:
            if isinstance(error, SearchProviderError):
                raise
            raise SearchProviderError("Search provider returned invalid JSON") from None


class SerperProvider(GoogleAPIProvider):
    name = "serper"

    def search(self, call: SearchCall) -> list[SearchResult]:
        self.preflight(call.per_page)
        payload = self._request(
            "POST",
            "https://google.serper.dev/search",
            headers={"X-API-KEY": self._key.get_secret_value()},
            payload={"q": call.query, "page": call.page, "num": call.per_page},
        )
        return _parse_organic(payload, call, field="organic")


class SerpAPIProvider(GoogleAPIProvider):
    name = "serpapi"

    def preflight(self, per_page: int) -> None:
        if per_page != 10:
            raise SearchProviderError(
                "SerpApi Google search requires per_page=10; num is not supported"
            )

    def search(self, call: SearchCall) -> list[SearchResult]:
        self.preflight(call.per_page)
        payload = self._request(
            "GET",
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": call.query,
                "start": (call.page - 1) * call.per_page,
                "api_key": self._key.get_secret_value(),
                "hl": "en",
                "gl": "us",
            },
        )
        return _parse_organic(payload, call, field="organic_results")


def create_search_provider(
    settings: RunSettings, *, client: httpx.Client | None = None
) -> SearchProvider:
    if settings.search_provider == "serper":
        return SerperProvider(
            settings.serper_api_key,
            key_name="SERPER_API_KEY",
            timeout=settings.search_timeout_seconds,
            client=client,
        )
    return SerpAPIProvider(
        settings.serpapi_api_key,
        key_name="SERPAPI_API_KEY",
        timeout=settings.search_timeout_seconds,
        client=client,
    )


class FakeSearchProvider:
    """Deterministic fixtures and a typed record of every requested page."""

    name = "fake"

    def __init__(self, pages: Mapping[tuple[str, int], list[SearchResult]] | None = None) -> None:
        self.pages = dict(pages or {})
        self.calls: list[SearchCall] = []

    def preflight(self, per_page: int) -> None:
        if per_page < 1:
            raise SearchProviderError("per_page must be positive")

    def search(self, call: SearchCall) -> list[SearchResult]:
        self.calls.append(call)
        return [
            SearchResult.model_validate(result)
            for result in self.pages.get((call.query, call.page), [])
        ]
