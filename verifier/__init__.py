"""The deterministic verifier: each tool's checks, and the task's, on contract instances."""

from contract import Task, Tool

from . import task
from .tools import City, Pin, Search

TOOLS = {
    Tool.PIN_QUAKES: Pin,
    Tool.CITY_INFO: City,
    Tool.SEARCH_QUAKES: Search,
}

# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {
    Task.FIND_QUAKES: task.verify_task,
}


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
