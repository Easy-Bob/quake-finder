"""The three tools: the hidden answer key, the city's facts, and the agent's catalog searches (receipted)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from contract import CityInput, CityOutput, PinOutput, QuakeInput, SearchInput, SearchOutput
from plugin import usgs
from verifier.quakes import (
    CITIES,
    DAY_MS,
    line_sha256,
    local_year,
    magnitude,
    offset_text,
    parse_utc,
    question_problem,
    row,
    table_sha256,
)

MAX_SEARCHES = 3
MAX_EVENTS = 60


def pin_quakes(value: QuakeInput, workspace: Path) -> PinOutput:
    """The find-quakes task's reference: the catalog a little wider than the question (a day either
    side of the local year, 25 km more, 0.1 less magnitude), pinned before the agent starts."""
    problem = question_problem(value.city.value, value.year, value.min_magnitude, value.radius_km)
    if problem:
        raise ValueError(problem)
    lat, lon, _ = CITIES[value.city.value]
    start, end = local_year(value.city.value, value.year)
    candidates = usgs.search(lat, lon, value.radius_km, start - DAY_MS, end + DAY_MS, value.min_magnitude)
    return PinOutput(
        city=value.city,
        year=value.year,
        min_magnitude=value.min_magnitude,
        radius_km=value.radius_km,
        candidates=candidates,
        table_sha256=table_sha256(value.city.value, value.year, value.min_magnitude, value.radius_km, candidates),
    )


def city_info(value: CityInput, workspace: Path) -> CityOutput:
    lat, lon, offset = CITIES[value.city.value]
    return CityOutput(
        city=value.city, latitude=lat, longitude=lon, utc_offset=offset_text(offset), utc_offset_minutes=offset
    )


def receipts_file(workspace: Path) -> Path:
    return workspace / "quakes" / "receipts.jsonl"


def read_receipts(workspace: Path) -> list[dict]:
    path = receipts_file(workspace)
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def search_quakes(value: SearchInput, workspace: Path) -> SearchOutput:
    start, end = parse_utc(value.start_utc), parse_utc(value.end_utc)
    least = magnitude(value.min_magnitude)
    if not start < end <= start + 400 * DAY_MS:
        raise ValueError("end_utc must be after start_utc, at most 400 days later")
    if not 1 <= value.radius_km <= 1000:
        raise ValueError("radius_km must be 1 to 1000")
    earlier = read_receipts(workspace)
    if len(earlier) >= MAX_SEARCHES:
        raise ValueError(f"all {MAX_SEARCHES} searches are used: submit from the results so far")
    found = usgs.search(value.latitude, value.longitude, value.radius_km, start, end, value.min_magnitude)
    events = sorted(
        (
            e
            for e in found
            if start <= e.time_ms < end and magnitude(e.magnitude) >= least and e.distance_km <= value.radius_km
        ),
        key=lambda e: (e.time_ms, e.id),
    )
    if len(events) > MAX_EVENTS:
        raise ValueError(f"{len(events)} events match; at most {MAX_EVENTS} are returned: narrow the search")
    body = {
        "call": len(earlier) + 1,
        "query": [
            value.latitude,
            value.longitude,
            value.radius_km,
            value.start_utc,
            value.end_utc,
            value.min_magnitude,
        ],
        "events": [row(e) for e in events],
        "prev": earlier[-1]["sha256"] if earlier else "",
    }
    path = receipts_file(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as out:
        out.write(json.dumps(body | {"sha256": line_sha256(body)}, sort_keys=True) + "\n")
    calls = len(earlier) + 1
    return SearchOutput(
        events=[replace(e) for e in events], count=len(events), calls_used=calls, calls_left=MAX_SEARCHES - calls
    )
