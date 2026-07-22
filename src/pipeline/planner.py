"""Deterministic expansion of Product Definitions into batch resources."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from src.core.product_catalog import (
    ProductCatalog,
    artifact_relative_directory,
    normalized_input_path,
    sha256_file,
)
from src.core.support_article_versions import (
    historical_normalized_input_path,
    historical_resource_key,
    historical_versions,
)
from src.pipeline.models import BatchItem, LANGUAGES, PipelinePlan


class PlanningError(RuntimeError):
    """A fatal error prevented construction of a deterministic plan."""


class UnknownGroupError(PlanningError):
    """The requested Catalog Category or Support Article Type does not exist."""


class InvalidScopeError(PlanningError):
    """The requested scope or language is invalid."""


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as error:
        raise PlanningError(f"Pipeline path escapes repository root: {path}") from error


class PipelinePlanner:
    """Plan all current and historical resources without inspecting content quality."""

    def __init__(self, root: str | Path = ".", catalog: ProductCatalog | None = None) -> None:
        self.root = Path(root).resolve()
        self.catalog = catalog or ProductCatalog(self.root)

    def plan(
        self,
        scope: str = "all",
        *,
        group: str | None = None,
        language: str = "both",
    ) -> PipelinePlan:
        if scope not in ("all", "group"):
            raise InvalidScopeError("scope must be 'all' or 'group'")
        if scope == "all" and group is not None:
            raise InvalidScopeError("group cannot be supplied with all scope")
        if scope == "group" and not group:
            raise InvalidScopeError("group scope requires a group name")

        languages = self._languages(language)
        records = self.catalog.load_definitions()
        index = self.catalog.build_index()
        product_keys = self._product_keys(index, scope, group)
        items: list[BatchItem] = []

        for product_key in product_keys:
            record = records[product_key]
            definition = record.definition
            for selected_language in languages:
                items.append(self._current_item(record.relative_path, definition, selected_language))
                for version in historical_versions(definition):
                    items.append(self._historical_item(record.relative_path, definition, version, selected_language))

        items.sort(key=lambda item: (item.language, item.resource_key))
        scope_value: dict[str, Any] = {"kind": scope}
        if group is not None:
            scope_value["group"] = group
        return PipelinePlan(scope=scope_value, languages=languages, items=tuple(items))

    @staticmethod
    def _languages(language: str) -> tuple[str, ...]:
        if language == "both":
            return LANGUAGES
        if language in LANGUAGES:
            return (language,)
        raise InvalidScopeError(f"Unsupported language: {language}")

    @staticmethod
    def _product_keys(index: dict[str, Any], scope: str, group: str | None) -> list[str]:
        if scope == "all":
            return sorted(index["products"])
        assert group is not None
        if group.startswith("SupportArticle/"):
            support_type = group.removeprefix("SupportArticle/")
            view = index["support_article_types"].get(support_type)
        else:
            view = index["catalog_categories"].get(group)
        if view is None:
            known = sorted(index["catalog_categories"]) + [
                f"SupportArticle/{value}" for value in sorted(index["support_article_types"])
            ]
            raise UnknownGroupError(f"Unknown pipeline group: {group}. Known groups: {', '.join(known)}")
        return sorted(view["products"])

    def _current_item(
        self,
        config_path: str,
        definition: dict[str, Any],
        language: str,
    ) -> BatchItem:
        product_key = definition["product_key"]
        source = definition["sources"][language]
        normalized = normalized_input_path(self.root, definition, language)
        return self._item(
            config_path=config_path,
            definition=definition,
            language=language,
            resource_key=product_key,
            resource_kind="current",
            slug=definition["slug"],
            source=source,
            normalized=normalized,
        )

    def _historical_item(
        self,
        config_path: str,
        definition: dict[str, Any],
        version: dict[str, Any],
        language: str,
    ) -> BatchItem:
        product_key = definition["product_key"]
        version_key = version["version_key"]
        return self._item(
            config_path=config_path,
            definition=definition,
            language=language,
            resource_key=historical_resource_key(product_key, version_key),
            resource_kind="historical_version",
            slug=version["slug"],
            source=version["sources"][language],
            normalized=historical_normalized_input_path(self.root, definition, language, version_key),
            version_key=version_key,
            version_label=version["version_label"],
        )

    def _item(
        self,
        *,
        config_path: str,
        definition: dict[str, Any],
        language: str,
        resource_key: str,
        resource_kind: str,
        slug: str,
        source: dict[str, Any],
        normalized: Path,
        version_key: str | None = None,
        version_label: str | None = None,
    ) -> BatchItem:
        source_path: Path | None = None
        if source["availability"] == "available":
            source_path = self.root / "data" / "current_prod_html" / language / source["snapshot_path"]

        skip_reason: dict[str, str] | None = None
        if definition["capability_status"] == "known_unsupported":
            skip_reason = {
                "code": "KNOWN_UNSUPPORTED",
                "message": definition["unsupported_reason"],
            }
        elif source["availability"] == "unavailable":
            skip_reason = {
                "code": "SOURCE_UNAVAILABLE",
                "message": source["unavailable_reason"],
            }

        relative_dir = artifact_relative_directory(definition, language)
        output = Path("outputs") / relative_dir / f"{resource_key}.json"
        diagnostic = Path("diagnostics") / relative_dir / f"{resource_key}.sidecar.json"
        validation = Path("validation") / relative_dir / f"{resource_key}.validation.json"
        config_relative = Path("data") / "configs" / config_path
        config_absolute = self.root / config_relative
        strategy = (
            "support_article"
            if definition["page_model"] == "SupportArticlePage"
            else definition.get("extraction", {}).get("strategy", "auto")
        )

        return BatchItem(
            language=language,
            resource_key=resource_key,
            product_key=definition["product_key"],
            resource_kind=resource_kind,
            page_model=definition["page_model"],
            capability_status=definition["capability_status"],
            config_path=config_relative.as_posix(),
            config_sha256=sha256_file(config_absolute),
            source_availability=source["availability"],
            source_path=_relative(self.root, source_path) if source_path else None,
            source_sha256=sha256_file(source_path) if source_path and source_path.is_file() else None,
            normalized_path=_relative(self.root, normalized),
            # Normalization is a byte-identical copy.  Freeze the expected hash
            # from the source, never from a possibly stale generated file.
            normalized_sha256=sha256_file(source_path) if source_path and source_path.is_file() else None,
            output_path=output.as_posix(),
            diagnostic_path=diagnostic.as_posix(),
            validation_path=validation.as_posix(),
            slug=slug,
            strategy=strategy,
            catalog_categories=tuple(sorted(definition.get("catalog_categories", []))),
            support_article_type=definition.get("support_article_type"),
            version_key=version_key,
            version_label=version_label,
            source_url=source.get("url"),
            cms_path=source.get("cms_path"),
            skip_reason=skip_reason,
        )
