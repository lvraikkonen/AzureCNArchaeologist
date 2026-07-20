"""SQLite persistence for orthogonal extraction lifecycle state."""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from src.core.settings import settings

from .models import BatchProcessRecord, ExecutionStatus, PublicationStatus, ReviewStatus, ValidationStatus


class BatchProcessRecordManager:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = str(db_path or settings.BATCH_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    @contextmanager
    def _get_connection(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._get_connection() as connection:
            exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='batch_process_records'").fetchone()
            if exists:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(batch_process_records)")}
                if "processing_status" in columns and "execution_status" not in columns:
                    self._migrate_legacy_table(connection)
            self._create_table(connection)
            connection.commit()

    def _create_table(self, connection: sqlite3.Connection) -> None:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS batch_process_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_key TEXT NOT NULL, product_group TEXT, language TEXT NOT NULL,
                strategy_used TEXT,
                execution_status TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                review_status TEXT NOT NULL,
                publication_status TEXT NOT NULL,
                error_message TEXT, processing_time_ms INTEGER,
                output_file_path TEXT, sidecar_file_path TEXT, html_file_path TEXT,
                content_hash TEXT, extraction_timestamp TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, metadata TEXT
            )
        """)
        for column in ("product_key", "product_group", "execution_status", "validation_status", "extraction_timestamp", "content_hash"):
            connection.execute(f"CREATE INDEX IF NOT EXISTS idx_batch_{column} ON batch_process_records({column})")

    def _migrate_legacy_table(self, connection: sqlite3.Connection) -> None:
        legacy = "batch_process_records_legacy_v01"
        connection.execute(f"DROP TABLE IF EXISTS {legacy}")
        connection.execute(f"ALTER TABLE batch_process_records RENAME TO {legacy}")
        self._create_table(connection)
        mapping = {"pending": "pending", "processing": "running", "success": "succeeded", "failed": "failed", "retry": "pending"}
        rows = connection.execute(f"SELECT * FROM {legacy}").fetchall()
        for row in rows:
            old = dict(row)
            old_status = old.get("processing_status", "pending")
            raw_metadata = old.get("metadata")
            try:
                metadata = json.loads(raw_metadata) if raw_metadata else {}
            except json.JSONDecodeError:
                try:
                    metadata = ast.literal_eval(raw_metadata)
                except Exception:
                    metadata = {"legacy_metadata": raw_metadata}
            metadata["legacy_processing_status"] = old_status
            execution = mapping.get(old_status, "pending")
            validation = "passed" if old_status == "success" else "not_run"
            now = datetime.now(timezone.utc).isoformat()
            connection.execute("""
                INSERT INTO batch_process_records (
                  id, product_key, product_group, language, strategy_used, execution_status, validation_status,
                  review_status, publication_status, error_message, processing_time_ms, output_file_path,
                  sidecar_file_path, html_file_path, content_hash, extraction_timestamp, created_at, updated_at, metadata
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                old.get("id"), old.get("product_key", ""), old.get("product_group"), metadata.get("language", "zh-cn"),
                old.get("strategy_used"), execution, validation, "not_requested", "not_published", old.get("error_message"),
                old.get("processing_time_ms"), old.get("output_file_path"), None, old.get("html_file_path"), old.get("content_hash"),
                old.get("extraction_timestamp"), old.get("created_at") or now, old.get("updated_at") or now, json.dumps(metadata, ensure_ascii=False),
            ))
        connection.execute(f"DROP TABLE {legacy}")
        self._create_table(connection)

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        path = Path(file_path)
        if not path.is_file():
            return ""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def create_record(self, record: BatchProcessRecord) -> int:
        if record.html_file_path and not record.content_hash:
            record.content_hash = self.calculate_file_hash(record.html_file_path)
        record.extraction_timestamp = record.extraction_timestamp or datetime.now(timezone.utc)
        with self._get_connection() as connection:
            cursor = connection.execute("""
                INSERT INTO batch_process_records (
                  product_key, product_group, language, strategy_used, execution_status, validation_status,
                  review_status, publication_status, error_message, processing_time_ms, output_file_path,
                  sidecar_file_path, html_file_path, content_hash, extraction_timestamp, created_at, updated_at, metadata
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record.product_key, record.product_group, record.language, record.strategy_used,
                record.execution_status.value, record.validation_status.value, record.review_status.value,
                record.publication_status.value, record.error_message, record.processing_time_ms,
                record.output_file_path, record.sidecar_file_path, record.html_file_path, record.content_hash,
                record.extraction_timestamp.isoformat(), record.created_at.isoformat(), record.updated_at.isoformat(),
                json.dumps(record.metadata, ensure_ascii=False),
            ))
            connection.commit()
            return int(cursor.lastrowid)

    def update_record(self, record_id: int, **updates) -> bool:
        allowed = {"strategy_used", "execution_status", "validation_status", "review_status", "publication_status", "error_message", "processing_time_ms", "output_file_path", "sidecar_file_path", "content_hash", "metadata"}
        invalid = set(updates) - allowed
        if invalid:
            raise ValueError(f"Invalid batch fields: {sorted(invalid)}")
        for key, value in list(updates.items()):
            if hasattr(value, "value"):
                updates[key] = value.value
            elif key == "metadata":
                updates[key] = json.dumps(value, ensure_ascii=False)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        clause = ", ".join(f"{key} = ?" for key in updates)
        with self._get_connection() as connection:
            cursor = connection.execute(f"UPDATE batch_process_records SET {clause} WHERE id = ?", [*updates.values(), record_id])
            connection.commit()
            return cursor.rowcount > 0

    def get_record(self, record_id: int) -> Optional[BatchProcessRecord]:
        with self._get_connection() as connection:
            row = connection.execute("SELECT * FROM batch_process_records WHERE id = ?", (record_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def get_latest_record_for_product(self, product_key: str, status: Optional[ExecutionStatus] = None) -> Optional[BatchProcessRecord]:
        query = "SELECT * FROM batch_process_records WHERE product_key = ?"
        params: list[Any] = [product_key]
        if status:
            query += " AND execution_status = ?"
            params.append(status.value)
        query += " ORDER BY extraction_timestamp DESC LIMIT 1"
        with self._get_connection() as connection:
            row = connection.execute(query, params).fetchone()
        return self._row_to_record(row) if row else None

    def get_records_by_group(self, product_group: str, status: Optional[ExecutionStatus] = None, limit: Optional[int] = None) -> list[BatchProcessRecord]:
        query = "SELECT * FROM batch_process_records WHERE product_group = ?"
        params: list[Any] = [product_group]
        if status:
            query += " AND execution_status = ?"
            params.append(status.value)
        query += " ORDER BY extraction_timestamp DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with self._get_connection() as connection:
            return [self._row_to_record(row) for row in connection.execute(query, params).fetchall()]

    def get_failed_records(self, since: Optional[datetime] = None) -> list[BatchProcessRecord]:
        query = "SELECT * FROM batch_process_records WHERE execution_status = 'failed'"
        params: list[Any] = []
        if since:
            query += " AND extraction_timestamp >= ?"
            params.append(since.isoformat())
        query += " ORDER BY extraction_timestamp DESC"
        with self._get_connection() as connection:
            return [self._row_to_record(row) for row in connection.execute(query, params).fetchall()]

    def should_process_product(self, product_key: str, html_file_path: str, force: bool = False) -> tuple[bool, str]:
        if force:
            return True, "force_refresh"
        current = self.calculate_file_hash(html_file_path)
        latest = self.get_latest_record_for_product(product_key, ExecutionStatus.SUCCEEDED)
        if not latest or latest.validation_status != ValidationStatus.PASSED:
            return True, "no_previous_validated_result"
        return (latest.content_hash != current, "content_changed" if latest.content_hash != current else "content_unchanged")

    def get_processing_statistics(self, since: Optional[datetime] = None) -> dict[str, Any]:
        where, params = (" WHERE extraction_timestamp >= ?", [since.isoformat()]) if since else ("", [])
        with self._get_connection() as connection:
            execution = dict(connection.execute(f"SELECT execution_status, COUNT(*) FROM batch_process_records{where} GROUP BY execution_status", params).fetchall())
            validation = dict(connection.execute(f"SELECT validation_status, COUNT(*) FROM batch_process_records{where} GROUP BY validation_status", params).fetchall())
            review = dict(connection.execute(f"SELECT review_status, COUNT(*) FROM batch_process_records{where} GROUP BY review_status", params).fetchall())
            publication = dict(connection.execute(f"SELECT publication_status, COUNT(*) FROM batch_process_records{where} GROUP BY publication_status", params).fetchall())
            group_rows = connection.execute(f"SELECT product_group, execution_status, COUNT(*) FROM batch_process_records{where} GROUP BY product_group, execution_status", params).fetchall()
            strategy_rows = connection.execute(f"SELECT strategy_used, execution_status, COUNT(*), AVG(processing_time_ms) FROM batch_process_records{where} GROUP BY strategy_used, execution_status", params).fetchall()
        groups: dict[str, dict[str, int]] = {}
        for group, status, count in group_rows:
            groups.setdefault(group or "unknown", {})[status] = count
        strategies: dict[str, dict[str, dict[str, float]]] = {}
        for strategy, status, count, average in strategy_rows:
            strategies.setdefault(strategy or "unknown", {})[status] = {"count": count, "avg_processing_time_ms": average or 0}
        total = sum(execution.values())
        return {"status_counts": execution, "validation_counts": validation, "review_counts": review, "publication_counts": publication, "group_statistics": groups, "strategy_performance": strategies, "total_records": total, "success_rate": execution.get("succeeded", 0) / max(total, 1) * 100}

    def cleanup_old_records(self, older_than_days: int = 30) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        with self._get_connection() as connection:
            cursor = connection.execute("DELETE FROM batch_process_records WHERE extraction_timestamp < ? AND publication_status != 'published'", (cutoff,))
            connection.commit()
            return cursor.rowcount

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> BatchProcessRecord:
        value = dict(row)
        return BatchProcessRecord(
            id=value["id"], product_key=value["product_key"], product_group=value["product_group"], language=value["language"],
            strategy_used=value["strategy_used"], execution_status=ExecutionStatus(value["execution_status"]),
            validation_status=ValidationStatus(value["validation_status"]), review_status=ReviewStatus(value["review_status"]),
            publication_status=PublicationStatus(value["publication_status"]), error_message=value["error_message"],
            processing_time_ms=value["processing_time_ms"], output_file_path=value["output_file_path"], sidecar_file_path=value["sidecar_file_path"],
            html_file_path=value["html_file_path"], content_hash=value["content_hash"],
            extraction_timestamp=datetime.fromisoformat(value["extraction_timestamp"]) if value["extraction_timestamp"] else None,
            created_at=datetime.fromisoformat(value["created_at"]), updated_at=datetime.fromisoformat(value["updated_at"]),
            metadata=json.loads(value["metadata"] or "{}"),
        )
