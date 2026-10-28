"""Each tool's input and output checks."""

from .quakes import CITIES, distance_km, magnitude, offset_text, parse_utc, question_problem, table_sha256
from .task import result


def events_problem(events):
    ids = [event.id for event in events]
    if len(set(ids)) != len(ids):
        return "an event is listed twice"
    for event in events:
        try:
            magnitude(event.magnitude)
            parse_utc(event.time_utc)
        except ValueError as error:
            return f"{event.id}: {error}"
        if parse_utc(event.time_utc) != event.time_ms:
            return f"{event.id}: time_utc and time_ms disagree"
    return None


class Pin:
    @staticmethod
    def verify_input(value):
        problem = question_problem(value.city.value, value.year, value.min_magnitude, value.radius_km)
        return result(problem is None, problem or "input is valid")

    @staticmethod
    def verify_output(input_value, output_value, workspace):
        asked = (input_value.city, input_value.year, input_value.min_magnitude, input_value.radius_km)
        if (output_value.city, output_value.year, output_value.min_magnitude, output_value.radius_km) != asked:
            return result(False, "the key is for another question")
        problem = events_problem(output_value.candidates)
        if problem:
            return result(False, problem)
        digest = table_sha256(
            input_value.city.value,
            input_value.year,
            input_value.min_magnitude,
            input_value.radius_km,
            output_value.candidates,
        )
        if output_value.table_sha256 != digest:
            return result(False, "table_sha256 does not match the key")
        return result(True, "the key is consistent", candidates=len(output_value.candidates))


class City:
    @staticmethod
    def verify_input(value):
        return result(True, "input is valid")

    @staticmethod
    def verify_output(input_value, output_value, workspace):
        lat, lon, offset = CITIES[input_value.city.value]
        given = (
            output_value.latitude,
            output_value.longitude,
            output_value.utc_offset_minutes,
            output_value.utc_offset,
        )
        if given != (lat, lon, offset, offset_text(offset)):
            return result(False, "the city's facts are not the plugin's")
        return result(True, "the city's facts are right")


class Search:
    @staticmethod
    def verify_input(value):
        try:
            start, end = parse_utc(value.start_utc), parse_utc(value.end_utc)
            magnitude(value.min_magnitude)
        except ValueError as error:
            return result(False, str(error))
        if end <= start:
            return result(False, "end_utc must be after start_utc")
        if not 1 <= value.radius_km <= 1000:
            return result(False, "radius_km must be 1 to 1000")
        return result(True, "input is valid")

    @staticmethod
    def verify_output(input_value, output_value, workspace):
        problem = events_problem(output_value.events)
        if problem:
            return result(False, problem)
        start, end = parse_utc(input_value.start_utc), parse_utc(input_value.end_utc)
        least = magnitude(input_value.min_magnitude)
        for event in output_value.events:
            far = distance_km(input_value.latitude, input_value.longitude, event.latitude, event.longitude)
            if far != event.distance_km or far > input_value.radius_km:
                return result(False, f"{event.id} is not within the radius, or its distance is wrong")
            if not start <= event.time_ms < end or magnitude(event.magnitude) < least:
                return result(False, f"{event.id} is outside the window or below the magnitude")
        if output_value.count != len(output_value.events):
            return result(False, "count is not how many events there are")
        return result(True, "the search results are consistent", events=output_value.count)
