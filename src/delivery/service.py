"""Upload one verified Release and publish its CMS delivery manifest last."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from src.core.catalog import LANGUAGES, ProductCatalog
from src.release import ReleaseError, verify_release


DELIVERY_MANIFEST_NAME = "delivery-manifest.json"
JSON_CONTENT_TYPE = "application/json; charset=utf-8"


class DeliveryError(RuntimeError):
    """A verified Release could not be safely published to Blob Storage."""


class BlobSink(Protocol):
    """The minimal write-only Blob interface used by the delivery service."""

    container_name: str

    def upload_file(
        self,
        *,
        blob_name: str,
        source_path: Path,
        content_type: str,
    ) -> None: ...

    def upload_bytes(
        self,
        *,
        blob_name: str,
        data: bytes,
        content_type: str,
    ) -> None: ...


@dataclass(frozen=True)
class BlobUploadResult:
    release_id: str
    release_kind: str
    container_name: str
    upload_date: str
    uploaded_at: str
    blob_prefix: str
    delivery_manifest_blob_path: str
    manifest: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "uploaded",
            "release_id": self.release_id,
            "release_kind": self.release_kind,
            "container_name": self.container_name,
            "upload_date": self.upload_date,
            "uploaded_at": self.uploaded_at,
            "blob_prefix": self.blob_prefix,
            "delivery_manifest_blob_path": self.delivery_manifest_blob_path,
            "summary": self.manifest["summary"],
        }


@dataclass(frozen=True)
class _PayloadUpload:
    source_path: Path
    blob_path: str


def upload_release_to_blob(
    catalog: ProductCatalog,
    *,
    release_id: str,
    blob_sink: BlobSink,
    reviews_root: Path | str | None = None,
    releases_root: Path | str | None = None,
    uploaded_at: datetime | None = None,
) -> BlobUploadResult:
    """Upload exactly one sealed Release beneath upload-date/release-id.

    Payloads are uploaded first and ``delivery-manifest.json`` is uploaded
    last. CMS can therefore treat the manifest as the only completion marker.
    Existing Blob names are never overwritten by the sink.
    """

    try:
        verification = verify_release(
            catalog,
            release_id=release_id,
            reviews_root=reviews_root,
            releases_root=releases_root,
        )
    except ReleaseError as error:
        raise DeliveryError(
            f"Release {release_id} 未通过上传前核对：{error}"
        ) from error

    release_directory = _release_directory(
        catalog,
        release_id=release_id,
        releases_root=releases_root,
    )
    release_manifest = _read_json_object(
        release_directory / "release-manifest.json"
    )
    moment = uploaded_at if uploaded_at is not None else datetime.now().astimezone()
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise DeliveryError("上传时间必须包含时区。")
    upload_date = moment.date().isoformat()
    uploaded_at_text = moment.isoformat(timespec="seconds")
    blob_prefix = PurePosixPath(upload_date, release_id)

    manifest, payload_uploads = _build_delivery_manifest(
        release_directory=release_directory,
        release_manifest=release_manifest,
        blob_prefix=blob_prefix,
        uploaded_at=uploaded_at_text,
    )
    for payload in payload_uploads:
        blob_sink.upload_file(
            blob_name=payload.blob_path,
            source_path=payload.source_path,
            content_type=JSON_CONTENT_TYPE,
        )

    delivery_manifest_blob_path = (
        blob_prefix / DELIVERY_MANIFEST_NAME
    ).as_posix()
    blob_sink.upload_bytes(
        blob_name=delivery_manifest_blob_path,
        data=_json_bytes(manifest),
        content_type=JSON_CONTENT_TYPE,
    )
    return BlobUploadResult(
        release_id=release_id,
        release_kind=str(verification["release_kind"]),
        container_name=blob_sink.container_name,
        upload_date=upload_date,
        uploaded_at=uploaded_at_text,
        blob_prefix=blob_prefix.as_posix(),
        delivery_manifest_blob_path=delivery_manifest_blob_path,
        manifest=manifest,
    )


def _build_delivery_manifest(
    *,
    release_directory: Path,
    release_manifest: dict[str, Any],
    blob_prefix: PurePosixPath,
    uploaded_at: str,
) -> tuple[dict[str, Any], tuple[_PayloadUpload, ...]]:
    release_id = release_manifest.get("release_id")
    release_kind = release_manifest.get("release_kind")
    products = release_manifest.get("products")
    if not isinstance(release_id, str) or not release_id:
        raise DeliveryError("Release 清单缺少 release_id。")
    if release_kind not in {"full", "delta"}:
        raise DeliveryError("Release 清单中的 release_kind 无效。")
    if not isinstance(products, list) or not products:
        raise DeliveryError("Release 清单没有可上传产品。")

    delivery_products: list[dict[str, Any]] = []
    uploads: list[_PayloadUpload] = []
    seen_blob_paths: set[str] = set()
    for product in products:
        if not isinstance(product, dict):
            raise DeliveryError("Release 产品记录必须是对象。")
        product_key = product.get("product_key")
        if not isinstance(product_key, str) or not product_key:
            raise DeliveryError("Release 产品记录缺少 product_key。")
        items = product.get("items")
        if not isinstance(items, list) or [
            item.get("language") for item in items if isinstance(item, dict)
        ] != list(LANGUAGES):
            raise DeliveryError(
                f"产品 {product_key} 没有完整且有序的双语 Payload。"
            )

        delivery_items: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                raise DeliveryError(
                    f"产品 {product_key} 的处理项必须是对象。"
                )
            item_id = item.get("item_id")
            language = item.get("language")
            release_payload_path = item.get("release_payload_path")
            if not isinstance(item_id, str) or not item_id:
                raise DeliveryError(
                    f"产品 {product_key} 的处理项缺少 item_id。"
                )
            if language not in LANGUAGES:
                raise DeliveryError(f"处理项 {item_id} 的语言无效。")
            source_path = _safe_release_path(
                release_directory,
                release_payload_path,
                label=f"{item_id} Release Payload",
            )
            if not source_path.is_file():
                raise DeliveryError(f"找不到待上传 Payload：{source_path}")
            relative = PurePosixPath(str(release_payload_path))
            blob_path = (blob_prefix / relative).as_posix()
            if blob_path in seen_blob_paths:
                raise DeliveryError(f"待上传 Blob 路径重复：{blob_path}")
            seen_blob_paths.add(blob_path)
            uploads.append(_PayloadUpload(source_path, blob_path))
            delivery_items.append(
                {
                    "item_id": item_id,
                    "language": language,
                    "blob_path": blob_path,
                }
            )

        delivery_product: dict[str, Any] = {
            "product_key": product_key,
            "display_name": product.get("display_name", ""),
            "page_model": product.get("page_model", ""),
            "semantic_strategy": product.get("semantic_strategy", ""),
            "items": delivery_items,
        }
        delivery_products.append(delivery_product)

    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "release_id": release_id,
        "release_kind": release_kind,
        "upload_date": blob_prefix.parts[0],
        "uploaded_at": uploaded_at,
        "blob_prefix": blob_prefix.as_posix(),
        "summary": {
            "products": len(delivery_products),
            "payload_items": len(uploads),
        },
        "products": delivery_products,
    }
    source_review = release_manifest.get("source_review")
    if isinstance(source_review, dict):
        contract_version = source_review.get("payload_contract_version")
        if isinstance(contract_version, str) and contract_version:
            manifest["payload_contract_version"] = contract_version
    return manifest, tuple(uploads)


def _release_directory(
    catalog: ProductCatalog,
    *,
    release_id: str,
    releases_root: Path | str | None,
) -> Path:
    root = (
        Path(releases_root).resolve()
        if releases_root is not None
        else (catalog.project_root / "releases").resolve()
    )
    return (root / release_id).resolve()


def _safe_release_path(root: Path, value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise DeliveryError(f"{label} 路径必须是非空文本。")
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise DeliveryError(f"{label} 使用了不安全路径：{value}")
    root = root.resolve()
    path = root.joinpath(*relative.parts).resolve()
    if not path.is_relative_to(root):
        raise DeliveryError(f"{label} 路径越出 Release 目录：{value}")
    return path


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise DeliveryError(f"找不到 JSON 文件：{path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeliveryError(f"无法读取 JSON 文件 {path}：{error}") from error
    if not isinstance(value, dict):
        raise DeliveryError(f"JSON 文件必须包含对象：{path}")
    return value


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")
