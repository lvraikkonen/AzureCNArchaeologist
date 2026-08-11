"""Source and persisted-payload projections used by sampled validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.core.canonical_input import CanonicalHtmlInput
from src.core.product_manager import ProductManager
from src.core.source_reachability import SourceReachability
from src.core.support_article_versions import (
    build_support_url_route_map,
    get_historical_version,
)
from src.strategies.complex_content_strategy import ComplexContentStrategy
from src.strategies.region_filter_strategy import RegionFilterStrategy
from src.strategies.simple_static_strategy import SimpleStaticStrategy
from src.strategies.support_article_strategy import SupportArticleStrategy
from src.utils.html.cleaner import materialize_cms_html_fields
from src.utils.media.image_processor import preprocess_image_paths


class ProjectionError(ValueError):
    """A source or payload projection cannot be derived without guessing."""


def _runtime_definition(
    definition: Mapping[str, Any],
    version_key: str | None,
    language: str,
) -> dict[str, Any]:
    value = dict(definition)
    if value.get("page_model") == "SupportArticlePage":
        extraction = dict(value.get("extraction", {}))
        extraction["url_route_map"] = build_support_url_route_map(value, language)
        value["extraction"] = extraction
    if version_key is not None:
        value["slug"] = get_historical_version(value, version_key)["slug"]
    return value


def _normalize_business_fields(
    payload: dict[str, Any],
    definition: Mapping[str, Any],
    language: str,
) -> dict[str, Any]:
    for key in (
        "validation",
        "extraction_metadata",
        "error",
        "source_file",
        "source_url",
        "quality_score",
    ):
        payload.pop(key, None)
    payload["slug"] = definition["slug"]
    if definition["page_model"] == "FlexibleContentPage":
        payload["language"] = language
    materialize_cms_html_fields(payload, definition["page_model"])
    return payload


class SourceContentProjector:
    """Project expected content exclusively from frozen source/config inputs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.product_manager = ProductManager(str(self.root / "data" / "configs"))

    def project_payload(
        self,
        *,
        product_key: str,
        language: str,
        version_key: str | None,
        canonical_input: CanonicalHtmlInput,
        strategy: str,
        source_reachability: SourceReachability | None,
    ) -> dict[str, Any]:
        product_definition = self.product_manager.get_product_config(product_key)
        definition = _runtime_definition(
            product_definition,
            version_key,
            language,
        )
        soup = preprocess_image_paths(
            BeautifulSoup(canonical_input.text, "html.parser")
        )
        source_definition = (
            get_historical_version(product_definition, version_key)["sources"][language]
            if version_key is not None
            else product_definition["sources"][language]
        )
        source_url = source_definition.get("url", "")
        html_path = canonical_input.normalized_path.as_posix()
        if strategy == "simple_static":
            payload = SimpleStaticStrategy(
                definition,
                html_path,
            ).extract_flexible_content(soup, source_url)
        elif strategy == "region_filter":
            payload = RegionFilterStrategy(
                definition,
                html_path,
            ).extract_flexible_content(soup, source_url)
        elif strategy == "complex":
            if source_reachability is None:
                raise ProjectionError("Complex source projection requires SourceReachability")
            payload = ComplexContentStrategy(
                definition,
                html_path,
            ).extract_flexible_content(
                soup,
                source_url,
                source_reachability=source_reachability,
            )
        elif strategy == "support_article":
            payload = SupportArticleStrategy(
                definition,
                html_path,
            ).extract_flexible_content(soup, source_url)
        else:
            raise ProjectionError(f"Unsupported source projection strategy: {strategy}")
        return _normalize_business_fields(payload, definition, language)


class PayloadContentProjector:
    """Project comparable scopes from a Business Payload document."""

    @staticmethod
    def page_global(payload: Mapping[str, Any], strategy: str) -> dict[str, Any]:
        if strategy == "support_article":
            return {
                "title": payload.get("title", ""),
                "slug": payload.get("slug", ""),
                "metaTitle": payload.get("metaTitle", ""),
                "metaDescription": payload.get("metaDescription", ""),
                "metaKeywords": payload.get("metaKeywords", ""),
                "pageType": payload.get("pageType", ""),
                "lastModifiedDate": payload.get("lastModifiedDate", ""),
            }
        value = {
            "title": payload.get("title", ""),
            "metaTitle": payload.get("metaTitle", ""),
            "metaDescription": payload.get("metaDescription", ""),
            "metaKeywords": payload.get("metaKeywords", ""),
            "slug": payload.get("slug", ""),
            "language": payload.get("language", ""),
            "commonSections": list(payload.get("commonSections", [])),
        }
        if strategy in {"region_filter", "complex"}:
            value["baseContent"] = payload.get("baseContent", "")
        return value

    @staticmethod
    def full_content(payload: Mapping[str, Any], strategy: str) -> dict[str, Any]:
        if strategy == "support_article":
            return {
                "articleDescription": payload.get("articleDescription", ""),
                "mainContent": payload.get("mainContent", ""),
            }
        if strategy == "simple_static":
            return {"baseContent": payload.get("baseContent", "")}
        raise ProjectionError(f"Full content is not applicable to {strategy}")

    @staticmethod
    def state_content(
        payload: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        expected_criteria = [
            {"filterKey": key, "matchValues": value}
            for key, value in state["criteria"]
        ]
        matches = []
        for index, group in enumerate(payload.get("contentGroups", [])):
            if not isinstance(group, Mapping):
                continue
            try:
                criteria = json.loads(str(group.get("filterCriteriaJson", "")))
            except json.JSONDecodeError as error:
                raise ProjectionError(
                    f"Invalid filterCriteriaJson at contentGroups[{index}]"
                ) from error
            if criteria == expected_criteria:
                matches.append(group)
        if len(matches) != 1:
            raise ProjectionError(
                "Expected exactly one content group for state "
                f"{state['state_id']}, found {len(matches)}"
            )
        group = matches[0]
        return {
            "content": group.get("content", ""),
            "sharedContent": group.get("sharedContent", ""),
        }
