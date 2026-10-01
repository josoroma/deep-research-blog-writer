"""Exercise smoke reporting offline; the marked test opts in to actual HTTP."""

import json
from pathlib import Path

import pytest
from pydantic import HttpUrl

from evaluations import fetch_live_smoke
from evaluations.fetch_fixtures import FixtureHTTP, VirtualClock
from schemas.config import RunSettings
from services.fetch_service import FetchService


def bind_mock_service(monkeypatch: pytest.MonkeyPatch) -> RunSettings:
    settings = RunSettings(_env_file=None, crawler_contact="https://example.org/contact")

    def create(settings: RunSettings) -> FetchService:
        transport, clock = FixtureHTTP(), VirtualClock()
        return FetchService(settings, client=transport.client(), clock=clock, sleep=clock.sleep)

    monkeypatch.setattr(fetch_live_smoke, "FetchService", create)
    return settings


def test_smoke_extracts_through_registered_tools_without_dumping_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = fetch_live_smoke.run_smoke(
        bind_mock_service(monkeypatch), HttpUrl("https://fixture.test/article")
    )
    assert evidence["passed"] is True
    assert "body_markdown" not in json.dumps(evidence)


@pytest.mark.parametrize("path", ["pdf", "thin", "missing", "blocked"])
def test_smoke_reports_unsuccessful_outcome(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    evidence = fetch_live_smoke.run_smoke(
        bind_mock_service(monkeypatch), HttpUrl(f"https://fixture.test/{path}")
    )
    assert evidence["passed"] is False


def test_smoke_main_writes_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = bind_mock_service(monkeypatch)
    monkeypatch.setattr(fetch_live_smoke, "RunSettings", lambda: settings)
    output = tmp_path / "live.json"
    monkeypatch.setattr(
        "sys.argv", ["smoke", "--url", "https://fixture.test/article", "--output", str(output)]
    )
    assert fetch_live_smoke.main() == 0
    assert json.loads(output.read_text())["passed"] is True


def test_smoke_main_missing_contact_returns_two(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = RunSettings(_env_file=None)
    monkeypatch.setattr(fetch_live_smoke, "RunSettings", lambda: settings)
    monkeypatch.setattr("sys.argv", ["smoke"])
    assert fetch_live_smoke.main() == 2


@pytest.mark.live
def test_live_public_fetch_and_extraction() -> None:
    settings = RunSettings()
    if settings.crawler_contact is None:
        pytest.skip("Set CRAWLER_CONTACT before explicitly running the live test")
    evidence = fetch_live_smoke.run_smoke(settings, HttpUrl(fetch_live_smoke.DEFAULT_URL))
    assert evidence["passed"] is True
