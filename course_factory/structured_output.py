from __future__ import annotations

import json
from typing import Any


class JSONExtractionError(ValueError):
    pass


def strip_markdown_fences(text: str) -> str:
    value = text.strip()
    if not value.startswith("```"):
        return value

    first_newline = value.find("\n")
    if first_newline < 0:
        return value

    header = value[3:first_newline].strip().lower()
    if header not in {"", "json"}:
        return value

    body = value[first_newline + 1 :]
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3]
    return body.strip()


def extract_first_json_value(text: str) -> str:
    """
    Return the first complete top-level JSON object or array.

    The scanner tracks nesting, quoted strings and escapes, so it safely
    handles nested data and braces/brackets embedded inside JSON strings.
    Any leading or trailing prose is ignored.
    """
    value = strip_markdown_fences(text)

    start = None
    for index, char in enumerate(value):
        if char in "[{":
            start = index
            break

    if start is None:
        raise JSONExtractionError(
            "No JSON object or array found in model response."
        )

    stack: list[str] = []
    in_string = False
    escaped = False

    for index in range(start, len(value)):
        char = value[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char in "[{":
            stack.append(char)
            continue

        if char in "]}":
            if not stack:
                raise JSONExtractionError(
                    "Unexpected JSON closing delimiter."
                )
            opening = stack[-1]
            expected = "}" if opening == "{" else "]"
            if char != expected:
                raise JSONExtractionError(
                    "Mismatched JSON delimiters."
                )
            stack.pop()
            if not stack:
                return value[start:index + 1]

    raise JSONExtractionError(
        "Incomplete JSON object or array in model response."
    )


def parse_first_json_value(text: str) -> Any:
    return json.loads(extract_first_json_value(text))
