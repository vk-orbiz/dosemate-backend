"""End-to-end guard for `scripts/make_api.py --wire`: scaffold a resource into a copy of the
repo, then lint, type-check and test the result. If a template or an architecture rule drifts
so the generated code no longer passes, this fails.

Slow (copies the repo and runs mypy), so it is not part of the pre-push unit run; CI runs it.
Integration tests of the generated API run only when Postgres is reachable.
"""

import shutil
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
IGNORE = shutil.ignore_patterns(
    ".venv", ".git", ".codegraph", "__pycache__", ".*_cache", "node_modules", "smoke"
)


def _run(args: list[str], cwd: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, f"{' '.join(args)}\n{proc.stdout}\n{proc.stderr}"


def _postgres_reachable() -> bool:
    url = urlsplit(Settings().database_url)
    try:
        with socket.create_connection((url.hostname or "localhost", url.port or 5432), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    copy = tmp_path_factory.mktemp("repo") / "backend"
    shutil.copytree(ROOT, copy, ignore=IGNORE)
    _run(
        [
            "scripts.make_api",
            "gadget",
            "--fields",
            "label:str note:str? rank:int active:bool price:float?",
            "--wire",
        ],
        copy,
    )
    return copy


def test_generated_code_is_lint_clean(scaffolded: Path) -> None:
    _run(["ruff", "check", "."], scaffolded)
    _run(["ruff", "format", "--check", "."], scaffolded)


def test_generated_code_type_checks_strictly(scaffolded: Path) -> None:
    _run(["mypy", "app"], scaffolded)


def test_generated_tests_and_architecture_rules_pass(scaffolded: Path) -> None:
    suites = ["tests/unit"]
    if _postgres_reachable():
        suites.append("tests/integration")
    _run(["pytest", "-q", "-p", "no:cacheprovider", *suites], scaffolded)
