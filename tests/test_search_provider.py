"""Transport-contract tests use HTTPX's mock transport, never provider sockets."""

import json
from typing import Literal

import httpx
import pytest
from pydantic import SecretStr

from schemas.config import RunSettings
from schemas.search import SearchCall
from services.search_provider import (
    FakeSearchProvider,
    MissingSearchKey,
    SearchProviderError,
    create_search_provider,
)

KEY = "test-key-never-log"
CALL = SearchCall(query="agent frameworks", page=2, per_page=10)


def settings(provider: Literal["serper", "serpapi"] = "serper") -> RunSettings:
    return RunSettings(
        _env_file=None,
        search_provider=provider,
        serper_api_key=SecretStr(KEY),
        serpapi_api_key=SecretStr(KEY),
        search_timeout_seconds=7,
    )


def organic() -> list[dict[str, object]]:
    return [
        {
            "position": index,
            "link": f"https://example.com/{index}",
            "title": f"Title {index}",
            "snippet": f"Snippet {index}",
            "unrelated_provider_field": "ignored",
        }
        for index in range(10, 0, -1)
    ]


@pytest.mark.parametrize("name,field", [("serper", "organic"), ("serpapi", "organic_results")])
def test_provider_authentication_pagination_mapping_and_swapping(
    name: Literal["serper", "serpapi"], field: str
) -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.extensions["timeout"] == {"connect": 7, "read": 7, "write": 7, "pool": 7}
        if name == "serper":
            assert request.method == "POST"
            assert str(request.url) == "https://google.serper.dev/search"
            assert request.headers["X-API-KEY"] == KEY
            assert json.loads(request.content) == {"q": CALL.query, "page": 2, "num": 10}
        else:
            assert request.method == "GET"
            assert request.url.host == "serpapi.com"
            assert request.url.path == "/search.json"
            assert dict(request.url.params) == {
                "q": CALL.query,
                "start": "10",
                "api_key": KEY,
                "engine": "google",
                "hl": "en",
                "gl": "us",
            }
        return httpx.Response(200, json={field: organic(), "ads": [{"link": "https://ad.test"}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        results = create_search_provider(settings(name), client=client).search(CALL)
    assert len(requests) == 1
    assert [result.rank for result in results] == list(range(11, 21))
    assert all(result.query == CALL.query for result in results)
    assert results[0].title == "Title 1"
    assert results[0].snippet == "Snippet 1"
    assert str(results[0].url) == "https://example.com/1"


@pytest.mark.parametrize(
    "provider,key_name", [("serper", "SERPER_API_KEY"), ("serpapi", "SERPAPI_API_KEY")]
)
def test_missing_selected_key_is_named(
    provider: Literal["serper", "serpapi"], key_name: str
) -> None:
    configured = RunSettings(_env_file=None, search_provider=provider)
    with pytest.raises(MissingSearchKey, match=key_name):
        create_search_provider(configured)


def test_blank_key_is_missing_and_other_provider_key_is_not_a_fallback() -> None:
    configured = RunSettings(
        _env_file=None,
        search_provider="serper",
        serper_api_key=SecretStr("   "),
        serpapi_api_key=SecretStr(KEY),
    )
    with pytest.raises(MissingSearchKey, match="SERPER_API_KEY"):
        create_search_provider(configured)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"error": KEY},
        {"organic": None},
        {"organic": [{"position": 1, "link": "not a URL", "title": KEY}]},
        {"organic": [organic()[0], organic()[0]]},
    ],
)
def test_malformed_provider_fields_fail_without_exposing_payload(payload: object) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(SearchProviderError) as caught:
            create_search_provider(settings(), client=client).search(CALL)
    assert KEY not in str(caught.value)


@pytest.mark.parametrize("status", [301, 401, 403, 429, 500])
def test_http_failure_does_not_retry_follow_redirects_or_expose_body(status: int) -> None:
    calls = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, text=KEY, headers={"Location": "https://google.com/"})

    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=True) as client:
        with pytest.raises(SearchProviderError, match=f"HTTP {status}") as caught:
            create_search_provider(settings(), client=client).search(CALL)
    assert len(calls) == 1
    assert KEY not in str(caught.value)


def test_network_timeout_is_redacted() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"unsafe request {KEY}", request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SearchProviderError, match="network or timeout") as caught:
            create_search_provider(settings(), client=client).search(CALL)
    assert KEY not in str(caught.value)


def test_invalid_json_and_empty_results() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=KEY))
    ) as client:
        with pytest.raises(SearchProviderError, match="invalid JSON"):
            create_search_provider(settings(), client=client).search(CALL)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"organic": []}))
    ) as client:
        assert create_search_provider(settings(), client=client).search(CALL) == []


def test_sparse_positions_missing_snippet_and_page_size_are_preserved() -> None:
    rows = [
        {"link": "https://example.com", "title": "Source", "position": rank} for rank in (3, 1, 11)
    ]
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"organic": rows}))
    ) as client:
        results = create_search_provider(settings(), client=client).search(CALL)
    assert [result.rank for result in results] == [11, 13]
    assert all(result.snippet == "" for result in results)
    with pytest.raises(SearchProviderError, match="per_page=10"):
        create_search_provider(settings("serpapi")).preflight(5)
    for provider in (create_search_provider(settings()), FakeSearchProvider()):
        with pytest.raises(SearchProviderError, match="positive"):
            provider.preflight(0)


def test_provider_owned_http_client_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    real_client = httpx.Client
    created = []

    def factory(**kwargs: object) -> httpx.Client:
        client = real_client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"organic": organic()})
            )
        )
        created.append(client)
        return client

    monkeypatch.setattr(httpx, "Client", factory)
    results = create_search_provider(settings()).search(CALL)
    assert len(results) == 10
    assert created[0].is_closed
