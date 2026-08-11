"""Loopback HTTP bridge for the local Dashboard Review Workbench."""

from __future__ import annotations

import argparse
import json
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from src.pipeline.state_store import ManifestConflictError, RepositoryLockError
from src.review.contracts import REJECTION_REASONS, REVIEW_VERDICTS
from src.review.service import ReviewDecisionRequest, ReviewServiceError
from src.review.workbench import (
    ReviewWorkbenchError,
    ReviewWorkbenchService,
    WorkbenchBatchSelection,
)


MAX_JSON_BODY_BYTES = 64 * 1024


@dataclass(frozen=True)
class ReviewWorkbenchServerConfig:
    root: Path
    runs_dir: str | Path
    batch_ids: tuple[str, ...]
    dashboard_origin: str
    host: str = "127.0.0.1"
    port: int = 8765
    token: str | None = None
    history_index: str | Path | None = None


class ReviewWorkbenchHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        *,
        service: ReviewWorkbenchService,
        selection: WorkbenchBatchSelection,
        dashboard_origin: str,
        token: str,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.service = service
        self.selection = selection
        self.dashboard_origin = dashboard_origin.rstrip("/")
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
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._validate_request_shell():
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/v1/session":
                self._send_json({
                    "schema_version": "1.0",
                    "mode": "local_review_workbench",
                    "batches": list(self.server.selection.batch_ids),
                    "dashboard_origin": self.server.dashboard_origin,
                })
                return
            if parsed.path == "/v1/batches":
                self._send_json(self.server.service.list_batches(self.server.selection))
                return
            if parsed.path.startswith("/v1/batches/"):
                parts = [unquote(part) for part in parsed.path.strip("/").split("/")]
                if len(parts) == 4 and parts[0] == "v1" and parts[1] == "batches" and parts[3] == "projection":
                    batch_id = parts[2]
                    self._assert_allowed_batch(batch_id)
                    self._send_json(
                        self.server.service.build_projection(
                            batch_id,
                            history_index=self.server.selection.history_index,
                        )
                    )
                    return
                if (
                    len(parts) == 7
                    and parts[0] == "v1"
                    and parts[1] == "batches"
                    and parts[3] == "items"
                    and parts[6] == "evidence"
                ):
                    batch_id, language, resource_key = parts[2], parts[4], parts[5]
                    self._assert_allowed_batch(batch_id)
                    self._send_json(
                        self.server.service.get_item_evidence(
                            batch_id,
                            language=language,
                            resource_key=resource_key,
                        )
                    )
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "Unknown endpoint")
        except Exception as error:
            self._send_exception(error)

    def do_POST(self) -> None:
        if not self._validate_request_shell():
            return
        parsed = urlparse(self.path)
        try:
            parts = [unquote(part) for part in parsed.path.strip("/").split("/")]
            if (
                len(parts) == 7
                and parts[0] == "v1"
                and parts[1] == "batches"
                and parts[3] == "items"
                and parts[6] == "decision"
            ):
                batch_id, language, resource_key = parts[2], parts[4], parts[5]
                self._assert_allowed_batch(batch_id)
                document = self._read_json_body()
                request = self._decision_request(
                    batch_id=batch_id,
                    item_id=f"{language}/{resource_key}",
                    document=document,
                )
                result = self.server.service.review.decide(request).to_dict()
                status = (
                    HTTPStatus.ACCEPTED
                    if result["projection_status"] == "projection_rebuild_pending"
                    else HTTPStatus.OK
                )
                if status == HTTPStatus.ACCEPTED:
                    result["status"] = "committed_but_refresh_required"
                self._send_json(result, status=status)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "Unknown endpoint")
        except Exception as error:
            self._send_exception(error)

    def _validate_request_shell(self) -> bool:
        return self._validate_host_and_origin() and self._validate_authorization()

    def _validate_host_and_origin(self) -> bool:
        host = self.headers.get("Host")
        allowed_host = f"{self.server.server_address[0]}:{self.server.server_address[1]}"
        if host != allowed_host:
            self._send_error(HTTPStatus.FORBIDDEN, "invalid_host", "Invalid Host header")
            return False
        origin = self.headers.get("Origin")
        if origin != self.server.dashboard_origin:
            self._send_error(HTTPStatus.FORBIDDEN, "invalid_origin", "Invalid Origin header")
            return False
        return True

    def _validate_authorization(self) -> bool:
        authorization = self.headers.get("Authorization")
        if authorization != f"Bearer {self.server.token}":
            self._send_error(HTTPStatus.UNAUTHORIZED, "unauthorized", "Invalid Workbench token")
            return False
        return True

    def _assert_allowed_batch(self, batch_id: str) -> None:
        if batch_id not in self.server.selection.batch_ids:
            raise ReviewWorkbenchError("batch_not_allowed", f"Batch is not allowed: {batch_id}")

    def _read_json_body(self) -> Mapping[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if content_type.split(";", 1)[0].strip().lower() != "application/json":
            self._send_error(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "unsupported_media_type",
                "Content-Type must be application/json",
            )
            raise _AlreadyHandled()
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ReviewWorkbenchError("invalid_content_length", "Content-Length must be an integer") from error
        if length > MAX_JSON_BODY_BYTES:
            self._send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large", "Request body is too large")
            raise _AlreadyHandled()
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReviewWorkbenchError("invalid_json", "Request body must be valid UTF-8 JSON") from error
        if not isinstance(value, Mapping):
            raise ReviewWorkbenchError("invalid_request", "Decision request must be a JSON object")
        return value

    @staticmethod
    def _decision_request(
        *,
        batch_id: str,
        item_id: str,
        document: Mapping[str, Any],
    ) -> ReviewDecisionRequest:
        expected = {
            "expected_revision",
            "reviewer",
            "verdict",
            "reason",
            "notes",
            "inspected_states",
        }
        unknown = set(document) - expected
        missing = expected - set(document)
        if unknown:
            raise ReviewWorkbenchError("unknown_request_field", "Unknown decision request field: " + ", ".join(sorted(unknown)))
        if missing:
            raise ReviewWorkbenchError("missing_request_field", "Missing decision request field: " + ", ".join(sorted(missing)))
        expected_revision = document["expected_revision"]
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            raise ReviewWorkbenchError("invalid_expected_revision", "expected_revision must be an integer")
        reviewer = document["reviewer"]
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ReviewWorkbenchError("invalid_reviewer", "reviewer must be a non-empty string")
        verdict = document["verdict"]
        if verdict not in REVIEW_VERDICTS:
            raise ReviewWorkbenchError("invalid_verdict", "verdict must be approved or rejected")
        reason = document["reason"]
        if reason is not None and reason not in REJECTION_REASONS:
            raise ReviewWorkbenchError("invalid_reason", "reason is not a supported rejection reason")
        notes = document["notes"]
        if not isinstance(notes, str):
            raise ReviewWorkbenchError("invalid_notes", "notes must be a string")
        inspected_states = document["inspected_states"]
        if not isinstance(inspected_states, list):
            raise ReviewWorkbenchError("invalid_inspected_states", "inspected_states must be an array")
        parsed_states: list[Mapping[str, Any]] = []
        for index, value in enumerate(inspected_states):
            if not isinstance(value, Mapping):
                raise ReviewWorkbenchError("invalid_inspected_states", f"inspected_states[{index}] must be an object")
            allowed = {"scope", "state_id"}
            if set(value) - allowed:
                raise ReviewWorkbenchError("invalid_inspected_states", f"inspected_states[{index}] has unknown fields")
            parsed_states.append(dict(value))
        return ReviewDecisionRequest(
            batch_id=batch_id,
            item_id=item_id,
            expected_revision=expected_revision,
            reviewer=reviewer,
            verdict=verdict,
            reason=reason,
            notes=notes,
            inspected_states=tuple(parsed_states),
        )

    def _send_exception(self, error: Exception) -> None:
        if isinstance(error, _AlreadyHandled):
            return
        if isinstance(error, ManifestConflictError):
            self._send_error(HTTPStatus.CONFLICT, "manifest_revision_conflict", str(error))
        elif isinstance(error, RepositoryLockError):
            self._send_error(HTTPStatus.LOCKED, "repository_lock_held", str(error))
        elif isinstance(error, ReviewWorkbenchError):
            status = HTTPStatus.NOT_FOUND if error.code in {"unknown_batch", "unknown_item"} else HTTPStatus.BAD_REQUEST
            if error.code in {"batch_not_allowed", "history_batch_not_allowed"}:
                status = HTTPStatus.FORBIDDEN
            self._send_error(status, error.code, str(error))
        elif isinstance(error, ReviewServiceError):
            status = HTTPStatus.NOT_FOUND if error.code == "unknown_item" else HTTPStatus.CONFLICT
            self._send_error(status, error.code, str(error))
        else:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", str(error))

    def _send_error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json(
            {
                "schema_version": "1.0",
                "error": {"code": code, "message": message},
            },
            status=status,
        )

    def _send_json(self, value: Mapping[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", self.server.dashboard_origin)
        self.send_header("Vary", "Origin")


class _AlreadyHandled(Exception):
    pass


def make_review_workbench_server(
    config: ReviewWorkbenchServerConfig,
) -> tuple[ReviewWorkbenchHTTPServer, str]:
    service = ReviewWorkbenchService(config.root, config.runs_dir)
    selection = service.selection(
        config.batch_ids,
        history_index_path=config.history_index,
    )
    token = config.token or secrets.token_urlsafe(32)
    server = ReviewWorkbenchHTTPServer(
        (config.host, config.port),
        ReviewWorkbenchRequestHandler,
        service=service,
        selection=selection,
        dashboard_origin=config.dashboard_origin,
        token=token,
    )
    return server, token


def serve_review_workbench(config: ReviewWorkbenchServerConfig) -> None:
    server, token = make_review_workbench_server(config)
    host, port = server.server_address
    bridge = f"http://{host}:{port}"
    fragment = f"bridge={bridge}&token={token}"
    dashboard_url = f"{config.dashboard_origin.rstrip('/')}/review#{fragment}"
    print(f"Review Workbench bridge: {bridge}", flush=True)
    print(f"Dashboard URL: {dashboard_url}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def config_from_args(args: argparse.Namespace, *, root: Path) -> ReviewWorkbenchServerConfig:
    return ReviewWorkbenchServerConfig(
        root=root,
        runs_dir=args.runs_dir,
        batch_ids=tuple(args.batch_id or ()),
        dashboard_origin=args.dashboard_origin,
        host=args.host,
        port=args.port,
        history_index=args.history_index,
    )


def parse_query_filters(query: str) -> dict[str, list[str]]:
    return parse_qs(query, keep_blank_values=False)


__all__ = [
    "ReviewWorkbenchHTTPServer",
    "ReviewWorkbenchRequestHandler",
    "ReviewWorkbenchServerConfig",
    "config_from_args",
    "make_review_workbench_server",
    "parse_query_filters",
    "serve_review_workbench",
]
