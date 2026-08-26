from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.cli import main
from src.delivery import (
    AzureBlobSink,
    BlobDeliveryConfig,
    DeliveryError,
    load_blob_delivery_config,
    upload_release_to_blob,
)
from src.release import build_full_release
from src.review import prepare_review_queue
from tests.test_m5_review_release import _approve, _catalog, _sealed_run


class RecordingBlobSink:
    container_name = "cms-output"

    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.uploads: list[tuple[str, bytes, str]] = []

    def upload_file(
        self,
        *,
        blob_name: str,
        source_path: Path,
        content_type: str,
    ) -> None:
        self._record(blob_name, source_path.read_bytes(), content_type)

    def upload_bytes(
        self,
        *,
        blob_name: str,
        data: bytes,
        content_type: str,
    ) -> None:
        self._record(blob_name, data, content_type)

    def _record(self, blob_name: str, data: bytes, content_type: str) -> None:
        self.calls += 1
        if self.fail_on_call == self.calls:
            raise DeliveryError(f"受控上传失败：{blob_name}")
        self.uploads.append((blob_name, data, content_type))


def _build_release_fixture(tmp_path, project_builder):
    catalog = _catalog(project_builder, ("approved-product", "pending-product"))
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    releases_root = tmp_path / "releases"
    _sealed_run(catalog, runs_root, run_name="blob-test-batch")
    prepare_review_queue(
        catalog,
        run_name="blob-test-batch",
        review_id="blob-test-review",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    _approve(
        catalog,
        reviews_root,
        review_id="blob-test-review",
        product_key="approved-product",
    )
    release = build_full_release(
        catalog,
        review_id="blob-test-review",
        release_id="release-20260826-153000",
        reviews_root=reviews_root,
        releases_root=releases_root,
    )
    return catalog, reviews_root, releases_root, release


def test_upload_uses_upload_date_release_prefix_and_publishes_manifest_last(
    tmp_path, project_builder
) -> None:
    catalog, reviews_root, releases_root, release = _build_release_fixture(
        tmp_path, project_builder
    )
    sink = RecordingBlobSink()
    upload_time = datetime(
        2026,
        8,
        26,
        15,
        30,
        tzinfo=timezone(timedelta(hours=-7)),
    )

    result = upload_release_to_blob(
        catalog,
        release_id=release.release_id,
        blob_sink=sink,
        reviews_root=reviews_root,
        releases_root=releases_root,
        uploaded_at=upload_time,
    )

    assert result.blob_prefix == "2026-08-26/release-20260826-153000"
    assert result.delivery_manifest_blob_path == (
        "2026-08-26/release-20260826-153000/delivery-manifest.json"
    )
    assert [name for name, _, _ in sink.uploads] == [
        "2026-08-26/release-20260826-153000/"
        "payloads/zh-cn/pricing/approved-product.json",
        "2026-08-26/release-20260826-153000/"
        "payloads/en-us/pricing/approved-product.json",
        "2026-08-26/release-20260826-153000/delivery-manifest.json",
    ]
    assert all(
        content_type == "application/json; charset=utf-8"
        for _, _, content_type in sink.uploads
    )
    delivery_manifest = json.loads(sink.uploads[-1][1])
    assert delivery_manifest == result.manifest
    assert delivery_manifest["release_kind"] == "full"
    assert delivery_manifest["summary"] == {
        "products": 1,
        "payload_items": 2,
    }
    assert delivery_manifest["payload_contract_version"] == "1.2"
    assert [
        product["product_key"] for product in delivery_manifest["products"]
    ] == ["approved-product"]
    assert "pending-product" not in json.dumps(delivery_manifest)
    serialized_manifest = json.dumps(delivery_manifest, ensure_ascii=False)
    assert str(tmp_path) not in serialized_manifest
    assert "reviewer" not in serialized_manifest
    assert not any(
        forbidden in serialized_manifest.lower()
        for forbidden in ("hash", "digest", "fingerprint", "checksum")
    )
    assert all(
        "release-manifest.json" not in name
        and "review-decisions" not in name
        for name, _, _ in sink.uploads
    )


def test_payload_failure_stops_before_delivery_manifest(
    tmp_path, project_builder
) -> None:
    catalog, reviews_root, releases_root, release = _build_release_fixture(
        tmp_path, project_builder
    )
    sink = RecordingBlobSink(fail_on_call=2)

    with pytest.raises(DeliveryError, match="受控上传失败"):
        upload_release_to_blob(
            catalog,
            release_id=release.release_id,
            blob_sink=sink,
            reviews_root=reviews_root,
            releases_root=releases_root,
            uploaded_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )

    assert sink.calls == 2
    assert len(sink.uploads) == 1
    assert not any(
        name.endswith("delivery-manifest.json") for name, _, _ in sink.uploads
    )


def test_delivery_manifest_failure_leaves_only_non_consumable_payloads(
    tmp_path, project_builder
) -> None:
    catalog, reviews_root, releases_root, release = _build_release_fixture(
        tmp_path, project_builder
    )
    sink = RecordingBlobSink(fail_on_call=3)

    with pytest.raises(DeliveryError, match="受控上传失败"):
        upload_release_to_blob(
            catalog,
            release_id=release.release_id,
            blob_sink=sink,
            reviews_root=reviews_root,
            releases_root=releases_root,
            uploaded_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )

    assert sink.calls == 3
    assert len(sink.uploads) == 2
    assert all(
        not name.endswith("delivery-manifest.json")
        for name, _, _ in sink.uploads
    )


def test_tampered_release_is_rejected_before_any_blob_upload(
    tmp_path, project_builder
) -> None:
    catalog, reviews_root, releases_root, release = _build_release_fixture(
        tmp_path, project_builder
    )
    first_item = release.manifest["products"][0]["items"][0]
    payload_path = release.release_directory / first_item["release_payload_path"]
    payload_path.write_bytes(b"tampered after release\n")
    sink = RecordingBlobSink()

    with pytest.raises(DeliveryError, match="未通过上传前核对"):
        upload_release_to_blob(
            catalog,
            release_id=release.release_id,
            blob_sink=sink,
            reviews_root=reviews_root,
            releases_root=releases_root,
            uploaded_at=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )

    assert sink.calls == 0
    assert sink.uploads == []


def test_blob_config_reads_dotenv_and_does_not_repr_connection_string(
    tmp_path,
) -> None:
    secret = "unit-test-sensitive-connection-value"
    (tmp_path / ".env").write_text(
        f"AZURE_STORAGE_CONNECTION_STRING={secret}\n"
        "AZURE_BLOB_CONTAINER_NAME=cms-payloads\n",
        encoding="utf-8",
    )

    config = load_blob_delivery_config(tmp_path, environ={})

    assert config.connection_string == secret
    assert config.container_name == "cms-payloads"
    assert secret not in repr(config)
    assert "sensitive-connection" not in repr(config)


def test_process_environment_overrides_dotenv(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        "AZURE_STORAGE_CONNECTION_STRING=file-secret\n"
        "AZURE_BLOB_CONTAINER_NAME=file-container\n",
        encoding="utf-8",
    )

    config = load_blob_delivery_config(
        tmp_path,
        environ={
            "AZURE_STORAGE_CONNECTION_STRING": "process-secret",
            "AZURE_BLOB_CONTAINER_NAME": "process-container",
        },
    )

    assert config == BlobDeliveryConfig(
        connection_string="process-secret",
        container_name="process-container",
    )


def test_missing_connection_string_reports_variable_without_secret(tmp_path) -> None:
    with pytest.raises(
        DeliveryError,
        match="AZURE_STORAGE_CONNECTION_STRING",
    ) as captured:
        load_blob_delivery_config(
            tmp_path,
            environ={"AZURE_BLOB_CONTAINER_NAME": "cms-payloads"},
        )

    assert ".env_example" in str(captured.value)


def test_cli_uploads_verified_release_with_injected_blob_sink(
    tmp_path, project_builder
) -> None:
    catalog, reviews_root, releases_root, release = _build_release_fixture(
        tmp_path, project_builder
    )
    sink = RecordingBlobSink()
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(
        ["release-upload", "--release-id", release.release_id, "--json"],
        project_root=catalog.project_root,
        reviews_root=reviews_root,
        releases_root=releases_root,
        blob_sink=sink,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    output = json.loads(stdout.getvalue())
    assert output["status"] == "uploaded"
    assert output["container_name"] == "cms-output"
    assert output["summary"] == {"products": 1, "payload_items": 2}
    assert sink.uploads[-1][0].endswith("/delivery-manifest.json")


def test_azure_sink_uses_non_overwriting_json_upload(
    tmp_path, monkeypatch
) -> None:
    from azure.storage.blob import BlobServiceClient

    class FakeContainerClient:
        def __init__(self) -> None:
            self.calls = []

        def upload_blob(self, **kwargs) -> None:
            self.calls.append(kwargs)

    class FakeServiceClient:
        def __init__(self) -> None:
            self.container = FakeContainerClient()
            self.requested_container = None
            self.closed = False

        def get_container_client(self, container_name):
            self.requested_container = container_name
            return self.container

        def close(self) -> None:
            self.closed = True

    service_client = FakeServiceClient()
    monkeypatch.setattr(
        BlobServiceClient,
        "from_connection_string",
        staticmethod(lambda _connection_string: service_client),
    )
    payload = tmp_path / "payload.json"
    payload.write_bytes(b'{"ok": true}\n')
    sink = AzureBlobSink(
        BlobDeliveryConfig(
            connection_string="sensitive-connection-string",
            container_name="cms-output",
        )
    )

    sink.upload_file(
        blob_name="2026-08-26/release-id/payloads/en-us/product.json",
        source_path=payload,
        content_type="application/json; charset=utf-8",
    )
    sink.close()

    assert service_client.requested_container == "cms-output"
    assert service_client.closed is True
    assert len(service_client.container.calls) == 1
    call = service_client.container.calls[0]
    assert call["name"] == (
        "2026-08-26/release-id/payloads/en-us/product.json"
    )
    assert call["overwrite"] is False
    assert call["content_settings"].content_type == (
        "application/json; charset=utf-8"
    )


def test_azure_sink_converts_existing_blob_error_without_exposing_secret(
    monkeypatch,
) -> None:
    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import BlobServiceClient

    class ExistingBlobContainerClient:
        def upload_blob(self, **_kwargs) -> None:
            raise ResourceExistsError("already exists")

    class FakeServiceClient:
        def get_container_client(self, _container_name):
            return ExistingBlobContainerClient()

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        BlobServiceClient,
        "from_connection_string",
        staticmethod(lambda _connection_string: FakeServiceClient()),
    )
    secret = "sensitive-connection-string"
    sink = AzureBlobSink(
        BlobDeliveryConfig(
            connection_string=secret,
            container_name="cms-output",
        )
    )

    with pytest.raises(DeliveryError, match="禁止覆盖") as captured:
        sink.upload_bytes(
            blob_name="2026-08-26/release-id/delivery-manifest.json",
            data=b"{}\n",
            content_type="application/json; charset=utf-8",
        )

    assert secret not in str(captured.value)
