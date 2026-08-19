"""Compare two ordinary files through Git without relying on repository state."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class FileComparisonError(RuntimeError):
    """Git could not establish whether two stable files are equal."""


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int


def files_differ(previous: Path, current: Path) -> bool:
    """Return Git's exact file comparison while rejecting moving inputs."""

    previous_before = _identity(previous)
    current_before = _identity(current)
    try:
        completed = subprocess.run(
            [
                "git",
                "--no-pager",
                "diff",
                "--no-index",
                "--quiet",
                "--no-ext-diff",
                "--no-textconv",
                "--",
                str(previous),
                str(current),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise FileComparisonError(f"无法运行 Git 文件比较：{error}") from error

    previous_after = _identity(previous)
    current_after = _identity(current)
    if previous_before != previous_after:
        raise FileComparisonError(f"文件在比较过程中发生变化：{previous}。")
    if current_before != current_after:
        raise FileComparisonError(f"文件在比较过程中发生变化：{current}。")

    if completed.returncode == 0:
        return False
    if completed.returncode == 1:
        return True
    detail = completed.stderr.strip()
    suffix = f" Git 输出：{detail}" if detail else ""
    raise FileComparisonError(
        f"Git 无法比较 {previous} 与 {current}，退出码为 "
        f"{completed.returncode}。{suffix}"
    )


def _identity(path: Path) -> _FileIdentity:
    try:
        state = path.stat()
    except OSError as error:
        raise FileComparisonError(f"无法读取待比较文件 {path}：{error}") from error
    return _FileIdentity(
        device=state.st_dev,
        inode=state.st_ino,
        size=state.st_size,
        modified_ns=state.st_mtime_ns,
        changed_ns=state.st_ctime_ns,
    )


__all__ = ["FileComparisonError", "files_differ"]
