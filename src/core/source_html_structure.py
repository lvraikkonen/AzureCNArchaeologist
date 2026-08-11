"""Deterministic, read-only audit of high-confidence source HTML hierarchy defects."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup, Comment, Tag

from src.core.canonical_input import CanonicalHtmlInput
from src.utils.content.section_extractor import (
    contains_common_section_boundary,
    is_exact_common_section_boundary,
)


SCHEMA_VERSION = "1.0"
AUDITOR_VERSION = (
    "exact-owned-boundaries-static-page-global-ids-and-post-selector-scope-v4"
)

_BEGIN_TAB_CONTROL = re.compile(r"\bBEGIN\s*:\s*TAB-CONTROL\b", re.IGNORECASE)
_END_TAB_CONTROL = re.compile(r"\bEND\s*:\s*TAB-CONTROL\b", re.IGNORECASE)
_SLA_HEADING = re.compile(
    r"^(?:"
    r"支持(?:和|与)服务级别协议|服务级别协议|"
    r"support\s*(?:&|and)\s*(?:sla|service[\s-]+level agreements?)|"
    r"service[\s-]+level agreements?|sla"
    r")$",
    re.IGNORECASE,
)
_SUPPORT_ONLY_HEADING = re.compile(r"^(?:support|支持)$", re.IGNORECASE)
_SUPPORT_CONTACT_PATH = re.compile(
    r"/support/contact(?:[/?#]|$)",
    re.IGNORECASE,
)
_SELECTOR_CLASSES = frozenset({"technical-azure-selector", "pricing-detail-tab"})
_IGNORED_TEXT_TAGS = frozenset({"script", "style", "noscript", "template"})
_FORMAL_SELECTOR_CLASS = "technical-azure-selector"
_STATIC_SELECTOR_CONTROL_CLASSES = frozenset(
    {
        "pricing-detail-tab",
        "region-container",
        "software-kind-container",
    }
)
_STATIC_SELECTOR_CONTROL_ROLES = frozenset(
    {"tab", "tablist", "radiogroup"}
)


class SourceHtmlStructureAuditError(ValueError):
    """Stable failure raised when the audit itself cannot be trusted."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SourceHtmlStructureEvidence:
    line: int
    dom_path: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "dom_path": self.dom_path,
            "description": self.description,
        }


@dataclass(frozen=True)
class SourceHtmlStructureSuggestion:
    action: str
    description: str
    from_line: int
    before_line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "description": self.description,
            "from_line": self.from_line,
            "before_line": self.before_line,
        }


@dataclass(frozen=True)
class SourceHtmlStructureFinding:
    code: str
    severity: str
    blocking: bool
    message: str
    evidence: tuple[SourceHtmlStructureEvidence, ...]
    upstream_suggestion: SourceHtmlStructureSuggestion | None
    safety_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "blocking": self.blocking,
            "message": self.message,
            "evidence": [item.to_dict() for item in self.evidence],
            "upstream_suggestion": (
                self.upstream_suggestion.to_dict()
                if self.upstream_suggestion is not None
                else None
            ),
            "safety_checks": list(self.safety_checks),
        }


@dataclass(frozen=True)
class SourceHtmlStructureAuditResult:
    source_path: str
    source_sha256: str
    size_bytes: int
    product_key: str
    resource_key: str
    language: str
    findings: tuple[SourceHtmlStructureFinding, ...]

    @property
    def blocking_findings(self) -> tuple[SourceHtmlStructureFinding, ...]:
        return tuple(finding for finding in self.findings if finding.blocking)

    @property
    def passed(self) -> bool:
        return not self.blocking_findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "auditor_version": AUDITOR_VERSION,
            "source": {
                "product_key": self.product_key,
                "resource_key": self.resource_key,
                "language": self.language,
                "path": self.source_path,
                "sha256": self.source_sha256,
                "size_bytes": self.size_bytes,
            },
            "passed": self.passed,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass
class _RawDiv:
    classes: frozenset[str]
    start_line: int
    start_column: int
    parent: "_RawDiv | None"
    end_line: int | None = None


class _RawStructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.divs: list[_RawDiv] = []
        self.stack: list[_RawDiv] = []
        self.begin_tab_control_lines: list[int] = []
        self.end_tab_control_lines: list[int] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "div":
            return
        values = {name.lower(): value for name, value in attrs if value is not None}
        classes = frozenset((values.get("class") or "").split())
        line, column = self.getpos()
        frame = _RawDiv(
            classes=classes,
            start_line=line,
            start_column=column,
            parent=self.stack[-1] if self.stack else None,
        )
        self.divs.append(frame)
        self.stack.append(frame)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "div" or not self.stack:
            return
        self.stack.pop().end_line = self.getpos()[0]

    def handle_comment(self, data: str) -> None:
        line = self.getpos()[0]
        if _BEGIN_TAB_CONTROL.search(data):
            self.begin_tab_control_lines.append(line)
        if _END_TAB_CONTROL.search(data):
            self.end_tab_control_lines.append(line)


class SourceHtmlStructureAuditor:
    """Audit only source defects whose DOM ownership and raw line boundary agree."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def audit(
        self, canonical_input: CanonicalHtmlInput
    ) -> SourceHtmlStructureAuditResult:
        source_path = canonical_input.source_path
        absolute_source = (
            source_path if source_path.is_absolute() else self.root / source_path
        ).resolve()
        try:
            relative_source = absolute_source.relative_to(self.root).as_posix()
        except ValueError as error:
            raise SourceHtmlStructureAuditError(
                "source_path_outside_root",
                "Canonical source path is outside the audit root.",
            ) from error

        actual_sha256 = hashlib.sha256(canonical_input.raw_bytes).hexdigest()
        if actual_sha256 != canonical_input.source_sha256:
            raise SourceHtmlStructureAuditError(
                "source_identity_mismatch",
                "Canonical source bytes do not match source_sha256.",
            )
        try:
            decoded = canonical_input.raw_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SourceHtmlStructureAuditError(
                "source_not_strict_utf8",
                "Canonical source bytes are not strict UTF-8.",
            ) from error
        if decoded != canonical_input.text:
            raise SourceHtmlStructureAuditError(
                "source_text_mismatch",
                "Canonical source text does not reproduce the source bytes.",
            )

        raw = _RawStructureParser()
        try:
            raw.feed(canonical_input.text)
            raw.close()
            soup = BeautifulSoup(canonical_input.text, "html.parser")
        except Exception as error:
            raise SourceHtmlStructureAuditError(
                "html_structure_tokenization_failed",
                f"Source HTML structure tokenization failed: {type(error).__name__}.",
            ) from error

        lines = canonical_input.text.splitlines()
        qa_nodes = _exact_qa_nodes(soup)
        findings = [
            *self._duplicate_business_id_findings(soup),
            *self._common_boundary_not_exact_findings(soup, raw),
            *self._post_selector_content_not_exact_findings(soup, raw),
            *self._split_pricing_table_section_findings(soup, raw),
            *self._post_selector_support_section_findings(soup, raw),
            *self._selector_overwrap_findings(soup, raw, lines, qa_nodes),
            *self._pricing_section_overwrap_findings(soup, raw, lines, qa_nodes),
        ]
        findings.sort(key=lambda item: (item.evidence[0].line, item.code))
        return SourceHtmlStructureAuditResult(
            source_path=relative_source,
            source_sha256=canonical_input.source_sha256,
            size_bytes=canonical_input.size_bytes,
            product_key=canonical_input.product_key,
            resource_key=canonical_input.resource_key,
            language=canonical_input.language,
            findings=tuple(findings),
        )

    @staticmethod
    def _duplicate_business_id_findings(
        soup: BeautifulSoup,
    ) -> list[SourceHtmlStructureFinding]:
        """Block duplicate ids only in one proven static page-global boundary."""

        occurrences_by_id: dict[str, list[Tag]] = {}
        for root in _static_page_global_business_content_roots(soup):
            nodes = (
                (root, *root.find_all(True))
                if root.has_attr("id")
                else tuple(root.find_all(True))
            )
            for node in nodes:
                if _inside_ignored_markup(node, root):
                    continue
                raw_identifier = node.get("id")
                if not isinstance(raw_identifier, str):
                    continue
                identifier = raw_identifier.strip()
                if not identifier:
                    continue
                occurrences_by_id.setdefault(identifier, []).append(node)

        findings: list[SourceHtmlStructureFinding] = []
        for identifier, occurrences in occurrences_by_id.items():
            if len(occurrences) < 2:
                continue
            count = len(occurrences)
            evidence = tuple(
                SourceHtmlStructureEvidence(
                    line=_line(node),
                    dom_path=_dom_path(node, stop_at_id=False),
                    description=(
                        f"Duplicate non-empty business-content id "
                        f"{identifier!r}: occurrence {index} of {count}."
                    ),
                )
                for index, node in enumerate(occurrences, start=1)
            )
            first_redundant = occurrences[1]
            original = occurrences[0]
            findings.append(
                SourceHtmlStructureFinding(
                    code="SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT",
                    severity="error",
                    blocking=True,
                    message=(
                        "Static page-global business content contains non-empty id "
                        f"{identifier!r} on {count} elements; HTML id targets "
                        "must be unique."
                    ),
                    evidence=evidence,
                    upstream_suggestion=SourceHtmlStructureSuggestion(
                        action="remove_redundant_or_make_id_unique",
                        description=(
                            f"Upstream should remove redundant {identifier!r} "
                            "id attributes when they are not referenced, or "
                            "assign a unique id to every occurrence and update "
                            "all href, aria-controls, aria-labelledby, for, and "
                            f"data-* references targeting #{identifier}."
                        ),
                        from_line=_line(first_redundant),
                        before_line=_line(original),
                    ),
                    safety_checks=(
                        "sole_static_formal_selector_scope",
                        "no_active_filter_controls",
                        "exact_following_common_section_boundary",
                        "non_empty_duplicate_id",
                        "site_template_scope_excluded",
                    ),
                )
            )
        return findings

    @staticmethod
    def _common_boundary_not_exact_findings(
        soup: BeautifulSoup,
        raw: _RawStructureParser,
    ) -> list[SourceHtmlStructureFinding]:
        context = _post_selector_context(soup)
        if context is None:
            return []
        selector, following = context
        candidate = next(
            (
                node
                for node in following
                if contains_common_section_boundary(node)
            ),
            None,
        )
        if (
            candidate is None
            or is_exact_common_section_boundary(candidate)
            or not _has_balanced_raw_frame(raw, candidate)
        ):
            return []

        more_details = tuple(candidate.select("div.more-detail"))
        owned_sla_sections = tuple(
            section
            for section in (
                candidate,
                *candidate.select("div.pricing-page-section"),
            )
            if _owns_sla_heading(section)
        )
        embedded_styles = tuple(candidate.find_all("style"))
        faq_link_paragraphs: list[Tag] = []
        for faq in more_details:
            for sibling in faq.next_siblings:
                if not isinstance(sibling, Tag):
                    continue
                if sibling.name != "p":
                    continue
                if sibling.find(
                    "a",
                    href=lambda value: isinstance(value, str)
                    and "faq" in value.casefold(),
                ) is not None:
                    faq_link_paragraphs.append(sibling)

        classes = set(candidate.get("class") or ())
        wrapper_spans_common_sections = (
            "pricing-page-section" not in classes
            and bool(more_details)
            and bool(owned_sla_sections)
        )
        evidence_nodes: list[tuple[Tag, str]] = [
            (
                candidate,
                "Direct post-selector node contains a common-section "
                "boundary but is not itself one exact FAQ/SLA boundary.",
            )
        ]
        if embedded_styles:
            evidence_nodes.extend(
                (
                    style,
                    "Embedded style is a sibling of exact FAQ content inside "
                    "the same pricing-page-section.",
                )
                for style in embedded_styles
            )
            evidence_nodes.extend(
                (
                    faq,
                    "Exact div.more-detail FAQ follows embedded stylesheet "
                    "content in the same boundary.",
                )
                for faq in more_details
            )
            suggestion = SourceHtmlStructureSuggestion(
                action="separate_embedded_style_from_common_section",
                description=(
                    "Move the embedded stylesheet out of the business-content "
                    "pricing-page-section and into the page stylesheet or an "
                    "explicit non-business template scope, leaving div.more-detail "
                    "as an exact common-section boundary."
                ),
                from_line=_line(embedded_styles[0]),
                before_line=_line(more_details[0]),
            )
            variant_checks = ("embedded_style_sibling",)
        elif wrapper_spans_common_sections and faq_link_paragraphs:
            evidence_nodes.extend(
                (
                    faq,
                    "Exact div.more-detail FAQ is nested in a classless wrapper.",
                )
                for faq in more_details
            )
            evidence_nodes.extend(
                (
                    paragraph,
                    "FAQ documentation link is visible outside div.more-detail.",
                )
                for paragraph in faq_link_paragraphs
            )
            evidence_nodes.extend(
                (
                    section,
                    "Owned SLA section shares the same classless wrapper with FAQ.",
                )
                for section in owned_sla_sections
            )
            suggestion = SourceHtmlStructureSuggestion(
                action="split_ambiguous_common_section_wrapper",
                description=(
                    "Remove or split the classless wrapper so FAQ and SLA are "
                    "separate exact page-level common-section boundaries, and "
                    "move the FAQ documentation-link paragraph inside "
                    "div.more-detail before its closing tag."
                ),
                from_line=_line(candidate),
                before_line=_line(more_details[0]),
            )
            variant_checks = (
                "visible_content_outside_owned_faq",
                "wrapper_spans_multiple_common_sections",
            )
        elif faq_link_paragraphs and more_details:
            evidence_nodes.extend(
                (
                    faq,
                    "Exact div.more-detail FAQ ends before its documentation link.",
                )
                for faq in more_details
            )
            evidence_nodes.extend(
                (
                    paragraph,
                    "FAQ documentation link is visible outside div.more-detail.",
                )
                for paragraph in faq_link_paragraphs
            )
            faq_frame = _unique_raw_frame(raw, more_details[0])
            suggestion = SourceHtmlStructureSuggestion(
                action="move_visible_content_into_owned_faq",
                description=(
                    "Move the visible FAQ documentation-link paragraph inside "
                    "div.more-detail before its closing tag so the surrounding "
                    "pricing-page-section contains one exact FAQ boundary."
                ),
                from_line=_line(faq_link_paragraphs[0]),
                before_line=(
                    faq_frame.end_line
                    if faq_frame is not None and faq_frame.end_line is not None
                    else _line(more_details[0])
                ),
            )
            variant_checks = ("visible_content_outside_owned_faq",)
        else:
            material_children = tuple(
                child
                for child in candidate.children
                if isinstance(child, Tag)
                and (
                    child.get_text(" ", strip=True)
                    or child.find(
                        ["img", "video", "audio", "table", "iframe"]
                    )
                    is not None
                )
            )
            evidence_nodes.extend(
                (
                    child,
                    "Additional material shares a non-exact boundary with "
                    "FAQ/SLA content.",
                )
                for child in material_children
            )
            suggestion = SourceHtmlStructureSuggestion(
                action="split_ambiguous_common_section_wrapper",
                description=(
                    "Split the wrapper into exact page-level common-section "
                    "boundaries; keep arbitrary material outside FAQ/SLA and "
                    "give it an independently provable ownership boundary."
                ),
                from_line=_line(candidate),
                before_line=_line(
                    more_details[0]
                    if more_details
                    else owned_sla_sections[0]
                ),
            )
            variant_checks = ("mixed_common_section_content",)

        evidence = tuple(
            SourceHtmlStructureEvidence(
                line=_line(node),
                dom_path=_dom_path(node, stop_at_id=False),
                description=description,
            )
            for node, description in sorted(
                _deduplicate_evidence_nodes(evidence_nodes),
                key=lambda item: _line(item[0]),
            )
        )
        return [
            SourceHtmlStructureFinding(
                code="SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT",
                severity="error",
                blocking=True,
                message=(
                    "A direct post-selector node contains FAQ/SLA content plus "
                    "additional material, so it cannot be classified as one exact "
                    "common-section boundary."
                ),
                evidence=evidence,
                upstream_suggestion=suggestion,
                safety_checks=(
                    "direct_sibling_after_final_formal_selector",
                    "contains_exact_common_section_boundary",
                    "common_section_boundary_not_exact",
                    *variant_checks,
                    "raw_balanced_target_element",
                ),
            )
        ]

    @staticmethod
    def _post_selector_content_not_exact_findings(
        soup: BeautifulSoup,
        raw: _RawStructureParser,
    ) -> list[SourceHtmlStructureFinding]:
        context = _post_selector_context(soup)
        if context is None:
            return []
        selector, following = context
        selector_frame = _unique_raw_frame(raw, selector)
        if selector_frame is None or selector_frame.end_line is None:
            return []

        before_common: list[Tag] = []
        exact_common: Tag | None = None
        for node in following:
            if contains_common_section_boundary(node):
                if is_exact_common_section_boundary(node):
                    exact_common = node
                break
            before_common.append(node)
        if exact_common is None:
            return []

        tags_date_nodes = tuple(
            node
            for node in before_common
            if "tags-date" in (node.get("class") or ())
            and _is_material_tag(node)
            and _has_balanced_raw_frame(raw, node)
        )
        if tags_date_nodes:
            evidence = tuple(
                SourceHtmlStructureEvidence(
                    line=_line(node),
                    dom_path=_dom_path(node, stop_at_id=False),
                    description=(
                        "Pricing footnote is a page-level sibling outside the "
                        "formal selector and before the exact FAQ/SLA boundary."
                    ),
                )
                for node in tags_date_nodes
            )
            return [
                SourceHtmlStructureFinding(
                    code=(
                        "SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION"
                    ),
                    severity="error",
                    blocking=True,
                    message=(
                        "A pricing footnote sits outside the selector state that "
                        "provides its pricing-table context."
                    ),
                    evidence=evidence,
                    upstream_suggestion=SourceHtmlStructureSuggestion(
                        action="return_footnote_to_state_panel",
                        description=(
                            "Move the tags-date pricing footnote back into the "
                            "specific selector state/table panel whose markers it "
                            "explains; do not relabel it as page-global content."
                        ),
                        from_line=_line(tags_date_nodes[0]),
                        before_line=selector_frame.end_line,
                    ),
                    safety_checks=(
                        "direct_sibling_after_final_formal_selector",
                        "post_selector_tags_date_footnote",
                        "exact_following_common_section_boundary",
                        "pricing_context_requires_state_ownership",
                        "raw_balanced_target_element",
                    ),
                )
            ]

        script_text = "\n".join(
            script.get_text("\n", strip=False)
            for script in soup.find_all("script")
        )
        classless_business_nodes = tuple(
            node
            for node in before_common
            if node.name == "div"
            and not node.get("class")
            and not node.get("id")
            and _is_material_tag(node)
            and node.find(["h2", "h3"]) is not None
            and _has_balanced_raw_frame(raw, node)
        )
        runtime_targets = tuple(
            node
            for node in before_common
            if node.name == "div"
            and isinstance(node.get("id"), str)
            and str(node.get("id")).strip()
            and not _is_material_tag(node)
            and _runtime_target_is_materialized(
                script_text,
                str(node.get("id")).strip(),
            )
            and _has_balanced_raw_frame(raw, node)
        )
        if (
            not classless_business_nodes
            or len(runtime_targets) < 2
            or "fetch(" not in script_text
        ):
            return []

        evidence_nodes = [
            *(
                (
                    node,
                    "Visible pricing explanation has no exact section or selector "
                    "state ownership.",
                )
                for node in classless_business_nodes
            ),
            *(
                (
                    node,
                    "Empty runtime target is populated by fetched state-dependent "
                    "pricing markup.",
                )
                for node in runtime_targets
            ),
        ]
        evidence = tuple(
            SourceHtmlStructureEvidence(
                line=_line(node),
                dom_path=_dom_path(node, stop_at_id=False),
                description=description,
            )
            for node, description in sorted(
                evidence_nodes,
                key=lambda item: _line(item[0]),
            )
        )
        return [
            SourceHtmlStructureFinding(
                code="SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION",
                severity="error",
                blocking=True,
                message=(
                    "Visible pricing explanations and empty runtime-fetch targets "
                    "sit outside the selector without exact state ownership."
                ),
                evidence=evidence,
                upstream_suggestion=SourceHtmlStructureSuggestion(
                    action="materialize_state_content_inside_selector",
                    description=(
                        "Materialize the fetched pricing tables and explanations "
                        "in the canonical source under their reachable selector "
                        "state panels. Do not treat empty runtime targets or their "
                        "surrounding prose as page-global content."
                    ),
                    from_line=_line(classless_business_nodes[0]),
                    before_line=selector_frame.end_line,
                ),
                safety_checks=(
                    "direct_sibling_after_final_formal_selector",
                    "classless_visible_pricing_content",
                    "multiple_empty_runtime_fetch_targets",
                    "exact_following_common_section_boundary",
                    "pricing_context_requires_state_ownership",
                    "raw_balanced_target_element",
                ),
            )
        ]

    @staticmethod
    def _split_pricing_table_section_findings(
        soup: BeautifulSoup,
        raw: _RawStructureParser,
    ) -> list[SourceHtmlStructureFinding]:
        context = _post_selector_context(soup)
        if context is None:
            return []
        selector, following = context
        content_nodes: list[Tag] = []
        exact_common_found = False
        for node in following:
            if contains_common_section_boundary(node):
                exact_common_found = is_exact_common_section_boundary(node)
                break
            if (
                node.name == "div"
                and "pricing-page-section" in (node.get("class") or ())
            ):
                content_nodes.append(node)

        pairs: list[tuple[Tag, Tag, Tag, Tag]] = []
        for heading_section, table_section in zip(
            content_nodes,
            content_nodes[1:],
        ):
            headings = _owned_heading_nodes(
                heading_section,
                names=("h1", "h2", "h3"),
            )
            heading_tables = _owned_table_nodes(heading_section)
            table_headings = _owned_heading_nodes(
                table_section,
                names=("h1", "h2", "h3"),
            )
            tables = _owned_table_nodes(table_section)
            if (
                headings
                and not heading_tables
                and tables
                and not table_headings
                and _has_balanced_raw_frame(raw, heading_section)
                and _has_balanced_raw_frame(raw, table_section)
            ):
                pairs.append(
                    (
                        heading_section,
                        headings[0],
                        table_section,
                        tables[0],
                    )
                )
        if not pairs:
            return []

        pair_evidence: list[SourceHtmlStructureEvidence] = []
        for heading_section, heading, table_section, _table in pairs:
            pair_evidence.extend(
                (
                    SourceHtmlStructureEvidence(
                        line=_line(heading_section),
                        dom_path=_dom_path(
                            heading_section,
                            stop_at_id=False,
                        ),
                        description=(
                            "Pricing heading is isolated in a section without "
                            "its pricing table."
                        ),
                    ),
                    SourceHtmlStructureEvidence(
                        line=_line(table_section),
                        dom_path=_dom_path(
                            table_section,
                            stop_at_id=False,
                        ),
                        description=(
                            "Adjacent pricing-table section has no owned h1/h2/h3 "
                            f"heading; preceding heading is "
                            f"{_normalized_text(heading)!r}."
                        ),
                    ),
                )
            )
        findings = [
            SourceHtmlStructureFinding(
                code=(
                    "SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING"
                ),
                severity="error",
                blocking=True,
                message=(
                    f"{len(pairs)} pricing table section(s) are split from their "
                    "owned headings into adjacent sibling sections."
                ),
                evidence=tuple(pair_evidence),
                upstream_suggestion=SourceHtmlStructureSuggestion(
                    action="merge_heading_with_pricing_table_section",
                    description=(
                        "For every affected pair, place the heading and its table "
                        "in the same pricing-page-section while preserving their "
                        "physical order and pricing-state ownership."
                    ),
                    from_line=_line(pairs[0][2]),
                    before_line=_line(pairs[0][0]),
                ),
                safety_checks=(
                    "direct_sibling_after_final_formal_selector",
                    "adjacent_pricing_section_pair",
                    "heading_section_has_no_table",
                    "table_section_has_no_owned_heading",
                    "raw_balanced_target_element",
                ),
            )
        ]
        if not exact_common_found:
            evidence_nodes = [selector]
            evidence_nodes.extend(content_nodes)
            findings.append(
                SourceHtmlStructureFinding(
                    code=(
                        "SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY"
                    ),
                    severity="error",
                    blocking=True,
                    message=(
                        "Post-selector pricing content reaches the end of the "
                        "page without an exact FAQ/SLA common-section boundary."
                    ),
                    evidence=tuple(
                        SourceHtmlStructureEvidence(
                            line=_line(node),
                            dom_path=_dom_path(node, stop_at_id=False),
                            description=(
                                "Final formal selector begins the unbounded "
                                "post-selector sequence."
                                if node is selector
                                else "Post-selector pricing section precedes "
                                "page termination without an exact common boundary."
                            ),
                        )
                        for node in evidence_nodes
                    ),
                    upstream_suggestion=SourceHtmlStructureSuggestion(
                        action="restore_exact_common_section_terminal",
                        description=(
                            "After repairing the pricing-section ownership, "
                            "restore an exact page-level FAQ/SLA terminal boundary. "
                            "If the source intentionally has no common section, "
                            "upstream must provide an explicit agreed terminal "
                            "marker instead of relying on inferred end-of-page."
                        ),
                        from_line=_line(content_nodes[-1]),
                        before_line=_line(selector),
                    ),
                    safety_checks=(
                        "direct_sibling_after_final_formal_selector",
                        "post_selector_pricing_sections_present",
                        "split_heading_table_sections_present",
                        "no_exact_faq_or_sla_boundary",
                        "raw_balanced_target_element",
                    ),
                )
            )
        return findings

    @staticmethod
    def _post_selector_support_section_findings(
        soup: BeautifulSoup,
        raw: _RawStructureParser,
    ) -> list[SourceHtmlStructureFinding]:
        context = _post_selector_context(soup)
        if context is None:
            return []
        selector, following = context
        first_material = next(
            (node for node in following if _is_material_tag(node)),
            None,
        )
        if (
            first_material is None
            or first_material.name != "div"
            or "pricing-page-section"
            not in (first_material.get("class") or ())
            or first_material.select_one(
                f"div.{_FORMAL_SELECTOR_CLASS}"
            )
            is not None
            or not _has_balanced_raw_frame(raw, selector)
            or not _has_balanced_raw_frame(raw, first_material)
        ):
            return []
        headings = _owned_heading_nodes(first_material)
        support_headings = tuple(
            heading
            for heading in headings
            if _SUPPORT_ONLY_HEADING.fullmatch(_normalized_text(heading))
        )
        support_links = tuple(
            link
            for link in first_material.find_all("a", href=True)
            if _SUPPORT_CONTACT_PATH.search(str(link.get("href", "")))
        )
        later_exact_boundary = any(
            contains_common_section_boundary(node)
            and is_exact_common_section_boundary(node)
            for node in following[following.index(first_material) + 1 :]
        )
        if (
            len(headings) != 1
            or len(support_headings) != 1
            or not support_links
            or later_exact_boundary
        ):
            return []

        heading = support_headings[0]
        link = support_links[0]
        evidence = (
            SourceHtmlStructureEvidence(
                line=_line(selector),
                dom_path=_dom_path(selector, stop_at_id=False),
                description="Final formal selector ends before support-only content.",
            ),
            SourceHtmlStructureEvidence(
                line=_line(first_material),
                dom_path=_dom_path(first_material, stop_at_id=False),
                description=(
                    "Direct pricing-page-section is visible but is not an exact "
                    "FAQ/SLA common-section boundary."
                ),
            ),
            SourceHtmlStructureEvidence(
                line=_line(heading),
                dom_path=_dom_path(heading, stop_at_id=False),
                description=(
                    f"Owned heading is support-only: "
                    f"{_normalized_text(heading)!r}."
                ),
            ),
            SourceHtmlStructureEvidence(
                line=_line(link),
                dom_path=_dom_path(link, stop_at_id=False),
                description="Section contains an explicit Azure support contact link.",
            ),
        )
        return [
            SourceHtmlStructureFinding(
                code=(
                    "SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED"
                ),
                severity="error",
                blocking=True,
                message=(
                    "A support-only section directly follows the final selector "
                    "but cannot be classified as baseContent or an exact "
                    "FAQ/SLA common section."
                ),
                evidence=evidence,
                upstream_suggestion=SourceHtmlStructureSuggestion(
                    action="clarify_support_section_ownership",
                    description=(
                        "Upstream must declare whether this section is pricing "
                        "business content or a common SLA/Qa section. If it is "
                        "SLA content, use the agreed exact heading/wrapper and "
                        "include the owned SLA material; otherwise move it into "
                        "an explicit business-content boundary. Do not broaden "
                        "matching to every heading named Support."
                    ),
                    from_line=_line(first_material),
                    before_line=_line(selector),
                ),
                safety_checks=(
                    "direct_sibling_after_final_formal_selector",
                    "owned_support_only_heading",
                    "support_contact_link_present",
                    "no_exact_faq_or_sla_boundary",
                    "no_nested_formal_selector",
                    "raw_balanced_target_element",
                ),
            )
        ]

    def _selector_overwrap_findings(
        self,
        soup: BeautifulSoup,
        raw: _RawStructureParser,
        lines: list[str],
        qa_nodes: tuple[Tag, ...],
    ) -> list[SourceHtmlStructureFinding]:
        findings: list[SourceHtmlStructureFinding] = []
        for selector in _selector_nodes(soup):
            selector_line = _line(selector)
            descendants = tuple(
                node
                for node in qa_nodes
                if selector in node.parents and _line(node) > selector_line
            )
            if not descendants:
                continue
            first = min(descendants, key=_line)
            top_child = _top_child_under(selector, first)
            boundary_lines = [
                line
                for line in raw.end_tab_control_lines
                if selector_line < line < _line(top_child)
            ]
            if not boundary_lines:
                continue
            boundary_line = max(boundary_lines)
            frame = _unique_raw_frame(raw, selector)
            suggestion = _safe_suggestion(
                frame,
                before_line=_line(top_child),
                lines=lines,
                description=(
                    "Move the selector's existing closing </div> before the first "
                    "exact FAQ/SLA section following END: TAB-CONTROL."
                ),
            )
            evidence = (
                SourceHtmlStructureEvidence(
                    selector_line,
                    _dom_path(selector),
                    "Formal pricing selector starts here.",
                ),
                SourceHtmlStructureEvidence(
                    boundary_line,
                    _dom_path(selector),
                    "END: TAB-CONTROL occurs while the selector is still open.",
                ),
                SourceHtmlStructureEvidence(
                    _line(first),
                    _dom_path(first),
                    _qa_description(first),
                ),
                SourceHtmlStructureEvidence(
                    frame.end_line if frame and frame.end_line else _line(first),
                    _dom_path(selector),
                    "Observed selector closing boundary.",
                ),
            )
            checks = [
                "dom_exact_qa_or_owned_sla",
                "tab_control_boundary_comment",
            ]
            if suggestion is not None:
                checks.extend(
                    [
                        "raw_balanced_target_element",
                        "standalone_closing_tag_line",
                        "relocation_preserves_content_order",
                    ]
                )
            findings.append(
                SourceHtmlStructureFinding(
                    code="SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL",
                    severity="error",
                    blocking=True,
                    message=(
                        "A formal pricing selector remains open past END: "
                        "TAB-CONTROL and contains an exact FAQ/SLA section."
                    ),
                    evidence=evidence,
                    upstream_suggestion=suggestion,
                    safety_checks=tuple(checks),
                )
            )
        return findings

    def _pricing_section_overwrap_findings(
        self,
        soup: BeautifulSoup,
        raw: _RawStructureParser,
        lines: list[str],
        qa_nodes: tuple[Tag, ...],
    ) -> list[SourceHtmlStructureFinding]:
        findings: list[SourceHtmlStructureFinding] = []
        seen_sections: set[int] = set()
        for selector in _selector_nodes(soup):
            section = selector.find_parent("div", class_="pricing-page-section")
            if not isinstance(section, Tag) or id(section) in seen_sections:
                continue
            seen_sections.add(id(section))
            selector_line = _line(selector)
            later_qa = tuple(
                node
                for node in qa_nodes
                if section in node.parents
                and selector not in node.parents
                and _line(node) > selector_line
            )
            intro = _intro_node_before(section, selector)
            if not later_qa or intro is None:
                continue
            begin_lines = [
                line
                for line in raw.begin_tab_control_lines
                if _line(section) < line < selector_line
            ]
            if not begin_lines:
                continue
            before_line = max(begin_lines)
            frame = _unique_raw_frame(raw, section)
            suggestion = _safe_suggestion(
                frame,
                before_line=before_line,
                lines=lines,
                description=(
                    "Move the overwrapping pricing section's existing closing "
                    "</div> before BEGIN: TAB-CONTROL."
                ),
            )
            blocking = suggestion is None
            first_qa = min(later_qa, key=_line)
            evidence = (
                SourceHtmlStructureEvidence(
                    _line(section),
                    _dom_path(section),
                    "Pricing page section starts before introductory content.",
                ),
                SourceHtmlStructureEvidence(
                    _line(intro),
                    _dom_path(intro),
                    "Non-empty introductory content belongs before the selector.",
                ),
                SourceHtmlStructureEvidence(
                    selector_line,
                    _dom_path(selector),
                    "Formal pricing selector is nested in the same section.",
                ),
                SourceHtmlStructureEvidence(
                    _line(first_qa),
                    _dom_path(first_qa),
                    _qa_description(first_qa),
                ),
                SourceHtmlStructureEvidence(
                    frame.end_line if frame and frame.end_line else _line(first_qa),
                    _dom_path(section),
                    "Observed overwrapping section closing boundary.",
                ),
            )
            checks = [
                "dom_exact_qa_or_owned_sla",
                "intro_precedes_selector",
                "tab_control_boundary_comment",
            ]
            if suggestion is not None:
                checks.extend(
                    [
                        "raw_balanced_target_element",
                        "standalone_closing_tag_line",
                        "relocation_preserves_content_order",
                    ]
                )
            findings.append(
                SourceHtmlStructureFinding(
                    code=(
                        "SOURCE_HTML_PRICING_SECTION_OVERWRAPS_SELECTOR_AND_QA"
                    ),
                    severity="error" if blocking else "warning",
                    blocking=blocking,
                    message=(
                        "One pricing-page-section overwraps introductory content, "
                        "the pricing selector, and a later exact FAQ/SLA section."
                    ),
                    evidence=evidence,
                    upstream_suggestion=suggestion,
                    safety_checks=tuple(checks),
                )
            )
        return findings


def _outermost_formal_selectors(soup: BeautifulSoup) -> tuple[Tag, ...]:
    return tuple(
        selector
        for selector in soup.select(f"div.{_FORMAL_SELECTOR_CLASS}")
        if not any(
            isinstance(parent, Tag)
            and _FORMAL_SELECTOR_CLASS in (parent.get("class") or ())
            for parent in selector.parents
        )
    )


def _post_selector_context(
    soup: BeautifulSoup,
) -> tuple[Tag, tuple[Tag, ...]] | None:
    selectors = _outermost_formal_selectors(soup)
    if not selectors:
        return None
    selector = selectors[-1]
    parent = selector.parent
    if (
        not isinstance(parent, Tag)
        or "pure-content" not in (parent.get("class") or ())
    ):
        return None
    following: list[Tag] = []
    for sibling in selector.next_siblings:
        if isinstance(sibling, Comment):
            continue
        if not isinstance(sibling, Tag):
            if str(sibling).strip():
                return None
            continue
        if sibling.name in {"script", "style", "template"}:
            continue
        following.append(sibling)
    return selector, tuple(following)


def _is_material_tag(node: Tag) -> bool:
    return bool(
        node.get_text(" ", strip=True)
        or node.find(["img", "video", "audio", "table", "iframe"])
        is not None
    )


def _normalized_text(node: Tag) -> str:
    return unicodedata.normalize(
        "NFC",
        re.sub(r"\s+", " ", node.get_text(" ", strip=True)),
    ).strip(" \t\r\n:：")


def _owned_heading_nodes(
    section: Tag,
    *,
    names: tuple[str, ...] = ("h1", "h2", "h3", "h4", "h5", "h6"),
) -> tuple[Tag, ...]:
    return tuple(
        heading
        for heading in section.find_all(names)
        if heading.find_parent("div", class_="pricing-page-section")
        is section
    )


def _owned_table_nodes(section: Tag) -> tuple[Tag, ...]:
    return tuple(
        table
        for table in section.find_all("table")
        if table.find_parent("div", class_="pricing-page-section")
        is section
    )


def _has_balanced_raw_frame(
    raw: _RawStructureParser,
    node: Tag,
) -> bool:
    frame = _unique_raw_frame(raw, node)
    return frame is not None and frame.end_line is not None


def _runtime_target_is_materialized(
    script_text: str,
    identifier: str,
) -> bool:
    target = re.escape(identifier)
    return bool(
        re.search(
            rf"querySelector\(\s*['\"]#{target}['\"]\s*\)\.innerHTML",
            script_text,
        )
    )


def _deduplicate_evidence_nodes(
    values: Iterable[tuple[Tag, str]],
) -> tuple[tuple[Tag, str], ...]:
    found: list[tuple[Tag, str]] = []
    seen: set[int] = set()
    for node, description in values:
        identity = id(node)
        if identity in seen:
            continue
        seen.add(identity)
        found.append((node, description))
    return tuple(found)


def _static_page_global_business_content_roots(
    soup: BeautifulSoup,
) -> tuple[Tag, ...]:
    """Return the sole selector proven to be one static page-global fragment.

    The scope intentionally mirrors the structural classification used by the
    page-global/baseContent resolver, but stops before its id validation. A
    filtered selector is state-scoped content: repeated ids in different
    region/software/category panels are not duplicates inside one CMS fragment.
    """

    selectors = _outermost_formal_selectors(soup)
    if len(selectors) != 1:
        return ()

    selector = selectors[0]
    parent = selector.parent
    if (
        not isinstance(parent, Tag)
        or "pure-content" not in (parent.get("class") or ())
        or _has_active_selector_controls(selector)
    ):
        return ()

    found_common_boundary = False
    for sibling in selector.next_siblings:
        if isinstance(sibling, Comment):
            continue
        if not isinstance(sibling, Tag):
            if str(sibling).strip():
                return ()
            continue
        if sibling.name in {"script", "style", "template"}:
            continue
        if contains_common_section_boundary(sibling):
            if not is_exact_common_section_boundary(sibling):
                return ()
            found_common_boundary = True
            break
        if (
            sibling.get_text(" ", strip=True)
            or sibling.find(["img", "video", "audio", "table", "iframe"])
            is not None
        ):
            return ()

    return (selector,) if found_common_boundary else ()


def _has_active_selector_controls(selector: Tag) -> bool:
    nodes = (selector, *selector.find_all(True))
    for node in nodes:
        classes = {
            str(value).casefold() for value in node.get("class", ())
        }
        if classes.intersection(_STATIC_SELECTOR_CONTROL_CLASSES):
            return True
        if node.name in {"select", "form", "button"}:
            return True
        if (
            node.name == "input"
            and str(node.get("type", "")).casefold()
            in {"radio", "checkbox"}
        ):
            return True
        if (
            str(node.get("role", "")).casefold()
            in _STATIC_SELECTOR_CONTROL_ROLES
        ):
            return True
    return False


def _inside_ignored_markup(node: Tag, root: Tag) -> bool:
    if node.name in _IGNORED_TEXT_TAGS:
        return True
    for parent in node.parents:
        if parent is root:
            return False
        if isinstance(parent, Tag) and parent.name in _IGNORED_TEXT_TAGS:
            return True
    return False


def _selector_nodes(soup: BeautifulSoup) -> tuple[Tag, ...]:
    return tuple(
        node
        for node in soup.find_all("div")
        if set(node.get("class") or []) & _SELECTOR_CLASSES
    )


def _exact_qa_nodes(soup: BeautifulSoup) -> tuple[Tag, ...]:
    candidates: list[Tag] = list(soup.select("div.more-detail"))
    for section in soup.select("div.pricing-page-section"):
        if _owns_sla_heading(section):
            candidates.append(section)
    identities = {id(candidate) for candidate in candidates}
    return tuple(node for node in soup.find_all("div") if id(node) in identities)


def _owns_sla_heading(section: Tag) -> bool:
    for heading in section.find_all(("h1", "h2", "h3", "h4", "h5", "h6")):
        owner = heading.find_parent("div", class_="pricing-page-section")
        text = unicodedata.normalize(
            "NFC", re.sub(r"\s+", " ", heading.get_text(" ", strip=True))
        ).strip(" \t\r\n:：")
        if owner is section and _SLA_HEADING.fullmatch(text):
            return True
    return False


def _intro_node_before(section: Tag, selector: Tag) -> Tag | None:
    selector_line = _line(selector)
    for node in section.find_all(("p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol")):
        if _line(node) >= selector_line:
            continue
        if any(
            isinstance(parent, Tag) and parent.name in _IGNORED_TEXT_TAGS
            for parent in node.parents
        ):
            continue
        if re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip():
            return node
    return None


def _top_child_under(ancestor: Tag, descendant: Tag) -> Tag:
    current = descendant
    while isinstance(current.parent, Tag) and current.parent is not ancestor:
        current = current.parent
    return current


def _unique_raw_frame(
    raw: _RawStructureParser, node: Tag
) -> _RawDiv | None:
    classes = frozenset(node.get("class") or [])
    matches = [
        frame
        for frame in raw.divs
        if frame.start_line == _line(node) and frame.classes == classes
    ]
    return matches[0] if len(matches) == 1 else None


def _safe_suggestion(
    frame: _RawDiv | None,
    *,
    before_line: int,
    lines: list[str],
    description: str,
) -> SourceHtmlStructureSuggestion | None:
    if (
        frame is None
        or frame.end_line is None
        or frame.end_line <= before_line
        or frame.end_line > len(lines)
        or lines[frame.end_line - 1].strip().lower() != "</div>"
    ):
        return None
    return SourceHtmlStructureSuggestion(
        action="relocate_existing_closing_tag",
        description=description,
        from_line=frame.end_line,
        before_line=before_line,
    )


def _line(node: Tag) -> int:
    value = getattr(node, "sourceline", None)
    return int(value) if isinstance(value, int) and value > 0 else 1


def _qa_description(node: Tag) -> str:
    if "more-detail" in set(node.get("class") or []):
        return "Exact div.more-detail FAQ is nested across the expected boundary."
    return "Exact pricing section owns an SLA heading across the expected boundary."


def _dom_path(node: Tag, *, stop_at_id: bool = True) -> str:
    parts: list[str] = []
    current: Tag | None = node
    while isinstance(current, Tag) and current.name != "[document]":
        part = current.name
        identifier = current.get("id")
        if isinstance(identifier, str) and identifier:
            part += f"#{identifier}"
            if stop_at_id:
                parts.append(part)
                break
        classes = sorted(str(value) for value in (current.get("class") or []))
        if classes:
            part += "".join(f".{value}" for value in classes)
        parent = current.parent
        if isinstance(parent, Tag):
            siblings = [
                sibling
                for sibling in parent.find_all(current.name, recursive=False)
                if isinstance(sibling, Tag)
            ]
            if len(siblings) > 1:
                part += f":nth-of-type({siblings.index(current) + 1})"
        parts.append(part)
        current = parent if isinstance(parent, Tag) else None
    return " > ".join(reversed(parts))


__all__ = [
    "AUDITOR_VERSION",
    "SCHEMA_VERSION",
    "SourceHtmlStructureAuditError",
    "SourceHtmlStructureAuditResult",
    "SourceHtmlStructureAuditor",
    "SourceHtmlStructureEvidence",
    "SourceHtmlStructureFinding",
    "SourceHtmlStructureSuggestion",
]
