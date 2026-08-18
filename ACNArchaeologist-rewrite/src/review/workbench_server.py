"""Loopback-only HTTP bridge for the rewrite Review Workbench."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from src.core.catalog import CatalogError, ProductCatalog
from src.review.service import ReviewError
from src.review.workbench import ReviewWorkbenchService


MAX_JSON_BODY_BYTES = 64 * 1024
DECISION_FIELDS = {
    "reviewer",
    "decision",
    "notes",
    "inspected_languages",
    "inspected_materials",
}


@dataclass(frozen=True)
class ReviewWorkbenchServerConfig:
    project_root: Path
    review_id: str
    reviews_root: Path | str | None = None
    dashboard_origin: str = "http://127.0.0.1:3000"
    host: str = "127.0.0.1"
    port: int = 8765
    token: str | None = None


class ReviewWorkbenchHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        service: ReviewWorkbenchService,
        dashboard_origin: str,
        token: str,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.service = service
        self.dashboard_origin = dashboard_origin
        self.token = token


class ReviewWorkbenchRequestHandler(BaseHTTPRequestHandler):
    server: ReviewWorkbenchHTTPServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_OPTIONS(self) -> None:
        if not self._validate_host_and_origin():
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers", "Authorization, Content-Type"
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._validate_request_shell():
            return
        path = urlparse(self.path).path
        try:
            if path == "/v1/session":
                self._send_json(
                    {
                        "schema_version": "1.0",
                        "mode": "local-human-review",
                        "review_id": self.server.service.review_id,
                        "dashboard_origin": self.server.dashboard_origin,
                    }
                )
                return
            if path == "/v1/review":
                self._send_json(self.server.service.projection())
                return
            parts = [unquote(part) for part in path.strip("/").split("/")]
            if (
                len(parts) == 4
                and parts[:2] == ["v1", "products"]
                and parts[3] == "evidence"
            ):
                self._send_json(
                    self.server.service.product_evidence(parts[2])
                )
                return
            self._send_error(
                HTTPStatus.NOT_FOUND, "not_found", "请求的接口不存在。"
            )
        except Exception as error:  # mapped to a stable local API response
            self._send_exception(error)

    def do_POST(self) -> None:
        if not self._validate_request_shell():
            return
        path = urlparse(self.path).path
        try:
            parts = [unquote(part) for part in path.strip("/").split("/")]
            if (
                len(parts) == 4
                and parts[:2] == ["v1", "products"]
                and parts[3] == "decision"
            ):
                document = self._read_decision_body()
                result = self.server.service.submit_decision(
                    parts[2],
                    reviewer=document["reviewer"],
                    decision=document["decision"],
                    inspected_languages=document["inspected_languages"],
                    inspected_materials=document["inspected_materials"],
                    notes=document["notes"],
                )
                self._send_json(
                    {
                        "schema_version": "1.0",
                        "review_id": result.review_id,
                        "product_key": result.product_key,
                        "decision_path": result.decision_path.as_posix(),
                        "decision": result.decision,
                    },
                    status=HTTPStatus.CREATED,
                )
                return
            self._send_error(
                HTTPStatus.NOT_FOUND, "not_found", "请求的接口不存在。"
            )
        except Exception as error:  # mapped to a stable local API response
            self._send_exception(error)

    def _validate_request_shell(self) -> bool:
        return self._validate_host_and_origin() and self._validate_authorization()

    def _validate_host_and_origin(self) -> bool:
        expected_host = (
            f"{self.server.server_address[0]}:"
            f"{self.server.server_address[1]}"
        )
        if self.headers.get("Host") != expected_host:
            self._send_error(
                HTTPStatus.FORBIDDEN,
                "invalid_host",
                "Host 与本地审核服务地址不一致。",
            )
            return False
        if self.headers.get("Origin") != self.server.dashboard_origin:
            self._send_error(
                HTTPStatus.FORBIDDEN,
                "invalid_origin",
                "Origin 不是已配置的本地审核页面。",
            )
            return False
        return True

    def _validate_authorization(self) -> bool:
        received = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"
        if received != expected:
            self._send_error(
                HTTPStatus.UNAUTHORIZED,
                "unauthorized",
                "本地审核服务令牌无效。",
            )
            return False
        return True

    def _read_decision_body(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if content_type.split(";", 1)[0].strip().lower() != "application/json":
            raise WorkbenchRequestError(
                "unsupported_media_type", "Content-Type 必须是 application/json。"
            )
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length is not None else -1
        except ValueError as error:
            raise WorkbenchRequestError(
                "invalid_content_length", "Content-Length 必须是整数。"
            ) from error
        if length < 0:
            raise WorkbenchRequestError(
                "invalid_content_length", "请求缺少有效的 Content-Length。"
            )
        if length > MAX_JSON_BODY_BYTES:
            raise WorkbenchRequestError(
                "body_too_large", "审核决定请求超过允许大小。"
            )
        try:
            document = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WorkbenchRequestError(
                "invalid_json", "请求必须是有效的 UTF-8 JSON。"
            ) from error
        if not isinstance(document, dict):
            raise WorkbenchRequestError(
                "invalid_request", "审核决定请求必须是 JSON 对象。"
            )
        unknown = set(document) - DECISION_FIELDS
        missing = DECISION_FIELDS - set(document)
        if unknown:
            raise WorkbenchRequestError(
                "unknown_request_field",
                "审核决定包含未知字段：" + "、".join(sorted(unknown)) + "。",
            )
        if missing:
            raise WorkbenchRequestError(
                "missing_request_field",
                "审核决定缺少字段：" + "、".join(sorted(missing)) + "。",
            )
        for field in ("reviewer", "decision", "notes"):
            if not isinstance(document[field], str):
                raise WorkbenchRequestError(
                    "invalid_request_field", f"{field} 必须是文本。"
                )
        for field in ("inspected_languages", "inspected_materials"):
            value = document[field]
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise WorkbenchRequestError(
                    "invalid_request_field", f"{field} 必须是文本列表。"
                )
        return document

    def _send_exception(self, error: Exception) -> None:
        if isinstance(error, WorkbenchRequestError):
            status = (
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                if error.code == "body_too_large"
                else HTTPStatus.UNSUPPORTED_MEDIA_TYPE
                if error.code == "unsupported_media_type"
                else HTTPStatus.BAD_REQUEST
            )
            self._send_error(status, error.code, str(error))
            return
        if isinstance(error, ReviewError):
            message = str(error)
            status = (
                HTTPStatus.NOT_FOUND
                if "找不到" in message or "不在审核清单" in message
                else HTTPStatus.CONFLICT
            )
            self._send_error(status, "review_conflict", message)
            return
        if isinstance(error, CatalogError):
            self._send_error(HTTPStatus.NOT_FOUND, "unknown_product", str(error))
            return
        self._send_error(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "internal_error",
            "本地审核服务处理请求时发生内部错误。",
        )

    def _send_error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json(
            {
                "schema_version": "1.0",
                "error": {"code": code, "message": message},
            },
            status=status,
        )

    def _send_json(
        self, value: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_cors_headers(self) -> None:
        self.send_header(
            "Access-Control-Allow-Origin", self.server.dashboard_origin
        )
        self.send_header("Vary", "Origin")


class WorkbenchRequestError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def make_review_workbench_server(
    config: ReviewWorkbenchServerConfig,
) -> tuple[ReviewWorkbenchHTTPServer, str]:
    """Create but do not start one explicit-review loopback server."""

    if config.host != "127.0.0.1":
        raise ReviewError("本地审核服务只能绑定 127.0.0.1。")
    dashboard_origin = _validated_origin(config.dashboard_origin)
    catalog = ProductCatalog.load(config.project_root)
    service = ReviewWorkbenchService(
        catalog,
        review_id=config.review_id,
        reviews_root=config.reviews_root,
    )
    token = config.token or secrets.token_urlsafe(32)
    server = ReviewWorkbenchHTTPServer(
        (config.host, config.port),
        ReviewWorkbenchRequestHandler,
        service=service,
        dashboard_origin=dashboard_origin,
        token=token,
    )
    return server, token


def serve_review_workbench(config: ReviewWorkbenchServerConfig) -> None:
    """Serve until interrupted and print the token only in a URL fragment."""

    server, token = make_review_workbench_server(config)
    host, port = server.server_address
    bridge_url = f"http://{host}:{port}"
    dashboard_url = (
        f"{server.dashboard_origin}/review#bridge={bridge_url}&token={token}"
    )
    print(f"本地审核服务：{bridge_url}", flush=True)
    print(f"审核页面：{dashboard_url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("本地审核服务已停止。", flush=True)
    finally:
        server.server_close()


def _validated_origin(value: str) -> str:
    origin = value.rstrip("/")
    parsed = urlparse(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ReviewError(
            "Dashboard Origin 必须是本机 http(s) origin，不能包含路径、查询或片段。"
        )
    return origin


__all__ = [
    "ReviewWorkbenchHTTPServer",
    "ReviewWorkbenchRequestHandler",
    "ReviewWorkbenchServerConfig",
    "make_review_workbench_server",
    "serve_review_workbench",
]
