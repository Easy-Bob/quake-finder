# Quake Finder

A `nanoagent.plugin/v0001` plugin. Its task, `find-quakes`, asks an agent
for every earthquake within a radius of a city during one year of the
city's own calendar, at or above a magnitude, from the live
[USGS Earthquake Catalog](https://earthquake.usgs.gov/fdsnws/event/1/). It
also asks for the largest and the closest. A rule-based verifier recomputes
the answer from the catalog data pinned before the agent started, and checks
the agent found the events in its own searches.

## Tools

| Tool | Does | Code |
|---|---|---|
| `pin_quakes` | The answer key: the catalog's events a day either side of the local year, 25 km wider and 0.1 magnitude lower than the question, with their distances from the city | `src/plugin/tools.py` |
| `city_info` | A city's coordinates and its fixed UTC offset | `src/plugin/tools.py` |
| `search_quakes` | A live catalog search: every event in a UTC window, within a radius of a point, at or above a magnitude, with its distance. At most 3 per workspace; each appends a receipt to `quakes/receipts.jsonl` | `src/plugin/tools.py`, `src/plugin/usgs.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `find-quakes` | Finds the qualifying earthquakes, the largest and the closest | `agent`, with `city_info` and `search_quakes`; reference `pin_quakes` |

## The task

The catalog records time in UTC, but "in 2011" for Tokyo means Tokyo's
2011. That starts at 2010-12-31T15:00:00Z. A quake at 2010-12-31T23:01Z is
already New Year's morning in Tokyo. The agent turns the question into the
right search and names the largest and the closest events.

### The rules (`verifier/quakes.py`)

- A city's local year runs from Jan 1 00:00 to the next Jan 1 00:00 in its
  fixed UTC offset. The eight cities never use daylight saving time: Tokyo
  +09:00, Manila +08:00, Jakarta +07:00, Kathmandu +05:45, Lima −05:00,
  Honolulu −10:00, Reykjavik +00:00, Taipei +08:00.
- An event qualifies when it is in that window, its magnitude is at least
  the minimum (compared as exact decimals; equal counts), and its distance
  from the city is at most the radius (equal counts).
- Distance is the haversine on a 6371.0 km sphere, rounded to metres.
- Largest is the highest magnitude, smallest is the closest distance, and ties
  go to the earliest.

Times are whole milliseconds since 1970, with integer calendar arithmetic
(the verifier may not import `datetime`). The tests check it against
`datetime` for 36 years and every city's offset.

### Live data, pinned and receipted

`pin_quakes` reads the catalog before the agent starts and pins a slightly
wider set of events. The verifier applies the exact rules to those itself.
Each `search_quakes` call records what it returned in a hash-chained receipt.
The verifier checks that every event the agent saw matches the pinned
catalog. If USGS revised or added an event in between, it says so and asks
for a rerun.

## The verifier

`verifier/task.py` runs eight checks in order.

| # | Check | Fails when | Score |
|---|---|---|---|
| 1 | `key-integrity` | The key is altered, is for another question, or has a distance that is not its event's distance from the city | 0 |
| 2 | `receipts-integrity` | A search receipt was edited, dropped or reordered | 0 |
| 3 | `receipts-agree` | An event the agent saw differs from, or is missing from, the pinned catalog | 0 |
| 4 | `submitted-shape` | Ids are repeated or unknown, the count is wrong, or the largest or closest is not among the reported events | 0 |
| 5 | `events-exact` | The reported events are not exactly the qualifying ones | partial (F1) |
| 6 | `largest-correct` | The wrong largest | partial |
| 7 | `closest-correct` | The wrong closest | partial |
| 8 | `proven` | A reported event never appeared in the agent's own searches | × 0.5 |

When checks 1–4 hold, the score is the mean of the events' F1, the largest
being right and the closest being right, halved if not proven, at most 0.99
unless all eight hold. Example: `events-exact: usp000dcam (M5.1,
2004-12-31T20:13Z = 2005-01-01 05:13 Tokyo time, 165.399 km) qualifies but is
not reported`.

## Layout

It has the standard plugin layout, which NanoAgent requires:

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions (earthquake.usgs.gov), tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # needed environment variable names (none here)
├── src/plugin/      # the MCP server (__main__.py, its IMPLEMENTATIONS table), the tools, the USGS client and tools_dev/
├── tests/           # rule, tool and verifier tests, fixtures/ (recorded USGS answers) and cases/ (scripted runs)
├── ui/              # outputs drawn from their JSON Schema
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier package: quakes.py (shared with the tools), tools.py and task.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

`uv run pytest` runs offline:
- it replays the USGS answers recorded in `tests/fixtures/usgs/`;
- it checks the rules against `datetime` and known distances;
- it runs every tool;
- it plays `tests/cases/`: 22 scripted runs with the verdicts they expect.

The questions cover Tokyo 2005, Taipei 2006 and 2007, Kathmandu 2015, Lima
2007, Honolulu 2015 (no quakes), Reykjavik 2008, Manila 2019 and Jakarta
2019. The cases include UTC-year mistakes, a strict magnitude, a too-wide
radius, wrong largest or closest, unproven answers and tampering.

```bash
NANOAGENT_NETWORK=1 uv run pytest   # ask the live catalog instead
NANOAGENT_RECORD=1 uv run pytest    # record the fixtures again
```
