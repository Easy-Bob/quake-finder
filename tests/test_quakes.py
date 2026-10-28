"""The rules against Python's datetime (which only the tests may use) and known facts."""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest

from verifier.quakes import (
    CITIES,
    closest,
    distance_km,
    format_utc,
    largest,
    local_year,
    offset_text,
    parse_utc,
    qualifying,
    question_problem,
)


def test_utc_times_round_trip_and_match_datetime() -> None:
    moment = datetime.datetime(1989, 12, 30, 0, 0, tzinfo=datetime.UTC)
    while moment.year < 2026:
        text = moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
        millis = (moment - datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)) // datetime.timedelta(milliseconds=1)
        assert parse_utc(text) == millis and format_utc(millis) == text
        moment += datetime.timedelta(hours=37, minutes=13, seconds=7, milliseconds=411)


@pytest.mark.parametrize("city", list(CITIES))
@pytest.mark.parametrize("year", [1990, 2004, 2015, 2024])
def test_local_year_matches_datetime_with_the_fixed_offset(city: str, year: int) -> None:
    zone = datetime.timezone(datetime.timedelta(minutes=CITIES[city][2]))
    start = datetime.datetime(year, 1, 1, tzinfo=zone).timestamp() * 1000
    end = datetime.datetime(year + 1, 1, 1, tzinfo=zone).timestamp() * 1000
    assert local_year(city, year) == (int(start), int(end))


def test_tokyos_2011_starts_on_new_years_eve_in_utc() -> None:
    start, _ = local_year("Tokyo", 2011)
    assert format_utc(start, with_millis=False) == "2010-12-31T15:00:00Z"
    assert offset_text(345) == "+05:45" and offset_text(-300) == "-05:00"


def test_distance_is_the_haversine_on_a_6371_km_sphere() -> None:
    assert distance_km(0.0, 0.0, 0.0, 1.0) == 111.195
    assert distance_km(35.6895, 139.6917, 35.6895, 139.6917) == 0.0
    assert 2400 < distance_km(35.6895, 139.6917, 14.5995, 120.9842) < 3100  # Tokyo to Manila


@pytest.mark.parametrize("text", ["2024-02-30T00:00:00Z", "2024-01-01 00:00:00", "2024-01-01T24:00:00Z", "x"])
def test_parse_utc_refuses_what_is_not_a_utc_time(text: str) -> None:
    with pytest.raises(ValueError):
        parse_utc(text)


def event(ident, when, mag, km):
    return SimpleNamespace(id=ident, time_ms=parse_utc(when), magnitude=mag, distance_km=km)


def test_qualifying_is_inclusive_at_the_magnitude_and_radius_and_ties_go_to_the_earliest() -> None:
    events = [
        event("a", "2015-03-01T00:00:00Z", "6.0", 100.0),  # exactly the magnitude
        event("b", "2015-04-01T00:00:00Z", "6.5", 300.0),  # exactly the radius
        event("c", "2015-05-01T00:00:00Z", "6.5", 300.001),  # 1 m too far
        event("d", "2015-06-01T00:00:00Z", "5.9", 10.0),  # too small
        event("e", "2015-07-01T00:00:00Z", "6.5", 100.0),  # ties b's magnitude and a's distance, later
    ]
    kept = qualifying("Reykjavik", 2015, "6.0", 300, events)
    assert [e.id for e in kept] == ["a", "b", "e"]
    assert largest(kept).id == "b" and closest(kept).id == "a"
    assert largest([]) is None and closest([]) is None


@pytest.mark.parametrize(
    ("question", "message"),
    [
        (("Tokyo", 1989, "5.0", 300), "1990 to 2024"),
        (("Tokyo", 2005, "5", 300), "one decimal"),
        (("Tokyo", 2005, "4.4", 300), "4.5"),
        (("Tokyo", 2005, "5.0", 20), "50 to 800"),
    ],
)
def test_question_problem(question: tuple, message: str) -> None:
    assert message in question_problem(*question)
