from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest
from jsonschema import Draft202012Validator

from src.core.canonical_input import (
    CanonicalHtmlInput,
    CanonicalInputLoader,
    InputAssuranceError,
)
from src.core.reconstruction_parseability import (
    ReconstructionParseabilityValidator,
)


class FakeProductManager:
    def __init__(self, definitions: Mapping[str, dict[str, Any]]) -> None:
        self.definitions = dict(definitions)

    def get_product_config(self, product_key: str) -> dict[str, Any]:
        return copy.deepcopy(self.definitions[product_key])


def _definition(snapshot_path: str = "pricing/details/sample/index.html") -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "product_key": "sample",
        "display_name": "Sample",
        "slug": "sample",
        "page_model": "FlexibleContentPage",
        "capability_status": "supported",
        "catalog_categories": ["integration"],
        "extraction": {"semantic_strategy": "simple_static"},
        "sources": {
            "zh-cn": {
                "availability": "available",
                "snapshot_path": snapshot_path,
                "url": "https://example.test/pricing/sample/",
            },
            "en-us": {
                "availability": "available",
                "snapshot_path": snapshot_path,
                "url": "https://example.test/en-us/pricing/sample/",
            },
        },
    }


def _write_pair(
    root: Path,
    value: bytes,
    *,
    definition: dict[str, Any] | None = None,
    language: str = "zh-cn",
) -> tuple[dict[str, Any], Path, Path]:
    definition = definition or _definition()
    source = (
        root
        / "data"
        / "current_prod_html"
        / language
        / definition["sources"][language]["snapshot_path"]
    )
    normalized = root / "data" / "prod-html" / language / "pricing" / "sample.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    normalized.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(value)
    normalized.write_bytes(value)
    return definition, source, normalized


def _loader(
    root: Path,
    definition: dict[str, Any],
    *,
    max_input_bytes: int | None = 5 * 1024 * 1024,
) -> CanonicalInputLoader:
    return CanonicalInputLoader(
        root,
        FakeProductManager({"sample": definition}),  # type: ignore[arg-type]
        max_input_bytes,
    )


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_canonical_loader_accepts_only_derived_byte_identical_input(tmp_path: Path) -> None:
    value = b"<meta charset='utf-8'><html><body>ok</body></html>"
    definition, source, normalized = _write_pair(tmp_path, value)
    loaded = _loader(tmp_path, definition).load(
        "sample", "zh-cn", expected_sha256=_digest(value)
    )

    assert loaded.source_path == source
    assert loaded.normalized_path == normalized
    assert loaded.source_sha256 == loaded.normalized_sha256 == loaded.expected_sha256
    assert loaded.raw_bytes == value
    assert loaded.text == value.decode("utf-8")
    assert loaded.source_findings == ()


def test_canonical_loader_preserves_utf8_bom_bytes_and_text(tmp_path: Path) -> None:
    value = b"\xef\xbb\xbf<meta charset='utf-8'><p>\xe4\xb8\xad\xe6\x96\x87</p>"
    definition, _, _ = _write_pair(tmp_path, value)
    loaded = _loader(tmp_path, definition).load(
        "sample", "zh-cn", expected_sha256=_digest(value)
    )

    assert loaded.has_utf8_bom is True
    assert loaded.raw_bytes.startswith(b"\xef\xbb\xbf")
    assert loaded.text.startswith("\ufeff")
    assert loaded.normalized_sha256 == _digest(value)


def test_canonical_loader_rejects_invalid_utf8_without_fallback(tmp_path: Path) -> None:
    value = b"<html><body>\x80</body></html>"
    definition, _, _ = _write_pair(tmp_path, value)

    with pytest.raises(InputAssuranceError) as captured:
        _loader(tmp_path, definition).load(
            "sample", "zh-cn", expected_sha256=_digest(value)
        )
    assert captured.value.code == "INVALID_UTF8"


@pytest.mark.parametrize(
    "value",
    [
        "<meta charset='gbk'><p>中文</p>".encode("gbk"),
        b"<meta charset='iso-8859-1'><p>caf\xe9</p>",
    ],
)
def test_canonical_loader_rejects_legacy_encoded_inputs(
    tmp_path: Path, value: bytes
) -> None:
    definition, _, _ = _write_pair(tmp_path, value)
    with pytest.raises(InputAssuranceError) as captured:
        _loader(tmp_path, definition).load(
            "sample", "zh-cn", expected_sha256=_digest(value)
        )
    assert captured.value.code == "INVALID_UTF8"


def test_canonical_loader_rejects_source_normalized_drift(tmp_path: Path) -> None:
    value = b"<meta charset='utf-8'><p>source</p>"
    definition, _, normalized = _write_pair(tmp_path, value)
    normalized.write_bytes(b"<meta charset='utf-8'><p>changed</p>")

    with pytest.raises(InputAssuranceError) as captured:
        _loader(tmp_path, definition).load("sample", "zh-cn")
    assert captured.value.code == "SOURCE_NORMALIZED_HASH_MISMATCH"


def test_canonical_loader_rejects_frozen_hash_drift(tmp_path: Path) -> None:
    value = b"<meta charset='utf-8'><p>source</p>"
    definition, _, _ = _write_pair(tmp_path, value)

    with pytest.raises(InputAssuranceError) as captured:
        _loader(tmp_path, definition).load("sample", "zh-cn", expected_sha256="0" * 64)
    assert captured.value.code == "NORMALIZED_INPUT_HASH_MISMATCH"


def test_canonical_loader_rejects_source_path_escape(tmp_path: Path) -> None:
    definition = _definition("../../outside.html")
    outside = tmp_path / "data" / "outside.html"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("<p>outside</p>", encoding="utf-8")
    normalized = tmp_path / "data/prod-html/zh-cn/pricing/sample.html"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalized.write_text("<p>outside</p>", encoding="utf-8")

    with pytest.raises(InputAssuranceError) as captured:
        _loader(tmp_path, definition).load("sample", "zh-cn")
    assert captured.value.code == "CANONICAL_INPUT_PATH_MISMATCH"


def test_canonical_loader_rejects_symlinked_source(tmp_path: Path) -> None:
    value = b"<meta charset='utf-8'><p>source</p>"
    definition, source, normalized = _write_pair(tmp_path, value)
    source.unlink()
    external = tmp_path / "external.html"
    external.write_bytes(value)
    source.symlink_to(external)
    assert normalized.read_bytes() == value

    with pytest.raises(InputAssuranceError) as captured:
        _loader(tmp_path, definition).load("sample", "zh-cn")
    assert captured.value.code == "CANONICAL_INPUT_SYMLINK_FORBIDDEN"


def test_canonical_loader_enforces_in_memory_profile(tmp_path: Path) -> None:
    value = b"<p>1234567890</p>"
    definition, _, _ = _write_pair(tmp_path, value)
    with pytest.raises(InputAssuranceError) as captured:
        _loader(tmp_path, definition, max_input_bytes=8).load("sample", "zh-cn")
    assert captured.value.code == "INPUT_EXCEEDS_IN_MEMORY_PROFILE"


def test_charset_mismatch_is_a_finding_not_a_decode_failure(tmp_path: Path) -> None:
    value = "<meta charset='gbk'><p>中文</p>".encode("utf-8")
    definition, _, _ = _write_pair(tmp_path, value)
    loaded = _loader(tmp_path, definition).load(
        "sample", "zh-cn", expected_sha256=_digest(value)
    )

    assert [finding.code for finding in loaded.source_findings] == [
        "SOURCE_CHARSET_DECLARATION_NOT_UTF8"
    ]
    assert loaded.text.endswith("<p>中文</p>")


def test_conflicting_charset_and_bom_emit_deterministic_findings(tmp_path: Path) -> None:
    value = (
        b"\xef\xbb\xbf<meta charset='utf-8'>"
        b"<meta http-equiv='Content-Type' content='text/html; charset=gbk'>"
        b"<p>ok</p>"
    )
    definition, _, _ = _write_pair(tmp_path, value)
    loaded = _loader(tmp_path, definition).load("sample", "zh-cn")

    assert [finding.code for finding in loaded.source_findings] == [
        "SOURCE_CHARSET_BOM_CONFLICT",
        "SOURCE_CHARSET_DECLARATIONS_CONFLICT",
        "SOURCE_CHARSET_DECLARATION_NOT_UTF8",
    ]
    declarations = loaded.source_findings[0].to_dict()["evidence"]["declarations"]
    assert [item["normalized"] for item in declarations] == ["utf-8", "gbk"]


def _valid_html() -> bytes:
    return """<!doctype html>
<html><head><title>Sample pricing</title>
<meta charset="utf-8"><meta name="description" content="Rates">
</head><body><div class="pure-content"><tags ms.service="sample"></tags>
<h2>Compute rates</h2><table><caption>Compute</caption>
<tr><th rowspan="1">SKU</th><th>Price</th></tr>
<tr><td>A</td><td>¥1</td></tr></table></div></body></html>""".encode("utf-8")


def _canonical(tmp_path: Path, value: bytes | None = None) -> CanonicalHtmlInput:
    content = value or _valid_html()
    definition, _, _ = _write_pair(tmp_path, content)
    return _loader(tmp_path, definition).load(
        "sample", "zh-cn", expected_sha256=_digest(content)
    )


def test_default_independent_parsers_produce_deterministic_evidence(
    tmp_path: Path,
) -> None:
    canonical = _canonical(tmp_path)
    validator = ReconstructionParseabilityValidator()

    first = validator.validate(canonical)
    second = validator.validate(canonical)

    assert first.passed is True
    assert first.production_soup is not None
    assert first.evidence == second.evidence
    assert first.evidence["input_sha256"] == canonical.normalized_sha256
    assert first.evidence["verdict"] == "passed"


def _snapshot() -> dict[str, Any]:
    empty_hash = hashlib.sha256(b"").hexdigest()
    return {
        "body": {"sha256": empty_hash, "token_count": 0},
        "main": {"selector": "body", "sha256": empty_hash, "token_count": 0},
        "pricing_tables": [],
        "critical_fragments": {
            "title": {"count": 0, "fingerprints": []},
        },
    }


class StaticAdapter:
    def __init__(
        self,
        name: str,
        snapshot: Mapping[str, Any],
        *,
        failure: Exception | None = None,
    ) -> None:
        self.name = name
        self.version = "test-1"
        self.value = copy.deepcopy(dict(snapshot))
        self.failure = failure
        self.document = object()

    def parse(self, text: str) -> object:
        if self.failure:
            raise self.failure
        return self.document

    def snapshot(self, document: object, profile: Mapping[str, Any]) -> dict[str, Any]:
        return copy.deepcopy(self.value)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda value: value["body"].update({"token_count": 1}), "BODY_TEXT_DIVERGENCE"),
        (
            lambda value: value["main"].update({"selector": "pure_content"}),
            "MAIN_CONTENT_DIVERGENCE",
        ),
        (
            lambda value: value["pricing_tables"].append("1" * 64),
            "PRICING_TABLE_DIVERGENCE",
        ),
        (
            lambda value: value["critical_fragments"]["title"].update({"count": 1}),
            "CRITICAL_FRAGMENT_DIVERGENCE",
        ),
    ],
)
def test_material_parser_divergence_fails_closed(
    mutation: Any, expected_code: str
) -> None:
    production = _snapshot()
    independent = copy.deepcopy(production)
    mutation(independent)
    production_adapter = StaticAdapter("production", production)
    result = ReconstructionParseabilityValidator(
        production_adapter=production_adapter,
        independent_adapter=StaticAdapter("independent", independent),
    ).validate("<p>x</p>")

    assert result.passed is False
    assert result.production_soup is production_adapter.document
    assert expected_code in {item["code"] for item in result.evidence["differences"]}


def test_parser_failure_is_explicit_and_does_not_claim_success() -> None:
    snapshot = _snapshot()
    result = ReconstructionParseabilityValidator(
        production_adapter=StaticAdapter("production", snapshot),
        independent_adapter=StaticAdapter(
            "independent", snapshot, failure=ValueError("cannot parse")
        ),
    ).validate("<p>x</p>")

    assert result.passed is False
    assert result.evidence["verdict"] == "failed"
    assert result.evidence["differences"][0]["code"] == "PARSER_FAILURE"
    assert result.evidence["parsers"]["independent"]["status"] == "failed"


def test_generated_findings_and_parseability_evidence_match_schemas(
    tmp_path: Path,
) -> None:
    value = "<meta charset='gbk'><body><div class='pure-content'>中文</div></body>".encode(
        "utf-8"
    )
    canonical = _canonical(tmp_path, value)
    result = ReconstructionParseabilityValidator().validate(canonical)
    root = Path(__file__).resolve().parents[1]
    finding_schema = json.loads(
        (root / "schemas/source-finding-1.0.schema.json").read_text(encoding="utf-8")
    )
    evidence_schema = json.loads(
        (root / "schemas/reconstruction-parseability-1.0.schema.json").read_text(
            encoding="utf-8"
        )
    )

    Draft202012Validator(finding_schema).validate(
        canonical.source_findings[0].to_dict()
    )
    Draft202012Validator(evidence_schema).validate(result.evidence)
