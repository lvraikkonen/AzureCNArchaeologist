"""Small safe-read helpers for the v0.5.3 independent boundary."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any


class SafeReadError(ValueError):
    """A requested immutable input is unsafe or cannot be parsed exactly."""


class _DuplicateJsonKey(ValueError):
    pass


def safe_relative_path(value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise SafeReadError(f"Unsafe relative path: {value!s}")
    return relative


def regular_file(root: str | Path, relative: str | Path) -> Path:
    root = Path(root).resolve()
    relative = safe_relative_path(relative)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        try:
            metadata = cursor.lstat()
        except OSError as error:
            raise SafeReadError(
                f"Cannot inspect immutable path {relative.as_posix()}: {error}"
            ) from error
        if stat.S_ISLNK(metadata.st_mode):
            raise SafeReadError(
                f"Immutable path contains a symbolic link: {relative.as_posix()}"
            )
    path = root / relative
    try:
        path.resolve().relative_to(root)
    except ValueError as error:
        raise SafeReadError(
            f"Immutable path escapes its root: {relative.as_posix()}"
        ) from error
    if not stat.S_ISREG(path.lstat().st_mode):
        raise SafeReadError(
            f"Immutable path is not a regular file: {relative.as_posix()}"
        )
    return path


def read_regular_bytes(root: str | Path, relative: str | Path) -> bytes:
    path = regular_file(root, relative)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise SafeReadError(f"Cannot open immutable file {path}: {error}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SafeReadError(f"Immutable path is not a regular file: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is forbidden: {value}")


def strict_json_bytes(
    data: bytes,
    *,
    description: str,
    expected_type: type,
) -> Any:
    try:
        value = json.loads(
            data.decode("utf-8-sig"),
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise SafeReadError(f"Invalid JSON in {description}: {error}") from error
    if not isinstance(value, expected_type):
        raise SafeReadError(
            f"Expected {expected_type.__name__} in {description}, "
            f"got {type(value).__name__}"
        )
    return value

