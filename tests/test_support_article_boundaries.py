from __future__ import annotations

from bs4 import BeautifulSoup
import pytest

from src.machine_checks.independent_source import (
    IndependentSourceError,
    locate_support_source,
)
from src.strategies.support_article_strategy import SupportArticleStrategy


def _extract(html: str) -> tuple[dict[str, str], dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    strategy = SupportArticleStrategy(
        {
            "support_article_type": "SLA",
            "slug": "sample",
        }
    )
    payload = strategy.extract_flexible_content(soup)
    source = locate_support_source(soup)
    return payload, source


def test_direct_sectioned_article_preserves_complete_description_nodes() -> None:
    payload, source = _extract(
        """
        <html><head><title>Sample | Azure</title></head><body>
          <div class="pure-content">
            <h1>Sample SLA</h1>
            <div class="tags-date"><div class="ms-date">Updated: today</div></div>
            <div class="intro"><p>Summary</p><ol><li>Promise</li></ol></div>
            text between nodes
            <h2>Terms</h2><p>Full terms</p>
            <div id="content_feedback">Feedback</div>
          </div>
        </body></html>
        """
    )

    assert payload["articleDescription"] == source["articleDescription"]
    assert payload["mainContent"] == source["mainContent"]
    assert '<div class="intro"><p>Summary</p><ol><li>Promise</li></ol></div>' in source[
        "articleDescription"
    ]
    assert "text between nodes" in source["articleDescription"]
    assert "Updated" not in source["articleDescription"]
    assert "Feedback" not in source["mainContent"]


def test_single_wrapped_sectioned_article_uses_the_unique_body_root() -> None:
    payload, source = _extract(
        """
        <div class="pure-content">
          <h1>Wrapped SLA</h1>
          <div class="tags-date"><div class="wacn-date">今天</div></div>
          <div class="layout"><div class="article-body">
            <div class="intro"><p>Wrapped summary</p></div>
            <h2>Introduction</h2><p>Wrapped terms</p>
            <h2>Details</h2><table><tr><td>99.9%</td></tr></table>
          </div></div>
          <div class="content-feedback">Feedback</div>
        </div>
        """
    )

    assert payload["articleDescription"] == source["articleDescription"]
    assert payload["mainContent"] == source["mainContent"]
    assert '<div class="intro"><p>Wrapped summary</p></div>' == source[
        "articleDescription"
    ]
    assert source["mainContent"].startswith("<h2>Introduction</h2>")
    assert "99.9%" in source["mainContent"]


def test_headingless_short_article_maps_post_title_content_to_main() -> None:
    payload, source = _extract(
        """
        <div class="pure-content">
          <h1>Short SLA</h1>
          <div class="tags-date"><div class="ms-date">Updated: today</div></div>
          <p>No financially backed SLA is offered.</p>
          direct closing text
        </div>
        """
    )

    assert payload["articleDescription"] == source["articleDescription"] == ""
    assert payload["mainContent"] == source["mainContent"]
    assert "No financially backed SLA is offered." in source["mainContent"]
    assert "direct closing text" in source["mainContent"]
    assert "Updated" not in source["mainContent"]


@pytest.mark.parametrize(
    "html",
    (
        """
        <div class="pure-content">
          <h1>First title</h1><h1>Second title</h1><h2>Terms</h2><p>Body</p>
        </div>
        """,
        """
        <div class="pure-content">
          <h1>One title</h1>
          <div><h2>First body</h2><p>One</p></div>
          <div><h2>Second body</h2><p>Two</p></div>
        </div>
        """,
    ),
)
def test_independent_locator_blocks_ambiguous_article_roots(html: str) -> None:
    with pytest.raises(IndependentSourceError):
        locate_support_source(BeautifulSoup(html, "html.parser"))
