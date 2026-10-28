from __future__ import annotations

from pathlib import Path

import pytest

from contract import City, CityInput, QuakeInput, SearchInput
from plugin import city_info, pin_quakes, search_quakes
from plugin.tools import read_receipts

KATHMANDU = SearchInput(
    latitude=27.7172, longitude=85.324, radius_km=300,
    start_utc="2014-12-31T18:15:00Z", end_utc="2015-12-31T18:15:00Z", min_magnitude="6.0",
)  # fmt: skip


def test_city_info_gives_the_fixed_offset() -> None:
    info = city_info(CityInput(city=City.KATHMANDU), Path("."))
    assert (info.utc_offset, info.utc_offset_minutes) == ("+05:45", 345)


def test_search_quakes_filters_exactly_and_receipts_what_it_returned(tmp_path: Path) -> None:
    found = search_quakes(KATHMANDU, tmp_path)
    assert found.count == 6 and found.calls_left == 2
    assert all(e.distance_km <= 300 and float(e.magnitude) >= 6.0 for e in found.events)
    assert max(found.events, key=lambda e: float(e.magnitude)).magnitude == "7.8"
    [line] = read_receipts(tmp_path)
    assert [row[0] for row in line["events"]] == [e.id for e in found.events] and line["prev"] == ""


def test_search_quakes_allows_three_searches(tmp_path: Path) -> None:
    for _ in range(3):
        search_quakes(KATHMANDU, tmp_path)
    with pytest.raises(ValueError, match="all 3 searches"):
        search_quakes(KATHMANDU, tmp_path)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"end_utc": "2014-12-31T18:15:00Z"}, "after start_utc"),
        ({"end_utc": "2016-03-01T00:00:00Z"}, "400 days"),
        ({"radius_km": 0}, "1 to 1000"),
        ({"start_utc": "2014-12-31"}, "not a UTC time"),
    ],
)
def test_search_quakes_refuses_a_malformed_search(tmp_path: Path, changes: dict, message: str) -> None:
    asked = SearchInput(**{**KATHMANDU.__dict__, **changes})
    with pytest.raises(ValueError, match=message):
        search_quakes(asked, tmp_path)


def test_pin_quakes_refuses_a_malformed_question() -> None:
    with pytest.raises(ValueError, match="one decimal"):
        pin_quakes(QuakeInput(city=City.TOKYO, year=2005, min_magnitude="5", radius_km=300), Path("."))
