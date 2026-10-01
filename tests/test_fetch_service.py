"""US-5.1/5.2: real transport policy with mocked HTTP and explicit virtual time."""

import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from pydantic import HttpUrl, ValidationError

from evaluations.fetch_fixtures import FixtureHTTP, VirtualClock, fixture_html
from schemas.config import RunSettings
from schemas.content import FetchResult
from services.fetch_service import FetchService, MissingCrawlerContact, crawler_user_agent
from tools.registry import create_tool_registry


def settings() -> RunSettings:
    return RunSettings(_env_file=None, crawler_contact="https://example.org/contact")


def test_contact_preflight_and_header_validation() -> None:
    with pytest.raises(MissingCrawlerContact):
        crawler_user_agent(RunSettings(_env_file=None))
    for contact in ("javascript:alert(1)", "https://example.com\r\nBad: header", "invalid", "a@"):
        with pytest.raises(ValidationError):
            RunSettings(_env_file=None, crawler_contact=contact)
    email = RunSettings(_env_file=None, crawler_contact="crawler@example.org")
    assert crawler_user_agent(email) == "DeepResearchBlogWriter/0.1.0 (+mailto:crawler@example.org)"


def test_registered_fetch_redirect_headers_timeout_and_robots_cache() -> None:
    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as service:
        registry = create_tool_registry(fetcher=service)
        result = registry["fetch_url"].invoke({"url": "https://fixture.test/redirect"})
        assert isinstance(result, FetchResult) and result.page is not None
        assert result.page.html == fixture_html()
        assert str(result.final_url) == "https://fixture.test/article"
        assert result.status == 200
        service.fetch(HttpUrl("https://fixture.test/another"))
        starts = [event.started for event in service.events]
        assert all(right - left >= 1 for left, right in zip(starts, starts[1:], strict=False))
    assert transport.counts["https://fixture.test/robots.txt"] == 1
    assert all(
        request.headers["user-agent"] == crawler_user_agent(settings())
        for request in transport.requests
    )
    assert all(
        set(request.extensions["timeout"].values()) == {15.0} for request in transport.requests
    )
    assert service._thread.is_alive() is False
    service.close()
    with pytest.raises(RuntimeError, match="closed"):
        service.fetch(HttpUrl("https://fixture.test/a"))


@pytest.mark.parametrize("failure", ["timeout", "connection", 429, 500, 503])
@pytest.mark.parametrize("recover", [True, False])
def test_retry_classes_have_four_attempt_bound_and_backoff(
    failure: str | int, recover: bool
) -> None:
    page_requests = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal page_requests
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        page_requests += 1
        if recover and page_requests > 1:
            return httpx.Response(200, headers={"content-type": "text/html"}, text=fixture_html())
        if failure == "timeout":
            raise httpx.ReadTimeout("fixture", request=request)
        if failure == "connection":
            raise httpx.ConnectError("fixture", request=request)
        assert isinstance(failure, int)
        return httpx.Response(failure)

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.1,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/retry"))
        assert result.outcome == ("fetched" if recover else "unreachable")
        assert result.attempts == page_requests == (2 if recover else 4)
        assert [event.delay for event in service.retries] == ([1.1] if recover else [1.1, 2.1, 4.1])
        if not recover:
            assert result.reason and "retry_exhausted" in result.reason


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 418])
def test_permanent_http_failure_is_not_retried(status: int) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if request.url.path == "/robots.txt" else status)

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/missing"))
        assert result.outcome == "unreachable"
        assert result.reason == f"http_{status}"
        assert result.attempts == 1 and not service.retries


def test_robots_disallow_specific_allow_wildcard_and_fractional_delay() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text=(
                    "User-agent: *\nDisallow: /private*\nAllow: /private/public\nCrawl-delay: 1.5\n"
                ),
            )
        return httpx.Response(200, headers={"content-type": "text/html"}, text=fixture_html())

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
    ) as service:
        assert (
            service.fetch(HttpUrl("https://fixture.test/private/x")).outcome == "robots_disallowed"
        )
        assert service.fetch(HttpUrl("https://fixture.test/private/public")).outcome == "fetched"
        assert service.fetch(HttpUrl("https://fixture.test/article")).outcome == "fetched"
        assert [event.started for event in service.events] == [0.0, 1.5, 3.0]
    assert all(request.url.path != "/private/x" for request in requests)


@pytest.mark.parametrize(
    "status,outcome,attempts",
    [
        (404, "fetched", 1),
        (410, "fetched", 1),
        (401, "robots_disallowed", 1),
        (403, "robots_disallowed", 1),
        (503, "unreachable", 4),
        (429, "unreachable", 4),
        (400, "unreachable", 1),
    ],
)
def test_robots_status_policy(status: int, outcome: str, attempts: int) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(status)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=fixture_html())

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.0,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/a"))
        assert result.outcome == outcome
        assert len([e for e in service.events if e.kind == "robots"]) == attempts
        assert len([e for e in service.events if e.kind == "page"]) == (outcome == "fetched")


def test_redirect_destination_has_its_own_robots_gate() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /blocked")
        return httpx.Response(302, headers={"location": "https://other.fixture.test/blocked"})

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/redirect"))
        assert result.outcome == "robots_disallowed"
        assert str(result.final_url) == "https://other.fixture.test/blocked"
        assert [e.kind for e in service.events] == ["robots", "page", "robots"]


@pytest.mark.parametrize(
    "location,reason",
    [
        ("/loop", "redirect_loop"),
        ("", "ValueError"),
        ("file:///tmp/private", "ValidationError"),
    ],
)
def test_bad_redirects_are_permanent(location: str, reason: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": location})

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/loop"))
        assert result.reason == reason and not service.retries


@pytest.mark.parametrize("content_type", ["application/pdf", "text/plain", "image/png", ""])
def test_non_html_has_no_page(content_type: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": content_type}, content=b"unsupported")

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/binary"))
        assert result.outcome == "unsupported_content" and result.page is None


def test_wall_timeout_abandons_slow_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.fetch_service.TIMEOUT_SECONDS", 0.01)

    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        await asyncio.sleep(1)
        return httpx.Response(200)

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.0,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/slow"))
        assert result.outcome == "unreachable" and result.attempts == 4
        assert result.reason == "retry_exhausted:TimeoutError"


def test_thirty_hosts_share_five_slots_and_same_host_robots_cache() -> None:
    transport, clock = FixtureHTTP(delay=0.005), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as service:
        with ThreadPoolExecutor(max_workers=30) as pool:
            results = list(
                pool.map(
                    service.fetch, [HttpUrl(f"https://h{i}.fixture.test/a") for i in range(30)]
                )
            )
        assert all(result.outcome == "fetched" for result in results)
        assert service.max_active == 5
        with ThreadPoolExecutor(max_workers=10) as pool:
            list(
                pool.map(
                    service.fetch, [HttpUrl(f"https://slow.fixture.test/a{i}") for i in range(10)]
                )
            )
        starts = [e.started for e in service.events if e.host == "slow.fixture.test"]
        assert all(right - left >= 5 for left, right in zip(starts, starts[1:], strict=False))
        assert transport.counts["https://slow.fixture.test/robots.txt"] == 1


def test_response_size_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.fetch_service.MAX_HTML_BYTES", 10)
    transport, clock = FixtureHTTP(), VirtualClock()
    with FetchService(
        settings(), client=transport.client(), clock=clock, sleep=clock.sleep
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/article"))
        assert result.outcome == "unsupported_content" and result.reason == "response_size_limit"
        assert not service.retries


@pytest.mark.parametrize(
    "mode", ["html", "size", "invalid_redirect", "limit", "connection", "recovery"]
)
def test_unavailable_robots_never_permits_page_and_recovery_is_cached(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setattr("services.fetch_service.MAX_ROBOTS_BYTES", 50)
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if request.url.path != "/robots.txt":
            if mode != "recovery":
                return httpx.Response(302, headers={"location": f"/redirect-{calls}"})
            return httpx.Response(200, headers={"content-type": "text/html"}, text=fixture_html())
        if mode == "html":
            return httpx.Response(200, headers={"content-type": "text/html"}, text="challenge")
        if mode == "size":
            return httpx.Response(200, text="x" * 51)
        if mode == "invalid_redirect":
            return httpx.Response(302)
        if mode == "limit":
            return httpx.Response(302, headers={"location": f"/redirect-{calls}"})
        if mode == "connection" or calls == 1:
            raise httpx.ConnectError("fixture", request=request)
        return httpx.Response(404)

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.0,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/article"))
        assert result.outcome == ("fetched" if mode == "recovery" else "unreachable")
        if mode != "recovery":
            assert all(event.kind == "robots" for event in service.events)
        before = len([event for event in service.events if event.kind == "robots"])
        service.fetch(HttpUrl("https://fixture.test/another"))
        assert len([event for event in service.events if event.kind == "robots"]) == before


def test_page_redirect_limit_is_bounded() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        count = int(request.url.path.removeprefix("/r"))
        return httpx.Response(302, headers={"location": f"/r{count + 1}"})

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/r0"))
        assert result.reason == "redirect_limit" and not service.retries
        assert len([event for event in service.events if event.kind == "page"]) == 6


def test_timeout_includes_slow_stream_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.fetch_service.TIMEOUT_SECONDS", 0.01)

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b"<html>"
            await asyncio.sleep(1)
            yield b"</html>"

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "text/html"}, stream=SlowStream())

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.0,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/stream"))
        assert result.reason == "retry_exhausted:TimeoutError" and result.attempts == 4


def test_redirects_share_one_attempt_network_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.fetch_service.TIMEOUT_SECONDS", 0.02)

    async def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        await asyncio.sleep(0.012)
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "/article"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text=fixture_html())

    clock = VirtualClock()
    with FetchService(
        settings(),
        client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        clock=clock,
        sleep=clock.sleep,
        jitter=lambda: 0.0,
    ) as service:
        result = service.fetch(HttpUrl("https://fixture.test/redirect"))
        assert result.reason == "retry_exhausted:TimeoutError" and result.attempts == 4
