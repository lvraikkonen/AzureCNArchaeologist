"""Semantic fragment fingerprints and compact deterministic diffs."""

from __future__ import annotations

import copy
import html
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from src.core.canonical_identity import canonical_sha256


MAX_DIFFS = 20
SUMMARY_LIMIT = 256


def _text(value: str) -> str:
    decoded = html.unescape(value)
    normalized = unicodedata.normalize("NFC", decoded)
    return " ".join(normalized.split())


def _attr_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return sorted(_text(str(item)) for item in value)
    if value is None:
        return ""
    return _text(str(value))


def _tag_model(tag: Tag) -> dict[str, Any]:
    attrs = {
        str(key).lower(): _attr_value(value)
        for key, value in sorted(tag.attrs.items(), key=lambda item: str(item[0]))
    }
    children = []
    for child in tag.children:
        model = _node_model(child)
        if model is not None:
            children.append(model)
    return {
        "type": "element",
        "name": str(tag.name).lower(),
        "attrs": attrs,
        "children": children,
    }


def _node_model(node: Any) -> dict[str, Any] | None:
    if isinstance(node, Comment):
        return None
    if isinstance(node, NavigableString):
        text = _text(str(node))
        return {"type": "text", "text": text} if text else None
    if isinstance(node, Tag):
        return _tag_model(node)
    return None


def html_fragment_model(value: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(value or "", "html.parser")
    nodes = []
    for child in soup.contents:
        model = _node_model(child)
        if model is not None:
            nodes.append(model)
    return nodes


def semantic_model(value: Any) -> Any:
    if isinstance(value, str):
        return {"html_fragment": html_fragment_model(value)}
    if isinstance(value, Mapping):
        return {
            str(key): semantic_model(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [semantic_model(child) for child in value]
    return copy.deepcopy(value)


def semantic_fingerprint(value: Any) -> str:
    return canonical_sha256(semantic_model(value))


def _summary(value: Any) -> str:
    rendered = repr(value)
    if len(rendered) <= SUMMARY_LIMIT:
        return rendered
    return rendered[: SUMMARY_LIMIT - 1] + "..."


def _diffs(expected: Any, actual: Any, path: str, output: list[dict[str, str]]) -> None:
    if len(output) >= MAX_DIFFS:
        return
    if type(expected) is not type(actual):
        output.append(
            {
                "path": path,
                "expected": _summary(expected),
                "actual": _summary(actual),
            }
        )
        return
    if isinstance(expected, Mapping):
        keys = sorted(set(expected) | set(actual))
        for key in keys:
            if len(output) >= MAX_DIFFS:
                return
            child_path = f"{path}.{key}"
            if key not in expected or key not in actual:
                output.append(
                    {
                        "path": child_path,
                        "expected": _summary(expected.get(key, "<missing>")),
                        "actual": _summary(actual.get(key, "<missing>")),
                    }
                )
            else:
                _diffs(expected[key], actual[key], child_path, output)
        return
    if isinstance(expected, list):
        maximum = max(len(expected), len(actual))
        for index in range(maximum):
            if len(output) >= MAX_DIFFS:
                return
            child_path = f"{path}[{index}]"
            if index >= len(expected) or index >= len(actual):
                output.append(
                    {
                        "path": child_path,
                        "expected": _summary(
                            expected[index] if index < len(expected) else "<missing>"
                        ),
                        "actual": _summary(
                            actual[index] if index < len(actual) else "<missing>"
                        ),
                    }
                )
            else:
                _diffs(expected[index], actual[index], child_path, output)
        return
    if expected != actual:
        output.append(
            {
                "path": path,
                "expected": _summary(expected),
                "actual": _summary(actual),
            }
        )


def diff_document(
    *,
    scope: str,
    source_value: Any,
    payload_value: Any,
    source_fingerprint: str | None,
    payload_fingerprint: str | None,
) -> dict[str, Any]:
    source_model = semantic_model(source_value)
    payload_model = semantic_model(payload_value)
    differences: list[dict[str, str]] = []
    _diffs(source_model, payload_model, "$", differences)
    return {
        "schema_version": "1.0",
        "scope": scope,
        "source_fingerprint": source_fingerprint,
        "payload_fingerprint": payload_fingerprint,
        "differences": differences,
    }
