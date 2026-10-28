"""A scripted find-quakes run: the case's searches through the real tools, its submission, then the
real verifier. No model runs.

A case (tests/cases/<name>.json) gives the question, the searches the agent makes (each
[latitude, longitude, radius_km, start_utc, end_utc, min_magnitude]), the submission, an optional
tamper, and the verdict it expects.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import City, QuakeInput, QuakeOutput, SearchInput
from plugin import pin_quakes, search_quakes, usgs
from plugin.tools import read_receipts, receipts_file

CASES = Path(__file__).parent / "cases"


def question(case: dict) -> QuakeInput:
    return QuakeInput(**(case["question"] | {"city": City(case["question"]["city"])}))


def run_case(case: dict, workspace: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    asked = question(case)
    reference = pin_quakes(asked, workspace / "scratch")
    tamper = case.get("tamper")
    if tamper == "changed-data":
        # The catalog revises the first event's magnitude between the answer key's read and the agent's.
        original = usgs.search

        def revised(*args, **kwargs):
            events = original(*args, **kwargs)
            return [replace(events[0], magnitude="9.9"), *events[1:]] if events else events

        monkeypatch.setattr(usgs, "search", revised)
    for lat, lon, radius, start, end, least in case["searches"]:
        search_quakes(
            SearchInput(
                latitude=lat, longitude=lon, radius_km=radius, start_utc=start, end_utc=end, min_magnitude=least
            ),
            workspace,
        )
    lines = read_receipts(workspace)
    if tamper == "edit-receipt":
        lines[0]["events"] = lines[0]["events"][1:]
    elif tamper == "altered-key":
        reference = replace(reference, candidates=reference.candidates[1:])
    elif tamper not in (None, "changed-data"):
        raise ValueError(f"unknown tamper {tamper!r}")
    if tamper == "edit-receipt":
        receipts_file(workspace).write_text("".join(json.dumps(line, sort_keys=True) + "\n" for line in lines))
    # The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
    return verifier.verify_task(
        "find-quakes",
        build_output(plain_output(asked), QuakeInput),
        build_output(plain_output(QuakeOutput(**case["submit"])), QuakeOutput),
        reference,
        str(workspace),
    )


def load_cases() -> list[dict]:
    return [json.loads(path.read_text()) | {"name": path.stem} for path in sorted(CASES.glob("*.json"))]
