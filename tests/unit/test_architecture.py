"""Enforces the dependency rules by scanning imports (rules 1, 2, 3)."""

import ast
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


def _imported_layers(path: Path) -> set[str]:
    layers: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            parts = name.split(".")
            if parts[0] == "app" and len(parts) > 1:
                layers.add(parts[1])
    return layers


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_imports(layer: str) -> None:
    violations = [
        f"{path.relative_to(APP)} imports app.{bad}"
        for path in (APP / layer).rglob("*.py")
        for bad in sorted(_imported_layers(path) & FORBIDDEN[layer])
    ]
    assert not violations, "\n".join(violations)


def test_only_config_reads_environment() -> None:
    offenders = [
        str(p.relative_to(APP))
        for p in APP.rglob("*.py")
        if p.name != "config.py" and ("os.environ" in p.read_text() or "getenv" in p.read_text())
    ]
    assert not offenders, offenders
