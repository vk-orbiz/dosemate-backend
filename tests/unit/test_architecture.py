"""Enforces the dependency rules by scanning imports (rules 1, 2, 3, 7, 9)."""

import ast
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"

# layer -> app layers it must NOT import
FORBIDDEN: dict[str, set[str]] = {
    "core": {"models", "storage", "repo", "service", "transport", "main"},
    "models": {"core", "storage", "repo", "service", "transport", "main"},
    "storage": {"repo", "service", "transport", "main"},
    "repo": {"service", "transport", "main"},
    "service": {"repo", "storage", "transport", "main"},
    "transport": {"repo", "storage", "service", "main"},
}

# third-party package -> the only layers allowed to import it (`main` = app/main.py)
CONFINED_PACKAGES: dict[str, set[str]] = {
    "sqlalchemy": {"storage", "repo"},
    "alembic": {"storage"},
    "asyncpg": {"storage"},
    "fastapi": {"transport", "main"},
    "starlette": {"transport", "main"},
}

# `models/` is the pure domain: standard library and pydantic only (no frameworks, no I/O).
MODELS_THIRD_PARTY_ALLOWED = {"pydantic"}


def _imports(source: str) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
    return names


def _app_layers(source: str) -> set[str]:
    parts = (n.split(".") for n in _imports(source))
    return {p[1] for p in parts if p[0] == "app" and len(p) > 1}


def layer_violations(layer: str, source: str) -> list[str]:
    """Every rule broken by `source`, treated as living in `layer`."""
    problems = [
        f"imports app.{bad}" for bad in sorted(_app_layers(source) & FORBIDDEN.get(layer, set()))
    ]
    for top in sorted({n.split(".")[0] for n in _imports(source)}):
        if top in CONFINED_PACKAGES and layer not in CONFINED_PACKAGES[top]:
            problems.append(f"imports {top}, which is confined to {sorted(CONFINED_PACKAGES[top])}")
        is_third_party = top not in sys.stdlib_module_names and top != "app"
        if layer == "models" and is_third_party and top not in MODELS_THIRD_PARTY_ALLOWED:
            problems.append(f"imports {top}; models may only use the stdlib and pydantic")
    return problems


def _layer_of(path: Path) -> str:
    first = path.relative_to(APP).parts[0]
    return first.removesuffix(".py")


def test_layer_rules() -> None:
    violations = [
        f"{path.relative_to(APP)} {problem}"
        for path in sorted(APP.rglob("*.py"))
        for problem in layer_violations(_layer_of(path), path.read_text())
    ]
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize(
    ("layer", "source"),
    [
        ("service", "import sqlalchemy"),
        ("service", "from sqlalchemy.ext.asyncio import AsyncSession"),
        ("service", "from app.repo.user import UserRepo"),
        ("transport", "from sqlalchemy import select"),
        ("transport", "from app.storage.postgres.models import UserRow"),
        ("repo", "import asyncpg"),
        ("repo", "from alembic import command"),
        ("repo", "from fastapi import FastAPI"),
        ("storage", "from fastapi import FastAPI"),
        ("models", "import sqlalchemy"),
        ("models", "from fastapi import Depends"),
        ("models", "import httpx"),
        ("core", "from app.models.user import User"),
    ],
)
def test_checker_flags_violations(layer: str, source: str) -> None:
    """The scanner itself must fail on a violation, or the rules above prove nothing."""
    assert layer_violations(layer, source)


@pytest.mark.parametrize(
    ("layer", "source"),
    [
        ("repo", "from sqlalchemy import select\nfrom app.storage.postgres.models import UserRow"),
        ("storage", "import alembic\nimport asyncpg"),
        ("transport", "from fastapi import APIRouter\nfrom pydantic import BaseModel"),
        ("models", "from pydantic import BaseModel\nfrom datetime import datetime"),
        ("main", "from fastapi import FastAPI"),
    ],
)
def test_checker_allows_legitimate_imports(layer: str, source: str) -> None:
    assert not layer_violations(layer, source)


def test_only_config_reads_environment() -> None:
    offenders = [
        str(p.relative_to(APP))
        for p in APP.rglob("*.py")
        if p.name != "config.py" and ("os.environ" in p.read_text() or "getenv" in p.read_text())
    ]
    assert not offenders, offenders
