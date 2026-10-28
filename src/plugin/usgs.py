"""The USGS Earthquake Catalog's FDSN event service (earthquake.usgs.gov): events in a window around a point."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from contract import Event
from verifier.quakes import distance_km, format_utc

URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
TIMEOUT = 30.0


def query_url(params: dict) -> str:
    return URL + "?" + urllib.parse.urlencode(sorted(params.items()))


def fetch_text(url: str) -> str:
    """USGS's answer, as it sends it. Raises when it cannot be had: there is no fallback."""
    request = urllib.request.Request(url, headers={"User-Agent": "nanoagent-quake-finder"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode()


def search(
    latitude: float, longitude: float, radius_km: float, start_ms: int, end_ms: int, min_magnitude: str
) -> list[Event]:
    """Every catalog event with a magnitude, from the window, around the point; distances from the point.

    USGS is asked a little wider (radius + 25 km, magnitude - 0.1, the end second included), so the
    exact rules are applied by the caller to every event that could matter.
    """
    params = {
        "format": "geojson",
        "orderby": "time-asc",
        "limit": "2000",
        "latitude": f"{latitude:.4f}",
        "longitude": f"{longitude:.4f}",
        "maxradiuskm": f"{radius_km + 25:.0f}",
        "minmagnitude": f"{float(min_magnitude) - 0.1:.1f}",
        "starttime": format_utc(start_ms, with_millis=False)[:-1],
        "endtime": format_utc(end_ms + 999, with_millis=False)[:-1],
    }
    # Keep the magnitudes exactly as USGS writes them.
    features = json.loads(fetch_text(query_url(params)), parse_float=str)["features"]
    events = []
    for feature in features:
        props, (lon, lat, depth) = feature["properties"], feature["geometry"]["coordinates"][:3]
        if props.get("mag") is None:
            continue
        events.append(
            Event(
                id=feature["id"],
                time_utc=format_utc(int(props["time"])),
                time_ms=int(props["time"]),
                magnitude=str(props["mag"]),
                latitude=float(lat),
                longitude=float(lon),
                depth_km=float(depth),
                place=props.get("place") or "",
                distance_km=distance_km(latitude, longitude, float(lat), float(lon)),
            )
        )
    return events
