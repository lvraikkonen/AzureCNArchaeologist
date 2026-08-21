"""Indexed table-unit projection for Complex source-state fragments."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from src.core.region_processor import RegionProjectionError
from src.utils.html.normalization import normalize_html


ElementPath = tuple[int, ...]


@dataclass(frozen=True)
class IndexedFragmentProjector:
    """Clone and project one stable group of adjacent source fragments."""

    _source_holder: Tag
    _paths_by_table_id: dict[str, tuple[ElementPath, ...]]

    @classmethod
    def build(
        cls,
        fragments: list[Tag],
        *,
        relevant_table_ids: frozenset[str],
    ) -> "IndexedFragmentProjector":
        soup = BeautifulSoup("<div></div>", "html.parser")
        holder = soup.div
        assert holder is not None
        for fragment in fragments:
            holder.append(deepcopy(fragment))

        units_by_table_id: dict[str, list[Tag]] = {}
        for candidate in holder.find_all(
            lambda tag: isinstance(tag, Tag)
            and any(
                str(tag.get(attribute, "")).strip() in relevant_table_ids
                for attribute in ("id", "data-table-id")
            )
        ):
            unit = _canonical_table_unit(candidate)
            identifiers = {
                str(candidate.get(attribute, "")).strip()
                for attribute in ("id", "data-table-id")
                if str(candidate.get(attribute, "")).strip() in relevant_table_ids
            }
            for table_id in identifiers:
                units = units_by_table_id.setdefault(table_id, [])
                if all(unit is not existing for existing in units):
                    units.append(unit)

        paths_by_table_id = {
            table_id: tuple(_element_path(holder, unit) for unit in units)
            for table_id, units in units_by_table_id.items()
        }
        return cls(holder, paths_by_table_id)

    @property
    def table_ids(self) -> frozenset[str]:
        return frozenset(self._paths_by_table_id)

    def project(self, excluded_table_ids: tuple[str, ...]) -> str:
        clone = deepcopy(self._source_holder)
        selected_paths = {
            path
            for table_id in excluded_table_ids
            for path in self._paths_by_table_id.get(table_id, ())
        }
        paths = _outermost_paths(selected_paths)
        selected_units = [_resolve_element_path(clone, path) for path in paths]
        for unit in selected_units:
            unit.decompose()
        if not _has_business_content(clone):
            return ""
        return normalize_html(clone.decode_contents())


def applicable_exclusions_for_software(
    projectors: list[IndexedFragmentProjector],
    excluded_table_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Resolve a config row against all leaves owned by one Software branch."""

    available_ids = frozenset().union(
        *(projector.table_ids for projector in projectors)
    )
    applicable = tuple(
        table_id for table_id in excluded_table_ids if table_id in available_ids
    )
    if excluded_table_ids and not applicable:
        raise RegionProjectionError(
            "该配置记录在当前 Software 的所有内容叶子中没有对应任何物理表格单元，"
            "实际为 0 个。"
        )
    return applicable


def _canonical_table_unit(candidate: Tag) -> Tag:
    if "scroll-table" in candidate.get("class", []):
        unit = candidate
    else:
        parent = candidate.find_parent("div", class_="scroll-table")
        unit = parent if isinstance(parent, Tag) else candidate
    if unit.name != "table" and "scroll-table" not in unit.get("class", []):
        identifiers = [
            str(candidate.get(attribute, "")).strip()
            for attribute in ("id", "data-table-id")
            if str(candidate.get(attribute, "")).strip()
        ]
        raise RegionProjectionError(
            f"名称 {identifiers!r} 指向的不是表格或 scroll-table 容器。"
        )
    return unit


def _element_path(root: Tag, node: Tag) -> ElementPath:
    indexes: list[int] = []
    current = node
    while current is not root:
        parent = current.parent
        if not isinstance(parent, Tag):
            raise RegionProjectionError("表格物理单元不在待投影片段内。")
        children = [child for child in parent.children if isinstance(child, Tag)]
        indexes.append(
            next(
                index
                for index, child in enumerate(children)
                if child is current
            )
        )
        current = parent
    return tuple(reversed(indexes))


def _resolve_element_path(root: Tag, path: ElementPath) -> Tag:
    current = root
    for index in path:
        children = [child for child in current.children if isinstance(child, Tag)]
        if index >= len(children):
            raise RegionProjectionError("投影片段的元素路径与 preflight 索引不一致。")
        current = children[index]
    return current


def _outermost_paths(paths: set[ElementPath]) -> tuple[ElementPath, ...]:
    result: list[ElementPath] = []
    for path in sorted(paths, key=lambda item: (len(item), item)):
        if any(path[: len(parent)] == parent for parent in result):
            continue
        result.append(path)
    return tuple(result)


def _has_business_content(fragment: Tag) -> bool:
    return bool(
        fragment.get_text(" ", strip=True)
        or fragment.select_one("img, video, audio, table, iframe")
    )
