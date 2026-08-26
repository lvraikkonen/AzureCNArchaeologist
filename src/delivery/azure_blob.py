"""Azure Blob Storage adapter and local environment configuration."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .service import DeliveryError


CONNECTION_STRING_ENV = "AZURE_STORAGE_CONNECTION_STRING"
CONTAINER_NAME_ENV = "AZURE_BLOB_CONTAINER_NAME"
CONTAINER_NAME_PATTERN = re.compile(
    r"^(?!.*--)[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$"
)


@dataclass(frozen=True)
class BlobDeliveryConfig:
    connection_string: str = field(repr=False)
    container_name: str


def load_blob_delivery_config(
    project_root: Path | str,
    *,
    environ: Mapping[str, str] | None = None,
) -> BlobDeliveryConfig:
    """Read Blob settings from ``.env``, with process variables taking priority."""

    root = Path(project_root).resolve()
    env_path = root / ".env"
    file_values: Mapping[str, str | None] = {}
    if env_path.exists():
        if not env_path.is_file():
            raise DeliveryError(f"Blob 配置路径不是普通文件：{env_path}")
        try:
            from dotenv import dotenv_values

            file_values = dotenv_values(env_path)
        except (ImportError, OSError, UnicodeError) as error:
            raise DeliveryError(
                "无法读取 .env 中的 Blob 配置；"
                "请确认项目依赖和文件编码。"
            ) from error

    process_values = os.environ if environ is None else environ
    connection_string = _configured_value(
        CONNECTION_STRING_ENV,
        process_values=process_values,
        file_values=file_values,
    )
    container_name = _configured_value(
        CONTAINER_NAME_ENV,
        process_values=process_values,
        file_values=file_values,
    )
    if not connection_string:
        raise DeliveryError(
            f"缺少 {CONNECTION_STRING_ENV}；"
            "请复制 .env_example 为 .env 后填写。"
        )
    if not container_name:
        raise DeliveryError(
            f"缺少 {CONTAINER_NAME_ENV}；请在 .env 中明确填写目标容器。"
        )
    if not CONTAINER_NAME_PATTERN.fullmatch(container_name):
        raise DeliveryError(
            f"{CONTAINER_NAME_ENV} 必须是 3 到 63 位"
            "小写字母、数字或单连字符，"
            "且首尾必须是字母或数字。"
        )
    return BlobDeliveryConfig(
        connection_string=connection_string,
        container_name=container_name,
    )


class AzureBlobSink:
    """Write-only adapter that never overwrites an existing Blob."""

    def __init__(self, config: BlobDeliveryConfig) -> None:
        try:
            from azure.core.exceptions import AzureError, ResourceExistsError
            from azure.storage.blob import BlobServiceClient, ContentSettings
        except ImportError as error:
            raise DeliveryError(
                "缺少 Azure Blob SDK；请先安装项目依赖。"
            ) from error
        try:
            service_client = BlobServiceClient.from_connection_string(
                config.connection_string
            )
            container_client = service_client.get_container_client(
                config.container_name
            )
        except (TypeError, ValueError) as error:
            raise DeliveryError(
                "无法初始化 Azure Blob 客户端；"
                "请检查 .env 中的连接串和容器名。"
            ) from error

        self.container_name = config.container_name
        self._service_client = service_client
        self._container_client = container_client
        self._content_settings_type = ContentSettings
        self._azure_error_type = AzureError
        self._resource_exists_error_type = ResourceExistsError

    def upload_file(
        self,
        *,
        blob_name: str,
        source_path: Path,
        content_type: str,
    ) -> None:
        try:
            with source_path.open("rb") as stream:
                self._upload(
                    blob_name=blob_name,
                    data=stream,
                    content_type=content_type,
                )
        except OSError as error:
            raise DeliveryError(
                f"无法读取待上传文件：{source_path}"
            ) from error

    def upload_bytes(
        self,
        *,
        blob_name: str,
        data: bytes,
        content_type: str,
    ) -> None:
        self._upload(blob_name=blob_name, data=data, content_type=content_type)

    def close(self) -> None:
        self._service_client.close()

    def _upload(self, *, blob_name: str, data: Any, content_type: str) -> None:
        try:
            self._container_client.upload_blob(
                name=blob_name,
                data=data,
                overwrite=False,
                content_settings=self._content_settings_type(
                    content_type=content_type
                ),
            )
        except self._resource_exists_error_type as error:
            raise DeliveryError(
                f"Blob 已存在，禁止覆盖同一 Release 路径：{blob_name}"
            ) from error
        except self._azure_error_type as error:
            status_code = getattr(error, "status_code", None)
            error_code = getattr(error, "error_code", None)
            safe_details = ", ".join(
                str(value)
                for value in (status_code, error_code)
                if value is not None
            )
            suffix = f"（{safe_details}）" if safe_details else ""
            raise DeliveryError(
                f"Azure Blob 上传失败：{blob_name}{suffix}"
            ) from error


def _configured_value(
    name: str,
    *,
    process_values: Mapping[str, str],
    file_values: Mapping[str, str | None],
) -> str:
    value = (
        process_values[name]
        if name in process_values
        else file_values.get(name, "")
    )
    return value.strip() if isinstance(value, str) else ""
