from __future__ import annotations

from src.utils.html.cleaner import (
    CMS_HTML_SEMANTIC_MATERIALIZATION_VERSION,
    ICON_TICK_TEXT,
    clean_html_content,
    materialize_cms_html_fields,
    materialize_css_generated_semantics,
)


def test_live_empty_icon_tick_is_materialized_as_versioned_text() -> None:
    source = (
        '<td><i aria-hidden="true" class="icon icon-tick">\n</i></td>'
        "<td><i class='icon-tick icon'></i></td>"
    )

    projected = materialize_css_generated_semantics(source)

    assert CMS_HTML_SEMANTIC_MATERIALIZATION_VERSION == (
        "css-generated-semantics-v1"
    )
    assert ICON_TICK_TEXT == "✓"
    assert projected == "<td>✓</td><td>✓</td>"
    assert materialize_css_generated_semantics(projected) == projected


def test_materialization_ignores_comments_nonempty_and_other_classes() -> None:
    source = (
        '<!-- <i class="icon icon-tick"></i> -->'
        '<i class="icon icon-tick">already explicit</i>'
        '<i class="icon icon-plus"></i>'
        '<i class="icon foo-icon-tick"></i>'
    )

    projected = materialize_css_generated_semantics(source)

    assert projected == source


def test_clean_html_content_compacts_without_applying_cms_projection() -> None:
    source = (
        '<table>\n<tr>\n<td>\n<i class="icon icon-tick">\n</i>\n</td>\n'
        "</tr>\n</table>"
    )

    assert clean_html_content(source) == (
        '<table><tr><td><i class="icon icon-tick"></i></td></tr></table>'
    )


def test_final_payload_boundary_materializes_all_closed_world_html_fields() -> None:
    icon = '<i class="icon icon-tick"></i>'
    payload = {
        "baseContent": icon,
        "contentGroups": [
            {"content": icon, "sharedContent": icon},
            {"content": "plain"},
        ],
        "commonSections": [{"content": icon}],
        "pageConfig": {"filtersJsonConfig": icon},
    }

    materialize_cms_html_fields(payload, "FlexibleContentPage")

    assert payload["baseContent"] == "✓"
    assert payload["contentGroups"][0] == {
        "content": "✓",
        "sharedContent": "✓",
    }
    assert payload["contentGroups"][1]["content"] == "plain"
    assert payload["commonSections"][0]["content"] == "✓"
    assert payload["pageConfig"]["filtersJsonConfig"] == icon


def test_final_support_article_boundary_materializes_main_content() -> None:
    payload = {
        "mainContent": '<p><i class="icon icon-tick"></i></p>',
        "articleDescription": '<i class="icon icon-tick"></i>',
    }

    materialize_cms_html_fields(payload, "SupportArticlePage")

    assert payload["mainContent"] == "<p>✓</p>"
    assert payload["articleDescription"] == '<i class="icon icon-tick"></i>'
