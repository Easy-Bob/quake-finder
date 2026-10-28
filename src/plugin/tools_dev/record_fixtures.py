"""Where the offline tests keep the USGS answers they replay: tests/fixtures/usgs/<sha256 of the URL>.json.gz.

Recording runs the tests against the live catalog and saves every answer they ask for, gzipped
without a timestamp; replaying (the default) reads them back, so the tests need no network:

    NANOAGENT_RECORD=1 uv run pytest     # record (needs the network)
    uv run pytest                        # replay
    NANOAGENT_NETWORK=1 uv run pytest    # ask the live catalog, record nothing
"""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "usgs"


def fixture_path(url: str) -> Path:
    return FIXTURES / f"{hashlib.sha256(url.encode()).hexdigest()[:24]}.json.gz"


def save(url: str, text: str) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    fixture_path(url).write_bytes(gzip.compress(text.encode(), mtime=0))


def load(url: str) -> str:
    path = fixture_path(url)
    if not path.exists():
        raise FileNotFoundError(f"no recorded USGS answer for {url}: record with NANOAGENT_RECORD=1 uv run pytest")
    return gzip.decompress(path.read_bytes()).decode()
