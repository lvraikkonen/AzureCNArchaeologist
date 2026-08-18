from __future__ import annotations

import pytest

from src.utils.html.normalization import HtmlInputError, normalize_html, parse_html_bytes


def test_normalization_materializes_live_tick_after_removing_tag_whitespace() -> None:
    source = '<table>\n<tr><td> \n <i class="icon icon-tick"></i> \n </td></tr>\n</table>'

    assert normalize_html(source) == "<table><tr><td>✓</td></tr></table>"


def test_normalization_does_not_materialize_tick_inside_comment() -> None:
    source = '<div><!-- <i class="icon-tick"></i> --><i class="icon-tick"></i></div>'

    normalized = normalize_html(source)

    assert '<!-- <i class="icon-tick"></i> -->' in normalized
    assert normalized.endswith("✓</div>")


def test_normalization_rewrites_root_images_in_src_and_banner_configuration() -> None:
    source = (
        "<div data-config=\"{'backgroundImage':'/Images/media/images/a.png'}\">"
        '<img src="/Images/media/images/b.png"/></div>'
    )

    normalized = normalize_html(source)

    assert "'backgroundImage':'{base_url}/Images/media/images/a.png'" in normalized
    assert 'src="{base_url}/Images/media/images/b.png"' in normalized
    assert "media{base_url}" not in normalized


def test_normalization_is_idempotent() -> None:
    source = '<div>\n<img src="/Images/a.png"/> <i class="icon-tick"></i>\n</div>'
    once = normalize_html(source)

    assert normalize_html(once) == once


def test_parser_rejects_document_without_html_and_body() -> None:
    with pytest.raises(HtmlInputError, match="缺少 html 或 body"):
        parse_html_bytes(b"<div>fragment only</div>", source_name="fragment.html")

