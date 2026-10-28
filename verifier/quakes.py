"""The rules, shared by the tools and the verifier: the cities, local-year windows, distances, and which
events qualify. Standard library only, no ``datetime``: times are whole milliseconds since 1970.

- A city's local year runs from Jan 1 00:00 to the next Jan 1 00:00 in its fixed UTC offset (these
  cities never use daylight saving time). In UTC it starts ``offset`` earlier: Tokyo's 2011 starts at
  2010-12-31T15:00:00Z.
- An event qualifies when it is in that window, its magnitude is at least the minimum (compared as
  exact decimals), and its great-circle distance from the city is at most the radius.
- Distance: haversine on a sphere of radius 6371.0 km, rounded to 3 decimals (metres).
- Largest: the highest magnitude, ties to the earliest. Closest: the smallest distance, ties to the
  earliest.
"""

import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation

EARTH_KM = 6371.0
# City: (latitude, longitude, UTC offset in minutes).
CITIES = {
    "Tokyo": (35.6895, 139.6917, 540),
    "Manila": (14.5995, 120.9842, 480),
    "Jakarta": (-6.2088, 106.8456, 420),
    "Kathmandu": (27.7172, 85.324, 345),
    "Lima": (-12.0464, -77.0428, -300),
    "Honolulu": (21.3069, -157.8583, -600),
    "Reykjavik": (64.1466, -21.9426, 0),
    "Taipei": (25.033, 121.5654, 480),
}
FIRST_YEAR, LAST_YEAR = 1990, 2024
MAGNITUDE = re.compile(r"^[0-9]\.[0-9]$")
UTC = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?Z$")
DAY_MS = 86_400_000


def days_from_civil(year, month, day):
    """Days since 1970-01-01 (Howard Hinnant's algorithm)."""
    year -= month <= 2
    era = year // 400
    of_era = year - era * 400
    of_year = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    return era * 146097 + of_era * 365 + of_era // 4 - of_era // 100 + of_year - 719468


def civil_from_days(days):
    days += 719468
    era = days // 146097
    of_era = days - era * 146097
    year_of_era = (of_era - of_era // 1460 + of_era // 36524 - of_era // 146096) // 365
    of_year = of_era - (365 * year_of_era + year_of_era // 4 - year_of_era // 100)
    shifted = (5 * of_year + 2) // 153
    day = of_year - (153 * shifted + 2) // 5 + 1
    month = shifted + (3 if shifted < 10 else -9)
    return year_of_era + era * 400 + (month <= 2), month, day


def parse_utc(text):
    """Milliseconds since 1970 of a UTC time YYYY-MM-DDTHH:MM:SS[.sss]Z, or ValueError."""
    found = UTC.match(text)
    if not found:
        raise ValueError(f"{text!r} is not a UTC time written YYYY-MM-DDTHH:MM:SSZ")
    year, month, day, hour, minute, second = (int(part) for part in found.groups()[:6])
    lengths = [
        31,
        29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]
    if not 1 <= month <= 12 or not 1 <= day <= lengths[month - 1] or hour > 23 or minute > 59 or second > 59:
        raise ValueError(f"{text} is not a real time")
    millis = int((found.group(7) or "0").ljust(3, "0"))
    return days_from_civil(year, month, day) * DAY_MS + ((hour * 60 + minute) * 60 + second) * 1000 + millis


def format_utc(millis, with_millis=True):
    days, rest = divmod(millis, DAY_MS)
    year, month, day = civil_from_days(days)
    seconds, ms = divmod(rest, 1000)
    hour, seconds = divmod(seconds, 3600)
    minute, second = divmod(seconds, 60)
    tail = f".{ms:03d}Z" if with_millis else "Z"
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}{tail}"


def offset_text(minutes):
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def local_year(city, year):
    """(start, end) of the city's local calendar year in UTC milliseconds; end not included."""
    offset = CITIES[city][2] * 60_000
    return days_from_civil(year, 1, 1) * DAY_MS - offset, days_from_civil(year + 1, 1, 1) * DAY_MS - offset


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km, rounded to 3 decimals."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * EARTH_KM * math.asin(math.sqrt(min(1.0, a))), 3)


def magnitude(text):
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise ValueError(f"{text!r} is not a magnitude") from error


def question_problem(city, year, min_magnitude, radius_km):
    if not FIRST_YEAR <= year <= LAST_YEAR:
        return f"the year must be {FIRST_YEAR} to {LAST_YEAR}"
    if not MAGNITUDE.match(min_magnitude) or not Decimal("4.5") <= Decimal(min_magnitude) <= Decimal("8.0"):
        return 'min_magnitude must be "4.5" to "8.0", with one decimal'
    if not 50 <= radius_km <= 800:
        return "radius_km must be 50 to 800"
    return None


def qualifying(city, year, min_magnitude, radius_km, events):
    """The events that qualify, oldest first. ``events``: contract Events whose distance_km is from the city."""
    start, end = local_year(city, year)
    least = magnitude(min_magnitude)
    kept = [
        e for e in events if start <= e.time_ms < end and magnitude(e.magnitude) >= least and e.distance_km <= radius_km
    ]
    return sorted(kept, key=lambda e: (e.time_ms, e.id))


def largest(events):
    return min(events, key=lambda e: (-magnitude(e.magnitude), e.time_ms, e.id)) if events else None


def closest(events):
    return min(events, key=lambda e: (e.distance_km, e.time_ms, e.id)) if events else None


def row(event):
    """What a receipt or digest records of an event."""
    return [event.id, event.time_ms, event.magnitude, event.latitude, event.longitude]


def table_sha256(city, year, min_magnitude, radius_km, candidates):
    body = {"question": [city, year, min_magnitude, radius_km], "candidates": sorted(row(e) for e in candidates)}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def line_sha256(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
