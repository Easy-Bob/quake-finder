"""The find-quakes task's check: the reported events, largest and closest are the ones the pinned USGS
catalog gives for the question, and the agent found them in its own receipted searches.

Eight checks, in order. Failing one of the first four scores 0. Otherwise the score is the mean of
the events' F1, whether the largest is right and whether the closest is right, halved when the agent
reported an event it never searched up. Valid only when all eight hold.
"""

import json
from pathlib import Path

from .quakes import (
    CITIES,
    DAY_MS,
    closest,
    distance_km,
    format_utc,
    largest,
    line_sha256,
    local_year,
    magnitude,
    qualifying,
    row,
    table_sha256,
)

CHECKS = [
    "key-integrity",
    "receipts-integrity",
    "receipts-agree",
    "submitted-shape",
    "events-exact",
    "largest-correct",
    "closest-correct",
    "proven",
]


def result(valid, message, *, score=None, **details):
    return {"valid": valid, "score": float(valid) if score is None else score, "message": message, "details": details}


def verdict(check, why, score=0.0, **details):
    return result(False, f"{check}: {why}", score=score, failed=check, **details)


def key_problem(arguments, reference):
    if reference is None:
        return "no answer key was pinned"
    asked = (arguments.city, arguments.year, arguments.min_magnitude, arguments.radius_km)
    if (reference.city, reference.year, reference.min_magnitude, reference.radius_km) != asked:
        return "the answer key is for another question"
    city = arguments.city.value
    digest = table_sha256(city, arguments.year, arguments.min_magnitude, arguments.radius_km, reference.candidates)
    if reference.table_sha256 != digest:
        return "the answer key was altered: it no longer matches its sha256"
    lat, lon, _ = CITIES[city]
    for event in reference.candidates:
        if event.distance_km != distance_km(lat, lon, event.latitude, event.longitude):
            return f"the answer key's distance for {event.id} is not its distance from {city}"
    return None


def read_receipts(workspace):
    path = Path(workspace) / "quakes" / "receipts.jsonl"
    if not path.is_file():
        return [], None
    lines = [json.loads(text) for text in path.read_text().splitlines()]
    previous = ""
    for number, line in enumerate(lines, start=1):
        body = dict(line)
        digest = body.pop("sha256", None)
        if digest != line_sha256(body):
            return None, f"receipt {number} was altered after search_quakes wrote it"
        if body.get("prev") != previous or body.get("call") != number:
            return None, f"receipt {number} does not follow the one before it: a receipt was dropped or reordered"
        previous = digest
    return lines, None


def disagreement(arguments, reference, lines):
    """Why the events the agent read differ from the pinned catalog, or None."""
    city = arguments.city.value
    lat, lon, _ = CITIES[city]
    start, end = local_year(city, arguments.year)
    pinned = {event.id: row(event) for event in reference.candidates}
    least = magnitude(arguments.min_magnitude) - magnitude("0.1")
    for line in lines:
        for seen in line["events"]:
            ident, when, mag, elat, elon = seen
            if ident in pinned:
                if pinned[ident] != seen:
                    return f"{ident} has changed in the catalog since the answer key was pinned: run again"
            elif (
                start - DAY_MS <= when < end + DAY_MS
                and magnitude(mag) >= least
                and distance_km(lat, lon, elat, elon) <= arguments.radius_km + 25
            ):
                return f"{ident} was added to the catalog after the answer key was pinned: run again"
    return None


def local(event, city):
    """An event's time in the city's own clock, e.g. 2005-01-01 05:13."""
    return format_utc(event.time_ms + CITIES[city][2] * 60_000)[:16].replace("T", " ")


def why_not(event, arguments):
    """Why a reported event does not qualify."""
    city = arguments.city.value
    start, end = local_year(city, arguments.year)
    if not start <= event.time_ms < end:
        return f"it was on {local(event, city)} {city} time, outside the local year {arguments.year}"
    if magnitude(event.magnitude) < magnitude(arguments.min_magnitude):
        return f"its magnitude {event.magnitude} is below {arguments.min_magnitude}"
    return f"it is {event.distance_km} km from {city}, beyond {arguments.radius_km} km"


def verify_task(arguments, output, reference, workspace):
    """``output``: a contract QuakeOutput; ``reference``: pin_quakes' PinOutput."""
    problem = key_problem(arguments, reference)
    if problem:
        return verdict("key-integrity", problem)
    lines, problem = read_receipts(workspace)
    if problem:
        return verdict("receipts-integrity", problem)
    problem = disagreement(arguments, reference, lines)
    if problem:
        return verdict("receipts-agree", problem)

    city = arguments.city.value
    known = {event.id: event for event in reference.candidates}
    ids = output.event_ids
    if len(set(ids)) != len(ids) or output.count != len(ids):
        return verdict("submitted-shape", "event_ids must list each event once, and count must be how many")
    unknown = [ident for ident in ids if ident not in known]
    if unknown:
        return verdict("submitted-shape", f"{unknown[0]} is not a catalog event near {city} in that year")
    for name, chosen in (("largest_id", output.largest_id), ("closest_id", output.closest_id)):
        if (chosen == "") != (not ids) or (chosen and chosen not in ids):
            return verdict("submitted-shape", f'{name} must be one of event_ids, or "" exactly when there are none')

    truth = qualifying(city, arguments.year, arguments.min_magnitude, arguments.radius_km, reference.candidates)
    truth_ids = [event.id for event in truth]
    top, near = largest(truth), closest(truth)
    details = {"count": len(truth), "largest_id": top.id if top else "", "closest_id": near.id if near else ""}
    failures = []
    reported, wanted = set(ids), set(truth_ids)
    hits = len(reported & wanted)
    f1 = 1.0 if not reported and not wanted else 2 * hits / (len(reported) + len(wanted))
    if reported != wanted:
        missing = [e for e in truth if e.id not in reported]
        extra = [known[i] for i in ids if i not in wanted]
        if missing:
            e = missing[0]
            why = (
                f"{e.id} (M{e.magnitude}, {e.time_utc[:16]}Z = {local(e, city)} {city} time, {e.distance_km} km) "
                "qualifies but is not reported"
            )
        else:
            why = f"{extra[0].id} is reported but {why_not(extra[0], arguments)}"
        more = len(missing) + len(extra) - 1
        failures.append(("events-exact", why + (f" (+{more} more events wrong)" if more else "")))
    if output.largest_id != details["largest_id"]:
        failures.append(
            (
                "largest-correct",
                f"the largest is {details['largest_id'] or 'none'} (M{top.magnitude if top else '-'}), not {output.largest_id or 'none'}",
            )
        )
    if output.closest_id != details["closest_id"]:
        failures.append(
            (
                "closest-correct",
                f"the closest is {details['closest_id'] or 'none'} ({near.distance_km if near else '-'} km), not {output.closest_id or 'none'}",
            )
        )
    seen = {event[0] for line in lines for event in line["events"]}
    unseen = [ident for ident in ids if ident not in seen]
    if unseen:
        failures.append(("proven", f"{unseen[0]} never appeared in the agent's own search results"))
    if not failures:
        return result(True, f"All {len(CHECKS)} checks hold: {len(truth)} events.", **details)
    score = (f1 + (output.largest_id == details["largest_id"]) + (output.closest_id == details["closest_id"])) / 3
    score = round(min(0.99, score * (0.5 if unseen else 1.0)), 4)
    check, why = failures[0]
    more = f" (+{len(failures) - 1} more)" if len(failures) > 1 else ""
    return result(False, f"{check}: {why}{more}", score=score, failed=[c for c, _ in failures], **details)
