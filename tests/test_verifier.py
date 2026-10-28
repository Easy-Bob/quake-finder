from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from slimconfig import build_output, plain_output

import verifier
from contract import TOOLS, City, CityInput, QuakeInput, SearchInput, Tool
from plugin import city_info, pin_quakes, search_quakes

# NanoAgent's sandbox lets a verifier import only these, contract and its own package.
ALLOWED_IMPORTS = {
    "__future__", "collections", "dataclasses", "decimal", "difflib", "enum", "fractions", "functools",
    "hashlib", "itertools", "json", "math", "operator", "pathlib", "re", "statistics", "string",
    "textwrap", "typing", "unicodedata",
}  # fmt: skip
FORBIDDEN_NAMES = {"__import__", "compile", "eval", "exec", "getattr", "globals", "open", "setattr", "vars"}


# The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
def verify_input(tool: str, value: dict) -> dict:
    return verifier.verify_input(tool, build_output(value, TOOLS[Tool(tool)][0]))


def verify_output(tool: str, given: dict, made, workspace: Path) -> dict:
    given_class, made_class = TOOLS[Tool(tool)]
    return verifier.verify_output(
        tool, build_output(given, given_class), build_output(plain_output(made), made_class), str(workspace)
    )


def test_the_verifier_imports_only_what_the_sandbox_allows() -> None:
    for path in Path(verifier.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] in ALLOWED_IMPORTS for alias in node.names), path.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module.split(".")[0] in ALLOWED_IMPORTS | {"contract"}, path.name
            elif isinstance(node, ast.Name):
                assert node.id not in FORBIDDEN_NAMES, f"{path.name} uses {node.id}"
            elif isinstance(node, ast.Attribute):
                assert not node.attr.startswith("_"), f"{path.name} reaches {node.attr}"


def test_checks_what_the_types_cannot_say() -> None:
    good = {"city": "Lima", "year": 2007, "min_magnitude": "6.0", "radius_km": 400}
    assert verify_input("pin_quakes", good)["valid"] is True
    assert verify_input("pin_quakes", good | {"radius_km": 5})["valid"] is False
    search = {"latitude": 0.0, "longitude": 0.0, "radius_km": 100, "start_utc": "2007-01-01T05:00:00Z",
              "end_utc": "2008-01-01T05:00:00Z", "min_magnitude": "6.0"}  # fmt: skip
    assert verify_input("search_quakes", search)["valid"] is True
    assert verify_input("search_quakes", search | {"end_utc": "2006-01-01T00:00:00Z"})["valid"] is False


def test_tool_outputs_are_checked(tmp_path: Path) -> None:
    info = city_info(CityInput(city=City.LIMA), tmp_path)
    assert verify_output("city_info", {"city": "Lima"}, info, tmp_path)["valid"] is True
    assert verify_output("city_info", {"city": "Lima"}, replace(info, utc_offset_minutes=0), tmp_path)["valid"] is False
    asked = SearchInput(latitude=-12.0464, longitude=-77.0428, radius_km=400, start_utc="2007-01-01T05:00:00Z",
                        end_utc="2008-01-01T05:00:00Z", min_magnitude="6.0")  # fmt: skip
    found = search_quakes(asked, tmp_path)
    assert verify_output("search_quakes", plain_output(asked), found, tmp_path)["valid"] is True
    found.events[0] = replace(found.events[0], distance_km=found.events[0].distance_km + 1)
    assert verify_output("search_quakes", plain_output(asked), found, tmp_path)["valid"] is False


def test_the_answer_key_is_checked(tmp_path: Path) -> None:
    asked = {"city": "Lima", "year": 2007, "min_magnitude": "6.0", "radius_km": 400}
    key = pin_quakes(QuakeInput(city=City.LIMA, year=2007, min_magnitude="6.0", radius_km=400), tmp_path)
    assert verify_output("pin_quakes", asked, key, tmp_path)["valid"] is True
    assert verify_output("pin_quakes", asked | {"year": 2008}, key, tmp_path)["valid"] is False
    assert verify_output("pin_quakes", asked, replace(key, table_sha256="0" * 64), tmp_path)["valid"] is False


def test_the_task_input_is_the_reference_tools() -> None:
    assert TOOLS[Tool.PIN_QUAKES][0] is QuakeInput
