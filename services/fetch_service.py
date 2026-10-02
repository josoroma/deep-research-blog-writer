"""Run-owned polite HTTP transport behind the synchronous typed tool interface.

One event loop owns the client, semaphore and host locks. Concurrent tool calls
submit work to that loop, so they share limits without blocking unrelated hosts.
"""

from __future__ import annotations

import asyncio
import random
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from importlib.metadata import version
from typing import Literal, Protocol, Self
from urllib.parse import urljoin, urlsplit

import httpx
from protego import Protego
from pydantic import HttpUrl, ValidationError

from schemas.config import RunSettings
from schemas.content import FetchEvent, FetchResult, RetryEvent, utc_now
from schemas.responses import FetchedPage

TIMEOUT_SECONDS = 15.0
MAX_CONCURRENT = 5
MAX_RETRIES = 3
MAX_REDIRECTS = 5
MAX_HTML_BYTES = 4 * 1024 * 1024
MAX_ROBOTS_BYTES = 512 * 1024
PRODUCT = "DeepResearchBlogWriter"
REDIRECTS = {301, 302, 303, 307, 308}
HTML_TYPES = {"text/html", "application/xhtml+xml"}
TRANSIENT = (httpx.TimeoutException, httpx.NetworkError, TimeoutError)


class Fetcher(Protocol):
    def fetch(self, url: HttpUrl) -> FetchResult: ...


class MissingCrawlerContact(ValueError):
    pass


def crawler_user_agent(settings: RunSettings) -> str:
    if not settings.crawler_contact:
        raise MissingCrawlerContact("Set CRAWLER_CONTACT to a public contact URL or email")
    return f"{PRODUCT}/{version('deep-research-blog-writer')} (+{settings.crawler_contact})"


@dataclass(frozen=True)
class RobotsPolicy:
    rules: Protego | None = None
    deny: bool = False
    unavailable: bool = False

    def allows(self, url: str) -> bool:
        return (
            not self.deny
            and not self.unavailable
            and (self.rules is None or bool(self.rules.can_fetch(url, PRODUCT)))
        )


class ResponseTooLarge(Exception):
    pass


@dataclass
class NetworkBudget:
    """Cumulative network/body time for one page attempt, across redirects."""

    remaining: float


class FetchService:
    def __init__(
        self,
        settings: RunSettings,
        *,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] | None = None,
    ) -> None:
        from services.observability import current_observer

        self.observer = current_observer()
        self.user_agent = crawler_user_agent(settings)
        self._client = client or httpx.AsyncClient(trust_env=False)
        self._clock = clock
        self._sleep = sleep
        self._jitter = jitter or (lambda: random.uniform(0, 0.25))
        self.events: list[FetchEvent] = []
        self.retries: list[RetryEvent] = []
        self.max_active = 0
        self._active = 0
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._slots = asyncio.Semaphore(MAX_CONCURRENT)
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._last_start: dict[str, float] = {}
        self._host_delay: dict[str, float] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self._robots: dict[str, RobotsPolicy] = {}
        self._thread.start()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            asyncio.run_coroutine_threadsafe(self._client.aclose(), self._loop).result()
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join()
            self._loop.close()

    def fetch(self, url: HttpUrl) -> FetchResult:
        if self._closed:
            raise RuntimeError("FetchService is closed")
        return asyncio.run_coroutine_threadsafe(self._fetch(url), self._loop).result()

    async def _start(self, url: str) -> float:
        host = urlsplit(url).hostname or ""
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            previous = self._last_start.get(host)
            if previous is not None:
                remaining = previous + self._host_delay.get(host, 1.0) - self._clock()
                if remaining > 0:
                    await self._sleep(remaining)
            started = self._clock()
            self._last_start[host] = started
            return started

    async def _request(
        self,
        url: str,
        kind: Literal["robots", "page"],
        budget: NetworkBudget | None = None,
    ) -> tuple[int, httpx.Headers, str]:
        if budget is not None and budget.remaining <= 0:
            raise TimeoutError
        started = await self._start(url)
        event = FetchEvent(url=url, host=urlsplit(url).hostname or "", kind=kind, started=started)
        self.events.append(event)
        network_started = self._loop.time()
        timeout = min(TIMEOUT_SECONDS, budget.remaining) if budget else TIMEOUT_SECONDS
        try:
            # HTTPX phase timeouts alone do not bound a slowly streaming body.
            async with asyncio.timeout(timeout):
                async with self._client.stream(
                    "GET",
                    url,
                    headers={"User-Agent": self.user_agent},
                    timeout=TIMEOUT_SECONDS,
                    follow_redirects=False,
                ) as response:
                    event.status = response.status_code
                    content_type = (
                        response.headers.get("content-type", "").split(";")[0].strip().lower()
                    )
                    read_body = response.status_code == 200 and (
                        kind == "robots" or content_type in HTML_TYPES
                    )
                    if not read_body:
                        return response.status_code, response.headers, ""
                    limit = MAX_ROBOTS_BYTES if kind == "robots" else MAX_HTML_BYTES
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise ResponseTooLarge
                        chunks.append(chunk)
                    encoding = response.encoding or "utf-8"
                    return (
                        response.status_code,
                        response.headers,
                        b"".join(chunks).decode(encoding, errors="replace"),
                    )
        except Exception as error:
            event.error = type(error).__name__
            raise
        finally:
            if budget is not None:
                budget.remaining -= self._loop.time() - network_started

    async def _backoff(self, kind: Literal["robots", "page"], attempt: int) -> None:
        delay = float(2 ** (attempt - 1)) + max(0.0, min(0.25, self._jitter()))
        self.retries.append(RetryEvent(kind=kind, attempt=attempt, delay=delay))
        if self.observer is not None:
            self.observer.retry(
                "fetch", "fetch_backoff", kind=kind, attempt=attempt, delay_seconds=delay
            )
        await self._sleep(delay)

    @staticmethod
    def _redirect(url: str, location: str) -> str:
        if not location:
            raise ValueError("Redirect is missing Location")
        return str(HttpUrl(urljoin(url, location)))

    async def _policy(self, url: str) -> RobotsPolicy:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        lock = self._robots_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            if origin in self._robots:
                return self._robots[origin]
            policy = await self._load_robots(f"{origin}/robots.txt")
            if policy.rules is not None:
                delay = policy.rules.crawl_delay(PRODUCT)
                if isinstance(delay, (int, float)) and 0 < delay < float("inf"):
                    host = parts.hostname or ""
                    self._host_delay[host] = max(self._host_delay.get(host, 1.0), float(delay))
            self._robots[origin] = policy
            return policy

    async def _load_robots(self, url: str) -> RobotsPolicy:
        for attempt in range(1, MAX_RETRIES + 2):
            target = url
            try:
                for _ in range(MAX_REDIRECTS + 1):
                    status, headers, body = await self._request(target, "robots")
                    if status in REDIRECTS:
                        target = self._redirect(target, headers.get("location", ""))
                        continue
                    if status == 200:
                        if "html" in headers.get("content-type", "").lower():
                            return RobotsPolicy(unavailable=True)
                        return RobotsPolicy(rules=Protego.parse(body))
                    if status in {404, 410}:
                        return RobotsPolicy()
                    if status in {401, 403}:
                        return RobotsPolicy(deny=True)
                    if status != 429 and status < 500:
                        return RobotsPolicy(unavailable=True)
                    break
                else:
                    return RobotsPolicy(unavailable=True)
            except TRANSIENT:
                pass
            except (ValueError, ResponseTooLarge, httpx.HTTPError):
                return RobotsPolicy(unavailable=True)
            if attempt <= MAX_RETRIES:
                await self._backoff("robots", attempt)
        return RobotsPolicy(unavailable=True)

    async def _fetch(self, url: HttpUrl) -> FetchResult:
        async with self._slots:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
            try:
                return await self._fetch_page(url)
            finally:
                self._active -= 1

    async def _fetch_page(self, url: HttpUrl) -> FetchResult:
        target = str(url)
        status: int | None = None

        def result(
            outcome: Literal["fetched", "unreachable", "robots_disallowed", "unsupported_content"],
            reason: str | None,
            attempts: int,
            body: str | None = None,
        ) -> FetchResult:
            final = HttpUrl(target)
            return FetchResult(
                url=url,
                final_url=final,
                outcome=outcome,
                reason=reason,
                attempts=attempts,
                status=status,
                fetched_at=utc_now(),
                page=FetchedPage(html=body, status=200, final_url=final)
                if body is not None
                else None,
            )

        for attempt in range(1, MAX_RETRIES + 2):
            target = str(url)
            budget = NetworkBudget(TIMEOUT_SECONDS)
            visited: set[str] = set()
            try:
                for _ in range(MAX_REDIRECTS + 1):
                    if target in visited:
                        return result("unreachable", "redirect_loop", attempt)
                    visited.add(target)
                    policy = await self._policy(target)
                    if policy.unavailable:
                        return result("unreachable", "robots_unavailable", attempt)
                    if not policy.allows(target):
                        return result("robots_disallowed", "robots_rule", attempt)
                    status, headers, body = await self._request(target, "page", budget)
                    if status in REDIRECTS:
                        target = self._redirect(target, headers.get("location", ""))
                        continue
                    if status == 429 or status >= 500:
                        break
                    if status != 200:
                        return result("unreachable", f"http_{status}", attempt)
                    content_type = headers.get("content-type", "").split(";")[0].strip().lower()
                    if content_type not in HTML_TYPES:
                        return result("unsupported_content", "non_html_content_type", attempt)
                    return result("fetched", None, attempt, body)
                else:
                    return result("unreachable", "redirect_limit", attempt)
                reason = f"http_{status}"
            except TRANSIENT as error:
                reason = type(error).__name__
                status = None
            except ResponseTooLarge:
                return result("unsupported_content", "response_size_limit", attempt)
            except (ValueError, ValidationError, httpx.HTTPError) as error:
                return result("unreachable", type(error).__name__, attempt)
            if attempt <= MAX_RETRIES:
                await self._backoff("page", attempt)
        return result("unreachable", f"retry_exhausted:{reason}", MAX_RETRIES + 1)
