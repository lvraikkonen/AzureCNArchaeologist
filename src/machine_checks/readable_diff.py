"""Readable differences for complete JSON and HTML comparisons."""

from __future__ import annotations

from typing import Any


def json_differences(expected: Any, actual: Any, path: str = "$" ) -> list[dict[str, Any]]:
    """Compare complete values and report every differing JSON path."""

    if type(expected) is not type(actual):
        return [
            {
                "path": path,
                "reason": "类型不同",
                "expected": _readable_value(expected),
                "actual": _readable_value(actual),
            }
        ]
    if isinstance(expected, dict):
        differences: list[dict[str, Any]] = []
        for key in expected:
            child_path = f"{path}.{key}"
            if key not in actual:
                differences.append(
                    {
                        "path": child_path,
                        "reason": "第二次结果缺少字段",
                        "expected": _readable_value(expected[key]),
                        "actual": "<缺少>",
                    }
                )
            else:
                differences.extend(
                    json_differences(expected[key], actual[key], child_path)
                )
        for key in actual:
            if key not in expected:
                differences.append(
                    {
                        "path": f"{path}.{key}",
                        "reason": "第二次结果多出字段",
                        "expected": "<缺少>",
                        "actual": _readable_value(actual[key]),
                    }
                )
        return differences
    if isinstance(expected, list):
        differences = []
        if len(expected) != len(actual):
            differences.append(
                {
                    "path": path,
                    "reason": "列表长度不同",
                    "expected": len(expected),
                    "actual": len(actual),
                }
            )
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            differences.extend(
                json_differences(
                    expected_item,
                    actual_item,
                    f"{path}[{index}]",
                )
            )
        return differences
    if expected != actual:
        difference = {
            "path": path,
            "reason": "值不同",
            "expected": _readable_value(expected),
            "actual": _readable_value(actual),
        }
        if isinstance(expected, str) and isinstance(actual, str):
            difference["text_difference"] = text_difference(expected, actual)
        return [difference]
    return []


def text_difference(expected: str, actual: str, context: int = 100) -> dict[str, Any]:
    """Describe the first mismatch while still comparing both full strings."""

    limit = min(len(expected), len(actual))
    position = next(
        (index for index in range(limit) if expected[index] != actual[index]),
        limit,
    )
    start = max(0, position - context)
    end_expected = min(len(expected), position + context)
    end_actual = min(len(actual), position + context)
    return {
        "first_different_character": position,
        "expected_length": len(expected),
        "actual_length": len(actual),
        "expected_context": expected[start:end_expected],
        "actual_context": actual[start:end_actual],
    }


def _readable_value(value: Any) -> Any:
    if isinstance(value, str) and len(value) > 240:
        return {
            "text_length": len(value),
            "beginning": value[:120],
            "ending": value[-120:],
        }
    return value

