from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Comment, NavigableString

from src.core.extraction_coordinator import ExtractionCoordinator
from src.strategies.support_article_strategy import SupportArticleStrategy


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_BATCH_ID = "20260812T125640Z-e5aa4b3f"
REFERENCE_RUN = ROOT / "runs" / REFERENCE_BATCH_ID
REFERENCE_MANIFEST = json.loads(
    (REFERENCE_RUN / "input-manifest.json").read_text(encoding="utf-8")
)
REFERENCE_ITEMS = {
    item["item_id"]: item for item in REFERENCE_MANIFEST["items"]
}
DIRECT_TEXT_MARKER = "域名证书一般在域名注册平台下载"


def _main_content(
    html: str,
    *,
    source_url: str = "https://www.azure.cn/zh-cn/support/icp/example/",
) -> str:
    soup = BeautifulSoup(html, "html.parser")
    strategy = SupportArticleStrategy(
        {"slug": "example", "support_article_type": "ICP"}
    )
    return strategy._extract_main_content(strategy._find_content(soup), source_url)


def _extract_reference_item(item_id: str, tmp_path: Path):
    item = REFERENCE_ITEMS[item_id]
    coordinator = ExtractionCoordinator(
        str(tmp_path / "compat-output"),
        payload_root=tmp_path / "outputs",
        diagnostic_root=tmp_path / "diagnostics",
    )
    return coordinator.coordinate_extraction(
        item["product_key"],
        item["identity"]["language"],
        version_key=item["resource"]["version_key"],
        expected_input_sha256=item["normalized_input"]["sha256"],
        preselected_strategy=item["strategy"],
    )


def _frozen_direct_text(item_id: str) -> str:
    item = REFERENCE_ITEMS[item_id]
    source_path = ROOT / item["normalized_input"]["path"]
    soup = BeautifulSoup(
        source_path.read_bytes().decode("utf-8-sig"), "html.parser"
    )
    content = soup.select_one("div.pure-content") or soup.body or soup
    first_h2 = content.find("h2")
    assert first_h2 is not None
    direct_nodes = []
    current = first_h2
    while current is not None:
        if (
            isinstance(current, NavigableString)
            and not isinstance(current, Comment)
            and str(current).strip()
        ):
            direct_nodes.append(str(current))
        current = current.next_sibling
    assert len(direct_nodes) == 1
    assert DIRECT_TEXT_MARKER in direct_nodes[0]
    return direct_nodes[0]


def test_main_content_preserves_mixed_direct_text_in_physical_order() -> None:
    html = (
        '<div class="pure-content"><h1>Title</h1><h2>Body</h2>'
        "after-h2<h3>Question 18</h3>text-before<br/>text-after"
        "<h3>Question 19</h3>left<a>link</a>right</div>"
    )

    assert _main_content(html) == (
        "<h2>Body</h2>after-h2<h3>Question 18</h3>text-before"
        "<br/>text-after<h3>Question 19</h3>left<a>link</a>right"
    )


def test_main_content_preserves_duplicate_text_and_meaningful_whitespace() -> None:
    html = (
        '<div class="pure-content"><h2>Body</h2>  repeat me  '
        "<span>A</span>  repeat me  <p>End</p></div>"
    )

    main_content = _main_content(html)

    assert main_content.count("  repeat me  ") == 2
    assert main_content == (
        "<h2>Body</h2>  repeat me  <span>A</span>  repeat me  "
        "<p>End</p>"
    )


def test_main_content_ignores_layout_whitespace_and_top_level_comments() -> None:
    html = (
        '<div class="pure-content"><h2>Body</h2>\n  \t'
        "<!--top-level comment-->\n"
        '<div class="tags">UI only</div>\n'
        '<p><a href="/media/a.png">asset</a></p></div>'
    )

    main_content = _main_content(html)

    assert main_content == (
        '<h2>Body</h2><p><a href="{base_url}/media/a.png">asset</a></p>'
    )
    assert "comment" not in main_content
    assert "UI only" not in main_content


@pytest.mark.parametrize(
    "html",
    [
        '<div class="pure-content"><h1>No body boundary</h1></div>',
        (
            '<div class="pure-content"><h2></h2>'
            '<div class="tags">UI only</div><!--comment--></div>'
        ),
    ],
)
def test_main_content_keeps_existing_empty_behavior(html: str) -> None:
    assert _main_content(html) == ""


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_bilingual_icp_faq_restores_the_complete_direct_answer_once(
    language: str,
    tmp_path: Path,
) -> None:
    item_id = f"{language}/icp-faq"
    result = _extract_reference_item(item_id, tmp_path)

    assert result.execution_succeeded
    assert result.payload is not None
    direct_text = _frozen_direct_text(item_id)
    main_content = result.payload["mainContent"]
    assert main_content.count(direct_text) == 1
    assert main_content.index("18.") < main_content.index(direct_text)
    assert main_content.index(direct_text) < main_content.index("19.")

    reference_path = REFERENCE_RUN / REFERENCE_ITEMS[item_id]["artifacts"][
        "payload"
    ]["path"]
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    assert {
        key: value for key, value in result.payload.items() if key != "mainContent"
    } == {
        key: value for key, value in reference.items() if key != "mainContent"
    }


@pytest.mark.parametrize(
    "item_id",
    [
        "zh-cn/sla-sql-data",
        "en-us/sla-sql-data",
        "zh-cn/legal-summary",
        "en-us/legal-summary",
        "zh-cn/psr-summary",
        "en-us/psr-summary",
    ],
)
def test_real_bilingual_unaffected_support_families_are_byte_identical(
    item_id: str,
    tmp_path: Path,
) -> None:
    result = _extract_reference_item(item_id, tmp_path)

    assert result.execution_succeeded
    assert result.payload_path is not None
    reference_path = REFERENCE_RUN / REFERENCE_ITEMS[item_id]["artifacts"][
        "payload"
    ]["path"]
    assert result.payload_path.read_bytes() == reference_path.read_bytes()
