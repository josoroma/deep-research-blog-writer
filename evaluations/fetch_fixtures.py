"""Packaged original HTML and mock HTTP for reproducible EPIC-5 evidence."""

import asyncio
from collections import Counter
from importlib.resources import files

import httpx


def fixture_html(name: str = "article") -> str:
    return files("evaluations").joinpath("fixtures", "epic5", f"{name}.html").read_text()


class VirtualClock:
    """Deterministic monotonic time; delays are simulated, never wall-clock claims."""

    def __init__(self) -> None:
        self.now = 0.0
        self.delays: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.delays.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)


class FixtureHTTP:
    def __init__(self, *, delay: float = 0.0) -> None:
        self.requests: list[httpx.Request] = []
        self.counts: Counter[str] = Counter()
        self.delay = delay

    async def respond(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        self.counts[url] += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if request.url.path == "/robots.txt":
            host = request.url.host
            rules = "User-agent: *\nDisallow: /blocked\nAllow: /blocked/allowed\n"
            if host == "slow.fixture.test":
                rules += "Crawl-delay: 5\n"
            return httpx.Response(200, text=rules)
        path = request.url.path
        if path == "/redirect":
            return httpx.Response(302, headers={"location": "/article"})
        if path == "/missing":
            return httpx.Response(404)
        if path == "/retry" and self.counts[url] == 1:
            raise httpx.ReadTimeout("Fixture timeout", request=request)
        if path == "/exhaust":
            return httpx.Response(503)
        if path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"PDF")
        fixture = "article"
        if path.lstrip("/") in {"thin", "missing-metadata", "boilerplate-heavy", "non-ascii"}:
            fixture = {
                "/thin": "thin",
                "/missing-metadata": "missing-metadata",
                "/boilerplate-heavy": "boilerplate-heavy",
                "/non-ascii": "non-ascii",
            }[path]
        return httpx.Response(
            200, headers={"content-type": "text/html"}, text=fixture_html(fixture)
        )

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.respond), trust_env=False)
