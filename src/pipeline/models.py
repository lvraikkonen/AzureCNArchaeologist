"""Serializable domain models for the v0.3 batch pipeline.

The immutable input manifest records what a run means.  The batch manifest is
the only mutable source of truth for what happened to that input.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar, Iterable, Mapping


LANGUAGES = ("zh-cn", "en-us")
STAGES = ("discovery", "normalize", "preflight", "extract", "validate", "review", "report")
TERMINAL_EXECUTION_STATUSES = ("succeeded", "failed", "skipped")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


@dataclass(frozen=True)
class BatchItem:
    """One current or historical publishable resource in one language."""

    language: str
    resource_key: str
    product_key: str
    resource_kind: str
    page_model: str
    capability_status: str
    config_path: str
    config_sha256: str
    source_availability: str
    source_path: str | None
    source_sha256: str | None
    normalized_path: str
    normalized_sha256: str | None
    output_path: str
    diagnostic_path: str
    validation_path: str
    slug: str
    strategy: str
    catalog_categories: tuple[str, ...] = ()
    support_article_type: str | None = None
    version_key: str | None = None
    version_label: str | None = None
    source_url: str | None = None
    cms_path: str | None = None
    skip_reason: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.language not in LANGUAGES:
            raise ValueError(f"Unsupported language: {self.language}")
        if not self.resource_key or not self.product_key:
            raise ValueError("Batch item identities cannot be empty")
        if self.resource_kind not in ("current", "historical_version"):
            raise ValueError(f"Unsupported resource kind: {self.resource_kind}")
        for name in ("config_path", "normalized_path", "output_path", "diagnostic_path", "validation_path"):
            value = getattr(self, name)
            if value.startswith("/"):
                raise ValueError(f"{name} must be relative: {value}")

    @property
    def item_id(self) -> str:
        return f"{self.language}/{self.resource_key}"

    @property
    def runnable(self) -> bool:
        return self.skip_reason is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "identity": {"language": self.language, "resource_key": self.resource_key},
            "product_key": self.product_key,
            "resource": {
                "kind": self.resource_kind,
                "slug": self.slug,
                "version_key": self.version_key,
                "version_label": self.version_label,
            },
            "page_model": self.page_model,
            "capability_status": self.capability_status,
            "catalog_categories": list(self.catalog_categories),
            "support_article_type": self.support_article_type,
            "strategy": self.strategy,
            "config": {"path": self.config_path, "sha256": self.config_sha256},
            "source": {
                "availability": self.source_availability,
                "path": self.source_path,
                "url": self.source_url,
                "cms_path": self.cms_path,
                "sha256": self.source_sha256,
            },
            "normalized_input": {"path": self.normalized_path, "sha256": self.normalized_sha256},
            "artifacts": {
                "payload": {"path": self.output_path, "sha256": None},
                "diagnostic": {"path": self.diagnostic_path, "sha256": None},
                "validation": {"path": self.validation_path, "sha256": None},
            },
            "skip_reason": dict(self.skip_reason) if self.skip_reason else None,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BatchItem":
        identity = value["identity"]
        resource = value["resource"]
        source = value["source"]
        artifacts = value["artifacts"]
        return cls(
            language=identity["language"], resource_key=identity["resource_key"],
            product_key=value["product_key"], resource_kind=resource["kind"],
            page_model=value["page_model"], capability_status=value["capability_status"],
            config_path=value["config"]["path"], config_sha256=value["config"]["sha256"],
            source_availability=source["availability"], source_path=source.get("path"),
            source_sha256=source.get("sha256"), normalized_path=value["normalized_input"]["path"],
            normalized_sha256=value["normalized_input"].get("sha256"),
            output_path=artifacts["payload"]["path"], diagnostic_path=artifacts["diagnostic"]["path"],
            validation_path=artifacts["validation"]["path"], slug=resource["slug"],
            strategy=value["strategy"], catalog_categories=tuple(value.get("catalog_categories", [])),
            support_article_type=value.get("support_article_type"), version_key=resource.get("version_key"),
            version_label=resource.get("version_label"), source_url=source.get("url"),
            cms_path=source.get("cms_path"), skip_reason=value.get("skip_reason"),
        )


@dataclass(frozen=True)
class PipelinePlan:
    scope: Mapping[str, Any]
    languages: tuple[str, ...]
    items: tuple[BatchItem, ...]

    @property
    def summary(self) -> dict[str, int]:
        total = len(self.items)
        runnable = sum(item.runnable for item in self.items)
        known_unsupported = sum(
            bool(item.skip_reason and item.skip_reason.get("code") == "KNOWN_UNSUPPORTED")
            for item in self.items
        )
        unavailable = sum(
            bool(item.skip_reason and item.skip_reason.get("code") == "SOURCE_UNAVAILABLE")
            for item in self.items
        )
        return {
            "total": total,
            "runnable": runnable,
            "skipped": total - runnable,
            "known_unsupported": known_unsupported,
            "source_unavailable": unavailable,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": _clone(dict(self.scope)),
            "languages": list(self.languages),
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class InputManifest:
    batch_id: str
    created_at: str
    scope: Mapping[str, Any]
    languages: tuple[str, ...]
    summary: Mapping[str, int]
    provenance: Mapping[str, Any]
    items: tuple[Mapping[str, Any], ...]
    schema_version: str = "1.0"

    @classmethod
    def from_plan(
        cls,
        batch_id: str,
        plan: PipelinePlan,
        provenance: Mapping[str, Any],
        *,
        created_at: str | None = None,
    ) -> "InputManifest":
        return cls(
            batch_id=batch_id,
            created_at=created_at or utc_now(),
            scope=_clone(dict(plan.scope)),
            languages=plan.languages,
            summary=plan.summary,
            provenance=_clone(dict(provenance)),
            items=tuple(item.to_dict() for item in plan.items),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "scope": _clone(dict(self.scope)),
            "languages": list(self.languages),
            "summary": _clone(dict(self.summary)),
            "provenance": _clone(dict(self.provenance)),
            "items": _clone(list(self.items)),
        }


def initial_checkpoint(status: str = "pending") -> dict[str, Any]:
    return {
        "status": status,
        "attempts": [],
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "error": None,
    }


@dataclass(frozen=True)
class BatchManifest:
    value: Mapping[str, Any]
    SCHEMA_VERSION: ClassVar[str] = "1.0"

    @classmethod
    def from_input_manifest(cls, manifest: InputManifest | Mapping[str, Any]) -> "BatchManifest":
        source = manifest.to_dict() if isinstance(manifest, InputManifest) else _clone(dict(manifest))
        items: dict[str, Any] = {}
        for frozen in source["items"]:
            item_id = frozen["item_id"]
            skipped = frozen.get("skip_reason") is not None
            execution = "skipped" if skipped else "pending"
            checkpoints = {stage: initial_checkpoint("skipped" if skipped else "pending") for stage in STAGES}
            if skipped:
                for checkpoint in checkpoints.values():
                    checkpoint["error"] = _clone(frozen["skip_reason"])
            items[item_id] = {
                "item_id": item_id,
                "identity": _clone(frozen["identity"]),
                "product_key": frozen["product_key"],
                "resource": _clone(frozen["resource"]),
                "page_model": frozen["page_model"],
                "strategy": frozen["strategy"],
                "status": {
                    "execution": execution,
                    "validation": "not_run",
                    "review": "not_requested",
                    "publication": "not_published",
                },
                "checkpoints": checkpoints,
                "artifacts": {
                    "normalized_input": _clone(frozen["normalized_input"]),
                    **_clone(frozen["artifacts"]),
                },
                "error": _clone(frozen.get("skip_reason")),
            }
        now = source["created_at"]
        return cls({
            "schema_version": cls.SCHEMA_VERSION,
            "batch_id": source["batch_id"],
            "revision": 0,
            "status": "created",
            "created_at": now,
            "updated_at": now,
            "input_manifest": {"path": "input-manifest.json", "sha256": None},
            "checkpoints": {stage: initial_checkpoint() for stage in STAGES},
            "items": items,
            "summary": _clone(source["summary"]),
        })

    def to_dict(self) -> dict[str, Any]:
        return _clone(dict(self.value))

    @property
    def batch_id(self) -> str:
        return str(self.value["batch_id"])

    @property
    def revision(self) -> int:
        return int(self.value["revision"])


def items_from_dicts(values: Iterable[Mapping[str, Any]]) -> tuple[BatchItem, ...]:
    return tuple(BatchItem.from_dict(value) for value in values)


def summarize_batch_manifest(manifest: Mapping[str, Any]) -> dict[str, int]:
    """Build the canonical count projection from authoritative item states."""
    items = list(manifest["items"].values())
    total = len(items)
    skipped = sum(item["status"]["execution"] == "skipped" for item in items)
    return {
        "total": total,
        "runnable": total - skipped,
        "skipped": skipped,
        "known_unsupported": sum(
            (item.get("error") or {}).get("code") == "KNOWN_UNSUPPORTED"
            for item in items
        ),
        "source_unavailable": sum(
            (item.get("error") or {}).get("code") == "SOURCE_UNAVAILABLE"
            for item in items
        ),
        "execution_succeeded": sum(
            item["status"]["execution"] == "succeeded" for item in items
        ),
        "execution_failed": sum(
            item["status"]["execution"] == "failed" for item in items
        ),
        "execution_pending": sum(
            item["status"]["execution"] in ("pending", "running") for item in items
        ),
        "validation_passed": sum(
            item["status"]["validation"] == "passed" for item in items
        ),
        "validation_failed": sum(
            item["status"]["validation"] == "failed" for item in items
        ),
        "validation_not_run": sum(
            item["status"]["validation"] == "not_run"
            and item["status"]["execution"] != "skipped"
            for item in items
        ),
        "review_pending": sum(
            item["status"]["review"] == "pending" for item in items
        ),
        "not_published": sum(
            item["status"]["publication"] == "not_published" for item in items
        ),
    }


def derive_batch_availability(
    manifest: Mapping[str, Any], *, lock_is_held: bool
) -> tuple[str, bool]:
    """Derive display status and resumability without mutating pipeline state."""
    stored_status = str(manifest["status"])
    interrupted = stored_status in ("created", "running") and not lock_is_held
    incomplete_checkpoint = any(
        checkpoint["status"] in ("pending", "running")
        for item in manifest["items"].values()
        if item["status"]["execution"] != "skipped"
        for checkpoint in item["checkpoints"].values()
    )
    execution_failure = any(
        item["status"]["execution"] == "failed"
        for item in manifest["items"].values()
    )
    return (
        "interrupted" if interrupted else stored_status,
        interrupted or incomplete_checkpoint or execution_failure,
    )
