"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    PIN_QUAKES = "pin_quakes"
    CITY_INFO = "city_info"
    SEARCH_QUAKES = "search_quakes"


class Task(Enum):
    FIND_QUAKES = "find-quakes"


class City(Enum):
    TOKYO = "Tokyo"
    MANILA = "Manila"
    JAKARTA = "Jakarta"
    KATHMANDU = "Kathmandu"
    LIMA = "Lima"
    HONOLULU = "Honolulu"
    REYKJAVIK = "Reykjavik"
    TAIPEI = "Taipei"


CITY = "The city, one of Tokyo, Manila, Jakarta, Kathmandu, Lima, Honolulu, Reykjavik or Taipei"
MAGNITUDE = 'A magnitude written with one decimal, e.g. "5.0"'
UTC = "A UTC time written YYYY-MM-DDTHH:MM:SSZ"


@dataclass
class Event(Output):
    id: Annotated[str, "The USGS event id, e.g. us7000abcd"]
    time_utc: Annotated[str, "When it happened, UTC, YYYY-MM-DDTHH:MM:SS.sssZ"]
    time_ms: Annotated[int, "When it happened, in milliseconds since 1970-01-01T00:00:00Z"]
    magnitude: Annotated[str, "Its magnitude as USGS gives it, e.g. 5.44"]
    latitude: Annotated[float, "Its epicentre's latitude"]
    longitude: Annotated[float, "Its epicentre's longitude"]
    depth_km: Annotated[float, "Its depth in km"]
    place: Annotated[str, "USGS's description of where it was"]
    distance_km: Annotated[float, "Its great-circle distance from the search's centre, km, 3 decimals"]


@dataclass
class QuakeInput(Output):
    city: Annotated[City, CITY]
    year: Annotated[int, "The year in the city's own calendar, 1990 to 2024"]
    min_magnitude: Annotated[str, 'The smallest magnitude that counts, "4.5" to "8.0" with one decimal']
    radius_km: Annotated[int, "How far from the city, in km, 50 to 800"]


@dataclass
class PinOutput(Output):
    city: Annotated[City, CITY]
    year: Annotated[int, "The year"]
    min_magnitude: Annotated[str, MAGNITUDE]
    radius_km: Annotated[int, "The radius in km"]
    candidates: Annotated[
        list[Event], "Every catalog event a little wider than the question, with distances from the city"
    ]
    table_sha256: Annotated[str, "The sha256 of the question and the candidates, as quakes.table_sha256 computes it"]


@dataclass
class CityInput(Output):
    city: Annotated[City, CITY]


@dataclass
class CityOutput(Output):
    city: Annotated[City, CITY]
    latitude: Annotated[float, "The city's latitude"]
    longitude: Annotated[float, "The city's longitude"]
    utc_offset: Annotated[
        str, 'Its fixed offset from UTC all year, e.g. "+09:00" or "-05:00"; it never uses daylight saving time'
    ]
    utc_offset_minutes: Annotated[int, "The same offset in minutes, e.g. 540 or -300"]


@dataclass
class SearchInput(Output):
    latitude: Annotated[float, "The search centre's latitude"]
    longitude: Annotated[float, "The search centre's longitude"]
    radius_km: Annotated[int, "The search radius in km, 1 to 1000"]
    start_utc: Annotated[str, "The first instant searched, UTC, YYYY-MM-DDTHH:MM:SSZ (included)"]
    end_utc: Annotated[str, "The instant the search stops, UTC, YYYY-MM-DDTHH:MM:SSZ (not included)"]
    min_magnitude: Annotated[str, MAGNITUDE]


@dataclass
class SearchOutput(Output):
    events: Annotated[
        list[Event], "Every catalog event in the window, at least the magnitude and within the radius, by time"
    ]
    count: Annotated[int, "How many events"]
    calls_used: Annotated[int, "How many searches this workspace has made, this one included"]
    calls_left: Annotated[int, "How many searches are left"]


@dataclass
class QuakeOutput(Output):
    event_ids: Annotated[list[str], "Every qualifying event's id, oldest first"]
    count: Annotated[int, "How many qualifying events"]
    largest_id: Annotated[str, 'The id of the largest event (ties: the earliest), or "" when there is none']
    closest_id: Annotated[str, 'The id of the event closest to the city (ties: the earliest), or "" when there is none']


TOOLS = {
    Tool.PIN_QUAKES: (QuakeInput, PinOutput),
    Tool.CITY_INFO: (CityInput, CityOutput),
    Tool.SEARCH_QUAKES: (SearchInput, SearchOutput),
}

TASKS = {Task.FIND_QUAKES: (QuakeInput, QuakeOutput)}
