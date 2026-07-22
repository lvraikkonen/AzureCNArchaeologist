"""Closed-world loading for formal canonical HTML inputs.

The loader deliberately has no path override.  A caller supplies only the
Product Definition identity and, when available, the hash frozen by planning.
Source Snapshot and Normalized Input paths are derived from that definition,
read as bytes, and proved identical before any parser sees the document.
"""

from __future__ import annotations

import codecs
import hashlib
import os
import stat
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from src.core.product_catalog import normalized_input_path
from src.core.product_manager import ProductManager
from src.core.support_article_versions import (
    get_historical_version,
    historical_normalized_input_path,
    historical_resource_key,
)


LANGUAGES = ("zh-cn", "en-us")
DEFAULT_MAX_INPUT_BYTES = 5 * 1024 * 1024
UTF8_BOM = b"\xef\xbb\xbf"
CHARSET_SCAN_BYTES = 1024


class InputAssuranceError(ValueError):
    """A stable, machine-classifiable canonical input failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CharsetDeclaration:
    source: str
    value: str
    normalized: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "value": self.value,
            "normalized": self.normalized,
        }


@dataclass(frozen=True)
class SourceFinding:
    """A deterministic source-quality observation, not a parser failure."""

    code: str
    message: str
    evidence: Mapping[str, Any]
    category: str = "charset"
    severity: str = "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "evidence": {
                "actual_encoding": self.evidence["actual_encoding"],
                "utf8_bom": self.evidence["utf8_bom"],
                "declarations": [dict(item) for item in self.evidence["declarations"]],
            },
        }


@dataclass(frozen=True)
class CanonicalHtmlInput:
    product_key: str
    resource_key: str
    language: str
    source_path: Path
    normalized_path: Path
    source_sha256: str
    normalized_sha256: str
    expected_sha256: str
    raw_bytes: bytes
    text: str
    has_utf8_bom: bool
    source_findings: tuple[SourceFinding, ...]

    @property
    def size_bytes(self) -> int:
        return len(self.raw_bytes)


class _CharsetMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.declarations: list[tuple[str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "meta":
            return
        values = {key.lower(): value for key, value in attrs if value is not None}
        direct = values.get("charset")
        if direct:
            self.declarations.append(("meta_charset", direct))
        if values.get("http-equiv", "").strip().lower() != "content-type":
            return
        content = values.get("content", "")
        for part in content.split(";"):
            key, separator, value = part.partition("=")
            if separator and key.strip().lower() == "charset" and value.strip():
                self.declarations.append(("http_equiv", value.strip(" \t\r\n\"'")))
                break


class CanonicalInputLoader:
    """Load one byte-identical Source/Normalized pair from Product Definition."""

    def __init__(
        self,
        root: str | Path = ".",
        product_manager: ProductManager | None = None,
        max_input_bytes: int | None = DEFAULT_MAX_INPUT_BYTES,
    ) -> None:
        self.root = Path(root).resolve()
        self.product_manager = product_manager or ProductManager(
            str(self.root / "data" / "configs")
        )
        if max_input_bytes is not None and max_input_bytes <= 0:
            raise ValueError("max_input_bytes must be positive or None")
        self.max_input_bytes = max_input_bytes

    def load(
        self,
        product_key: str,
        language: str,
        *,
        version_key: str | None = None,
        expected_sha256: str | None = None,
    ) -> CanonicalHtmlInput:
        if language not in LANGUAGES:
            raise InputAssuranceError(
                "UNSUPPORTED_LANGUAGE", f"Unsupported language: {language}"
            )
        if expected_sha256 is not None and not _is_sha256(expected_sha256):
            raise InputAssuranceError(
                "INVALID_EXPECTED_SHA256", "Expected input SHA-256 is not valid"
            )

        definition = self.product_manager.get_product_config(product_key)
        if definition.get("product_key") != product_key:
            raise InputAssuranceError(
                "PRODUCT_DEFINITION_IDENTITY_MISMATCH",
                "Product Definition identity does not match the requested Product Key",
            )

        if version_key is None:
            resource_key = product_key
            source_definition = definition["sources"][language]
            normalized = normalized_input_path(self.root, definition, language)
        else:
            version = get_historical_version(definition, version_key)
            resource_key = historical_resource_key(product_key, version_key)
            source_definition = version["sources"][language]
            normalized = historical_normalized_input_path(
                self.root, definition, language, version_key
            )

        if source_definition.get("availability") != "available":
            raise InputAssuranceError(
                "SOURCE_UNAVAILABLE",
                f"Configured source is unavailable for {language}/{resource_key}",
            )
        snapshot_path = source_definition.get("snapshot_path")
        if not isinstance(snapshot_path, str) or not snapshot_path:
            raise InputAssuranceError(
                "INVALID_SOURCE_LOCATION", "Available source has no snapshot_path"
            )

        source_root = self.root / "data" / "current_prod_html" / language
        normalized_root = self.root / "data" / "prod-html" / language
        source = source_root / snapshot_path
        source_bytes = self._read_canonical_file(source, source_root, "Source Snapshot")
        normalized_bytes = self._read_canonical_file(
            normalized, normalized_root, "Normalized Input"
        )
        source_hash = _sha256(source_bytes)
        normalized_hash = _sha256(normalized_bytes)
        if source_hash != normalized_hash or source_bytes != normalized_bytes:
            raise InputAssuranceError(
                "SOURCE_NORMALIZED_HASH_MISMATCH",
                "Normalized Input is not byte-identical to its Source Snapshot",
            )

        frozen_hash = expected_sha256 or source_hash
        if source_hash != frozen_hash:
            raise InputAssuranceError(
                "NORMALIZED_INPUT_HASH_MISMATCH",
                "Canonical input SHA-256 does not match the frozen expected hash",
            )
        try:
            text = normalized_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise InputAssuranceError(
                "INVALID_UTF8",
                f"Canonical input is not strict UTF-8 at byte offset {error.start}",
            ) from error

        has_bom = normalized_bytes.startswith(UTF8_BOM)
        declarations = _charset_declarations(normalized_bytes)
        findings = _charset_findings(declarations, has_bom)
        return CanonicalHtmlInput(
            product_key=product_key,
            resource_key=resource_key,
            language=language,
            source_path=source,
            normalized_path=normalized,
            source_sha256=source_hash,
            normalized_sha256=normalized_hash,
            expected_sha256=frozen_hash,
            raw_bytes=normalized_bytes,
            text=text,
            has_utf8_bom=has_bom,
            source_findings=findings,
        )

    def _read_canonical_file(self, path: Path, base: Path, label: str) -> bytes:
        self._validate_path(path, base, label)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as error:
            raise InputAssuranceError(
                "CANONICAL_INPUT_READ_FAILED", f"Unable to open {label}: {path}"
            ) from error
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise InputAssuranceError(
                    "CANONICAL_INPUT_NOT_REGULAR_FILE", f"{label} is not a regular file"
                )
            if self.max_input_bytes is not None and metadata.st_size > self.max_input_bytes:
                raise InputAssuranceError(
                    "INPUT_EXCEEDS_IN_MEMORY_PROFILE",
                    f"{label} exceeds the frozen in-memory byte ceiling",
                )
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if self.max_input_bytes is not None and total > self.max_input_bytes:
                    raise InputAssuranceError(
                        "INPUT_EXCEEDS_IN_MEMORY_PROFILE",
                        f"{label} exceeds the frozen in-memory byte ceiling",
                    )
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)

    def _validate_path(self, path: Path, base: Path, label: str) -> None:
        base_absolute = base.absolute()
        path_absolute = path.absolute()
        try:
            repository_relative = path.relative_to(self.root)
        except ValueError as error:
            raise InputAssuranceError(
                "CANONICAL_INPUT_PATH_MISMATCH",
                f"{label} is outside the repository root",
            ) from error
        if ".." in repository_relative.parts:
            raise InputAssuranceError(
                "CANONICAL_INPUT_PATH_MISMATCH",
                f"{label} contains a parent-directory traversal",
            )
        try:
            relative = path_absolute.relative_to(base_absolute)
        except ValueError as error:
            raise InputAssuranceError(
                "CANONICAL_INPUT_PATH_MISMATCH",
                f"{label} escapes its canonical repository root",
            ) from error

        if base_absolute.resolve(strict=False) != base_absolute:
            raise InputAssuranceError(
                "CANONICAL_INPUT_SYMLINK_FORBIDDEN",
                f"{label} canonical root contains a symbolic link",
            )
        cursor = base_absolute
        for part in relative.parts:
            cursor = cursor / part
            try:
                metadata = os.lstat(cursor)
            except FileNotFoundError as error:
                raise InputAssuranceError(
                    "CANONICAL_INPUT_MISSING", f"{label} does not exist: {path}"
                ) from error
            if stat.S_ISLNK(metadata.st_mode):
                raise InputAssuranceError(
                    "CANONICAL_INPUT_SYMLINK_FORBIDDEN",
                    f"{label} must not contain symbolic-link components",
                )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalize_charset(value: str) -> str:
    cleaned = value.strip().lower()
    try:
        return codecs.lookup(cleaned).name
    except LookupError:
        return cleaned


def _charset_declarations(value: bytes) -> tuple[CharsetDeclaration, ...]:
    # HTML's reliable encoding prescan window is byte-oriented.  Markup and
    # charset labels are ASCII, so ignoring non-ASCII bytes cannot invent a
    # declaration and avoids splitting a UTF-8 sequence at the window edge.
    prefix = value[:CHARSET_SCAN_BYTES].decode("ascii", errors="ignore")
    parser = _CharsetMetaParser()
    try:
        parser.feed(prefix)
    except Exception:
        # A malformed declaration is a parseability concern.  Charset findings
        # are emitted only for declarations the prescanner can identify.
        return ()
    return tuple(
        CharsetDeclaration(source, raw.strip(), _normalize_charset(raw))
        for source, raw in parser.declarations
    )


def _charset_findings(
    declarations: tuple[CharsetDeclaration, ...], has_bom: bool
) -> tuple[SourceFinding, ...]:
    evidence = {
        "actual_encoding": "utf-8",
        "utf8_bom": has_bom,
        "declarations": [declaration.to_dict() for declaration in declarations],
    }
    normalized = {declaration.normalized for declaration in declarations}
    findings: list[SourceFinding] = []
    if any(value != "utf-8" for value in normalized):
        findings.append(SourceFinding(
            "SOURCE_CHARSET_DECLARATION_NOT_UTF8",
            "Source declares a non-UTF-8 charset while the accepted bytes are strict UTF-8.",
            evidence,
        ))
    if len(normalized) > 1:
        findings.append(SourceFinding(
            "SOURCE_CHARSET_DECLARATIONS_CONFLICT",
            "Source contains conflicting reliable charset declarations.",
            evidence,
        ))
    if has_bom and any(value != "utf-8" for value in normalized):
        findings.append(SourceFinding(
            "SOURCE_CHARSET_BOM_CONFLICT",
            "UTF-8 BOM conflicts with a non-UTF-8 charset declaration.",
            evidence,
        ))
    return tuple(sorted(findings, key=lambda finding: finding.code))


__all__ = [
    "CanonicalHtmlInput",
    "CanonicalInputLoader",
    "CharsetDeclaration",
    "DEFAULT_MAX_INPUT_BYTES",
    "InputAssuranceError",
    "SourceFinding",
]
