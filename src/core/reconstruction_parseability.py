"""Independent-parser reconstruction parseability assurance.

The production BeautifulSoup parser and an independent lxml parser consume the
same immutable UTF-8 text.  They project parser-specific DOMs into a small,
deterministic semantic snapshot; only material content differences block the
input.  HTML serialization and repair details are intentionally excluded.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

import bs4
from bs4 import (
    BeautifulSoup,
    Comment,
    Declaration,
    Doctype,
    NavigableString,
    ProcessingInstruction,
    Tag,
)
from lxml import etree, html as lxml_html

from src.core.canonical_input import CanonicalHtmlInput, SourceFinding


EXCLUDED_TEXT_TAGS = frozenset(("script", "style", "noscript", "template"))
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
PROFILE_VERSION = "1.0"


DEFAULT_PROFILE: dict[str, Any] = {
    "schema_version": PROFILE_VERSION,
    "main_roots": [
        {
            "key": "pure_content",
            "bs4": "div.pure-content",
            "xpath": "//div[contains(concat(' ', normalize-space(@class), ' '), ' pure-content ')]",
        },
        {"key": "main", "bs4": "main", "xpath": "//main"},
        {"key": "role_main", "bs4": "[role='main']", "xpath": "//*[@role='main']"},
        {"key": "body", "bs4": "body", "xpath": "//body"},
    ],
    "critical_fragments": [
        {"key": "title", "bs4": "title", "xpath": "//title", "attributes": []},
        {
            "key": "meta_description",
            "bs4": "meta[name='description' i]",
            "xpath": "//meta[translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='description']",
            "attributes": ["content"],
        },
        {
            "key": "ms_service_tag",
            "bs4": "tags[ms\\.service]",
            "xpath": "//tags[@ms.service]",
            "attributes": ["ms.service"],
        },
        {
            "key": "ms_service_meta",
            "bs4": "meta[name='ms.service' i]",
            "xpath": "//meta[translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='ms.service']",
            "attributes": ["content"],
        },
        {
            "key": "technical_selector",
            "bs4": ".technical-azure-selector",
            "xpath": "//*[contains(concat(' ', normalize-space(@class), ' '), ' technical-azure-selector ')]",
            "attributes": ["id", "class"],
        },
        {
            "key": "region_control",
            "bs4": "#region-container, [name='region']",
            "xpath": "//*[@id='region-container'] | //*[@name='region']",
            "attributes": ["id", "name", "value", "data-href", "href"],
        },
        {
            "key": "software_control",
            "bs4": "#software-container, [name='software']",
            "xpath": "//*[@id='software-container'] | //*[@name='software']",
            "attributes": ["id", "name", "value", "data-href", "href"],
        },
        {
            "key": "tab_targets",
            "bs4": "[data-href], a[href^='#']",
            "xpath": "//*[@data-href] | //a[starts-with(@href, '#')]",
            "attributes": ["id", "value", "data-href", "href"],
        },
    ],
}


class ParserAdapter(Protocol):
    name: str
    version: str

    def parse(self, text: str) -> Any:
        ...

    def snapshot(self, document: Any, profile: Mapping[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ParseabilityResult:
    production_soup: Any | None
    evidence: Mapping[str, Any]

    @property
    def passed(self) -> bool:
        return self.evidence["verdict"] == "passed"


class BeautifulSoupParserAdapter:
    name = "beautifulsoup-html.parser"
    version = bs4.__version__

    def parse(self, text: str) -> BeautifulSoup:
        return BeautifulSoup(text, "html.parser")

    def snapshot(
        self, document: BeautifulSoup, profile: Mapping[str, Any]
    ) -> dict[str, Any]:
        body = document.body or document
        body_text = _bs4_text(body)
        main_selector: str | None = None
        main: Tag | BeautifulSoup = body
        for candidate in profile["main_roots"]:
            selected = document.select_one(candidate["bs4"])
            if selected is not None:
                main_selector = candidate["key"]
                main = selected
                break

        tables = [_bs4_table_snapshot(table) for table in document.find_all("table")]
        critical: dict[str, dict[str, Any]] = {}
        for specification in profile["critical_fragments"]:
            selected = document.select(specification["bs4"])
            fingerprints = [
                _fragment_fingerprint(
                    str(element.name).lower(),
                    _bs4_text(element),
                    {
                        name: _normalize_attribute(name, element.attrs.get(name))
                        for name in specification["attributes"]
                        if element.attrs.get(name) is not None
                    },
                )
                for element in selected
            ]
            critical[specification["key"]] = {
                "count": len(fingerprints),
                "fingerprints": fingerprints,
            }
        return {
            "body": _text_fingerprint(body_text),
            "main": {
                "selector": main_selector,
                **_text_fingerprint(_bs4_text(main)),
            },
            "pricing_tables": tables,
            "critical_fragments": critical,
        }


class LxmlHtmlParserAdapter:
    name = "lxml.html"
    version = ".".join(str(part) for part in etree.LXML_VERSION)

    def parse(self, text: str) -> etree._Element:
        return lxml_html.document_fromstring(text)

    def snapshot(
        self, document: etree._Element, profile: Mapping[str, Any]
    ) -> dict[str, Any]:
        bodies = document.xpath("//body")
        body = bodies[0] if bodies else document
        body_text = _lxml_text(body)
        main_selector: str | None = None
        main = body
        for candidate in profile["main_roots"]:
            selected = document.xpath(candidate["xpath"])
            if selected:
                main_selector = candidate["key"]
                main = selected[0]
                break

        tables = [_lxml_table_snapshot(table) for table in document.xpath("//table")]
        critical: dict[str, dict[str, Any]] = {}
        for specification in profile["critical_fragments"]:
            selected = document.xpath(specification["xpath"])
            fingerprints = [
                _fragment_fingerprint(
                    _lxml_tag(element),
                    _lxml_text(element),
                    {
                        name: _normalize_attribute(name, element.get(name))
                        for name in specification["attributes"]
                        if element.get(name) is not None
                    },
                )
                for element in selected
                if isinstance(element, etree._Element)
            ]
            critical[specification["key"]] = {
                "count": len(fingerprints),
                "fingerprints": fingerprints,
            }
        return {
            "body": _text_fingerprint(body_text),
            "main": {
                "selector": main_selector,
                **_text_fingerprint(_lxml_text(main)),
            },
            "pricing_tables": tables,
            "critical_fragments": critical,
        }


class ReconstructionParseabilityValidator:
    def __init__(
        self,
        *,
        production_adapter: ParserAdapter | None = None,
        independent_adapter: ParserAdapter | None = None,
        profile: Mapping[str, Any] | None = None,
    ) -> None:
        self.production_adapter = production_adapter or BeautifulSoupParserAdapter()
        self.independent_adapter = independent_adapter or LxmlHtmlParserAdapter()
        self.profile = _copy_profile(profile or DEFAULT_PROFILE)
        _validate_profile(self.profile)
        self.profile_sha256 = _json_sha256(self.profile)

    def validate(
        self,
        value: CanonicalHtmlInput | str,
        *,
        input_sha256: str | None = None,
        source_findings: Sequence[SourceFinding | Mapping[str, Any]] = (),
    ) -> ParseabilityResult:
        if isinstance(value, CanonicalHtmlInput):
            text = value.text
            digest = value.normalized_sha256
            findings: Sequence[SourceFinding | Mapping[str, Any]] = value.source_findings
        else:
            text = value
            digest = input_sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest()
            findings = source_findings

        production_document, production_snapshot, production_error = self._run_adapter(
            self.production_adapter, text
        )
        _, independent_snapshot, independent_error = self._run_adapter(
            self.independent_adapter, text
        )
        differences = _compare_snapshots(
            production_snapshot,
            independent_snapshot,
            production_error,
            independent_error,
        )
        evidence = {
            "schema_version": "1.0",
            "input_sha256": digest,
            "profile": {
                "version": str(self.profile["schema_version"]),
                "sha256": self.profile_sha256,
            },
            "parsers": {
                "production": _parser_evidence(self.production_adapter, production_error),
                "independent": _parser_evidence(self.independent_adapter, independent_error),
            },
            "fingerprints": {
                "production": production_snapshot,
                "independent": independent_snapshot,
            },
            "differences": differences,
            "source_findings": [_finding_dict(finding) for finding in findings],
            "verdict": "failed" if differences else "passed",
        }
        return ParseabilityResult(production_document, evidence)

    def _run_adapter(
        self, adapter: ParserAdapter, text: str
    ) -> tuple[Any | None, dict[str, Any] | None, dict[str, str] | None]:
        try:
            document = adapter.parse(text)
            snapshot = adapter.snapshot(document, self.profile)
            _validate_snapshot_shape(snapshot)
            return document, snapshot, None
        except Exception as error:
            return None, None, {
                "type": type(error).__name__,
                "message": _normalize_exception_message(str(error)),
            }


def _copy_profile(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _validate_profile(profile: Mapping[str, Any]) -> None:
    if set(profile) != {"schema_version", "main_roots", "critical_fragments"}:
        raise ValueError("Parseability profile has unknown or missing fields")
    if not isinstance(profile["schema_version"], str) or not profile["schema_version"]:
        raise ValueError("Parseability profile schema_version is required")
    for name, fields in (
        ("main_roots", {"key", "bs4", "xpath"}),
        ("critical_fragments", {"key", "bs4", "xpath", "attributes"}),
    ):
        entries = profile[name]
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"Parseability profile {name} must be a non-empty array")
        keys: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != fields:
                raise ValueError(f"Invalid {name} entry")
            if not all(isinstance(entry[field], str) and entry[field] for field in ("key", "bs4", "xpath")):
                raise ValueError(f"Invalid selector in {name}")
            if entry["key"] in keys:
                raise ValueError(f"Duplicate parseability profile key: {entry['key']}")
            keys.add(entry["key"])
            if name == "critical_fragments" and (
                not isinstance(entry["attributes"], list)
                or not all(isinstance(item, str) and item for item in entry["attributes"])
                or len(set(entry["attributes"])) != len(entry["attributes"])
            ):
                raise ValueError("Critical fragment attributes must be unique strings")


def _validate_snapshot_shape(snapshot: Mapping[str, Any]) -> None:
    if set(snapshot) != {"body", "main", "pricing_tables", "critical_fragments"}:
        raise ValueError("Parser adapter returned an invalid semantic snapshot")
    if not isinstance(snapshot["pricing_tables"], list) or not isinstance(
        snapshot["critical_fragments"], dict
    ):
        raise ValueError("Parser adapter returned invalid fingerprint collections")


def _parser_evidence(
    adapter: ParserAdapter, error: Mapping[str, str] | None
) -> dict[str, Any]:
    return {
        "name": adapter.name,
        "version": adapter.version,
        "status": "failed" if error else "parsed",
        "error": dict(error) if error else None,
    }


def _finding_dict(finding: SourceFinding | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(finding, SourceFinding):
        return finding.to_dict()
    return json.loads(json.dumps(dict(finding), ensure_ascii=False))


def _compare_snapshots(
    production: Mapping[str, Any] | None,
    independent: Mapping[str, Any] | None,
    production_error: Mapping[str, str] | None,
    independent_error: Mapping[str, str] | None,
) -> list[dict[str, Any]]:
    if production_error or independent_error:
        return [{
            "code": "PARSER_FAILURE",
            "path": "$.parsers",
            "production": dict(production_error) if production_error else None,
            "independent": dict(independent_error) if independent_error else None,
        }]
    assert production is not None and independent is not None
    differences: list[dict[str, Any]] = []
    for key, code, path in (
        ("body", "BODY_TEXT_DIVERGENCE", "$.fingerprints.body"),
        ("main", "MAIN_CONTENT_DIVERGENCE", "$.fingerprints.main"),
        (
            "pricing_tables",
            "PRICING_TABLE_DIVERGENCE",
            "$.fingerprints.pricing_tables",
        ),
    ):
        if production[key] != independent[key]:
            differences.append({
                "code": code,
                "path": path,
                "production": production[key],
                "independent": independent[key],
            })
    critical_keys = sorted(
        set(production["critical_fragments"]) | set(independent["critical_fragments"])
    )
    for key in critical_keys:
        left = production["critical_fragments"].get(key)
        right = independent["critical_fragments"].get(key)
        if left != right:
            differences.append({
                "code": "CRITICAL_FRAGMENT_DIVERGENCE",
                "path": f"$.fingerprints.critical_fragments.{key}",
                "production": left,
                "independent": right,
            })
    return differences


def _normalize_exception_message(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()[:500]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def _bs4_text(element: Tag | BeautifulSoup) -> str:
    values: list[str] = []
    for descendant in element.descendants:
        if not isinstance(descendant, NavigableString):
            continue
        if isinstance(descendant, (Comment, Declaration, Doctype, ProcessingInstruction)):
            continue
        parent = descendant.parent
        excluded = False
        while parent is not None and parent is not element:
            if getattr(parent, "name", None) in EXCLUDED_TEXT_TAGS:
                excluded = True
                break
            parent = parent.parent
        if not excluded and getattr(descendant.parent, "name", None) not in EXCLUDED_TEXT_TAGS:
            values.append(str(descendant))
    return _normalize_text(" ".join(values))


def _lxml_text(element: etree._Element) -> str:
    values = element.xpath(
        ".//text()[not(ancestor::script) and not(ancestor::style) "
        "and not(ancestor::noscript) and not(ancestor::template)]"
    )
    return _normalize_text(" ".join(str(value) for value in values))


def _text_fingerprint(value: str) -> dict[str, Any]:
    return {
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        "token_count": len(value.split()) if value else 0,
    }


def _normalize_attribute(name: str, value: Any) -> str:
    if isinstance(value, (list, tuple)):
        values = [str(item) for item in value]
    else:
        values = str(value).split() if name == "class" else [str(value)]
    if name == "class":
        values = sorted(values)
    return _normalize_text(" ".join(values))


def _fragment_fingerprint(tag: str, text: str, attributes: Mapping[str, str]) -> str:
    return _json_sha256({
        "tag": tag,
        "text": text,
        "attributes": dict(sorted(attributes.items())),
    })


def _bs4_table_snapshot(table: Tag) -> str:
    caption = table.find("caption", recursive=False)
    heading = table.find_previous(HEADING_TAGS)
    rows: list[list[dict[str, str]]] = []
    for row in table.find_all("tr"):
        cells = []
        for cell in row.find_all(("th", "td"), recursive=False):
            cells.append({
                "kind": str(cell.name).lower(),
                "text": _bs4_text(cell),
                "rowspan": str(cell.get("rowspan", "1")),
                "colspan": str(cell.get("colspan", "1")),
            })
        rows.append(cells)
    return _json_sha256({
        "caption": _bs4_text(caption) if caption else "",
        "heading": _bs4_text(heading) if heading else "",
        "rows": rows,
    })


def _lxml_table_snapshot(table: etree._Element) -> str:
    captions = table.xpath("./caption")
    headings = table.xpath("preceding::*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6][1]")
    rows: list[list[dict[str, str]]] = []
    for row in table.xpath(".//tr"):
        cells = []
        for cell in row.xpath("./th | ./td"):
            cells.append({
                "kind": _lxml_tag(cell),
                "text": _lxml_text(cell),
                "rowspan": str(cell.get("rowspan", "1")),
                "colspan": str(cell.get("colspan", "1")),
            })
        rows.append(cells)
    return _json_sha256({
        "caption": _lxml_text(captions[0]) if captions else "",
        "heading": _lxml_text(headings[0]) if headings else "",
        "rows": rows,
    })


def _lxml_tag(element: etree._Element) -> str:
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "BeautifulSoupParserAdapter",
    "DEFAULT_PROFILE",
    "LxmlHtmlParserAdapter",
    "ParseabilityResult",
    "ParserAdapter",
    "ReconstructionParseabilityValidator",
]
