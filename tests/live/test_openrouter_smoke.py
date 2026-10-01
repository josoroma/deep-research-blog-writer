"""Opt-in real provider acceptance; never collected into the default offline run."""

import pytest

from evaluations.live_smoke import main


@pytest.mark.live
def test_production_model_returns_typed_tool_call() -> None:
    assert main() == 0
