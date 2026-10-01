"""Offline tests cannot open network connections or read developer credentials."""

import os
import socket
from collections.abc import Iterator
from typing import NoReturn

import pytest


@pytest.fixture(autouse=True)
def offline_environment(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    if request.node.get_closest_marker("live"):
        yield
        return
    for name in tuple(os.environ):
        if name.upper() in {
            "OPENROUTER_API_KEY",
            "SERPER_API_KEY",
            "PAGES",
            "PER_PAGE",
            "MAX_URLS",
            "MODEL_TIMEOUT_SECONDS",
            "MODEL_MAX_RETRIES",
        } or name.upper().startswith("MODELS"):
            monkeypatch.delenv(name, raising=False)

    def deny_network(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("Network access is forbidden in the offline unit suite")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    yield
