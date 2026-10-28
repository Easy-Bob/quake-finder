"""Tests replay recorded USGS answers, so they run offline and give the same results every time.
NANOAGENT_RECORD=1 records them from the live catalog; NANOAGENT_NETWORK=1 asks it without recording."""

import os

import pytest

from plugin import usgs
from plugin.tools_dev.record_fixtures import load, save

LIVE = usgs.fetch_text


def recording(url: str) -> str:
    text = LIVE(url)
    save(url, text)
    return text


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.environ.get("NANOAGENT_RECORD") == "1":
        monkeypatch.setattr(usgs, "fetch_text", recording)
    elif os.environ.get("NANOAGENT_NETWORK") != "1":
        monkeypatch.setattr(usgs, "fetch_text", load)
