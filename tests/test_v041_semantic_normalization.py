from __future__ import annotations

import pytest

from src.content_sampling.semantic import (
    MAX_DIFFS,
    diff_document,
    html_fragment_model,
    semantic_fingerprint,
    semantic_model,
)


def test_html_fragment_model_normalizes_whitespace_entities_nfc_and_comments() -> None:
    source = (
        "<!-- ignored -->"
        "<p>  Cafe\u0301&nbsp;&amp;\n price </p>"
        "<!-- ignored too -->"
    )

    assert html_fragment_model(source) == html_fragment_model(
        "<p>Café &amp; price</p>"
    )
    assert html_fragment_model(source) == [
        {
            "type": "element",
            "name": "p",
            "attrs": {},
            "children": [{"type": "text", "text": "Café & price"}],
        }
    ]


def test_semantic_model_sorts_mappings_but_preserves_sequence_duplicates() -> None:
    first = {
        "z": "<p>last</p>",
        "a": ["<b>one</b>", "<b>one</b>"],
    }
    reordered = {
        "a": ["<b>one</b>", "<b>one</b>"],
        "z": "<p>last</p>",
    }

    model = semantic_model(first)
    assert list(model) == ["a", "z"]
    assert model == semantic_model(reordered)
    assert len(model["a"]) == 2
    assert semantic_fingerprint(first) == semantic_fingerprint(reordered)
    assert semantic_fingerprint(first) != semantic_fingerprint(
        {"a": ["<b>one</b>"], "z": "<p>last</p>"}
    )


@pytest.mark.parametrize(
    ("source", "changed"),
    [
        ("<p>正文内容保持完整</p>", "<p>正文内容已经改变</p>"),
        ("<td>每月价格 ￥10</td>", "<td>每月价格 ￥11</td>"),
    ],
)
def test_semantic_fingerprint_detects_body_and_price_changes(
    source: str,
    changed: str,
) -> None:
    assert semantic_fingerprint(source) != semantic_fingerprint(changed)


def test_node_order_and_multiplicity_are_semantically_significant() -> None:
    ordered = "<p>A</p><p>B</p>"
    reversed_nodes = "<p>B</p><p>A</p>"
    duplicated = "<p>A</p><p>A</p>"
    single = "<p>A</p>"

    assert semantic_fingerprint(ordered) != semantic_fingerprint(reversed_nodes)
    assert semantic_fingerprint(duplicated) != semantic_fingerprint(single)
    assert len(html_fragment_model(duplicated)) == 2


def test_attribute_and_class_order_normalize_without_losing_key_attributes() -> None:
    first = (
        '<a class="primary wide" data-plan=" P1 " href="/plans/basic" '
        'title="Basic">Plan</a>'
    )
    reordered = (
        '<a title="Basic" href="/plans/basic" data-plan="P1" '
        'class="wide primary">Plan</a>'
    )

    assert html_fragment_model(first) == html_fragment_model(reordered)
    assert semantic_fingerprint(first) == semantic_fingerprint(reordered)


@pytest.mark.parametrize(
    ("source", "changed"),
    [
        ('<a href="/a">A</a>', '<a href="/b">A</a>'),
        ('<img src="/a.png">', '<img src="/b.png">'),
        ('<div id="east">A</div>', '<div id="north">A</div>'),
        (
            '<div data-region="east-china">A</div>',
            '<div data-region="north-china">A</div>',
        ),
    ],
)
def test_href_src_and_key_attribute_changes_are_detected(
    source: str,
    changed: str,
) -> None:
    assert semantic_fingerprint(source) != semantic_fingerprint(changed)


def test_diff_document_has_stable_attribute_then_text_paths() -> None:
    source = {"mainContent": '<a href="/a">Price ￥10</a>'}
    payload = {"mainContent": '<a href="/b">Price ￥11</a>'}
    source_fingerprint = semantic_fingerprint(source)
    payload_fingerprint = semantic_fingerprint(payload)

    result = diff_document(
        scope="full-content",
        source_value=source,
        payload_value=payload,
        source_fingerprint=source_fingerprint,
        payload_fingerprint=payload_fingerprint,
    )

    assert result == {
        "schema_version": "1.0",
        "scope": "full-content",
        "source_fingerprint": source_fingerprint,
        "payload_fingerprint": payload_fingerprint,
        "differences": [
            {
                "path": "$.mainContent.html_fragment[0].attrs.href",
                "expected": "'/a'",
                "actual": "'/b'",
            },
            {
                "path": "$.mainContent.html_fragment[0].children[0].text",
                "expected": "'Price ￥10'",
                "actual": "'Price ￥11'",
            },
        ],
    }


def test_diff_document_is_deterministically_capped_at_twenty_differences() -> None:
    source = list(range(25))
    payload = list(range(100, 125))

    result = diff_document(
        scope="cap",
        source_value=source,
        payload_value=payload,
        source_fingerprint=semantic_fingerprint(source),
        payload_fingerprint=semantic_fingerprint(payload),
    )

    assert MAX_DIFFS == 20
    assert len(result["differences"]) == MAX_DIFFS
    assert [difference["path"] for difference in result["differences"]] == [
        f"$[{index}]" for index in range(MAX_DIFFS)
    ]
