"""One lightweight static dependency firewall for the independent package."""

from __future__ import annotations

import ast
import json
from pathlib import Path


class IndependenceViolation(RuntimeError):
    """The independent package references a forbidden production module."""


def forbidden_prefixes(root: str | Path) -> tuple[str, ...]:
    root = Path(root)
    profile = json.loads(
        (
            root
            / "data/configs/independent-fidelity-profiles/"
            "v0.5.1-minimal.json"
        ).read_text(encoding="utf-8")
    )
    return tuple(profile["forbidden_dependency_prefixes"])


def _forbidden(module: str, prefixes: tuple[str, ...]) -> bool:
    production_source = module.startswith("src.") and not (
        module == "src.independent_fidelity"
        or module.startswith("src.independent_fidelity.")
    )
    return production_source or any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in prefixes
    )


def check_static_dependencies(root: str | Path) -> list[str]:
    """Return stable violations; an empty list is the firewall pass result."""

    root = Path(root).resolve()
    package = root / "src/independent_fidelity"
    prefixes = forbidden_prefixes(root)
    violations: list[str] = []
    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if _forbidden(module, prefixes):
                    violations.append(
                        f"{path.relative_to(root).as_posix()}:{node.lineno}: {module}"
                    )
    return violations


def assert_static_dependencies(root: str | Path) -> None:
    violations = check_static_dependencies(root)
    if violations:
        raise IndependenceViolation(
            "Forbidden independent-fidelity dependencies:\n- "
            + "\n- ".join(violations)
        )
