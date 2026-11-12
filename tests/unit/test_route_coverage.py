"""Every documented HTTP route must have an integration test.

Runs with the unit tests (no database needed) and therefore in the pre-push hook, so a
new endpoint can't be pushed without a test that calls it as `client.<method>("<path>", ...)`
somewhere under tests/integration/.
"""

import re
from pathlib import Path

from app.main import build_app

INTEGRATION_DIR = Path(__file__).resolve().parents[1] / "integration"


def _call_pattern(method: str, path: str) -> re.Pattern[str]:
    # `/v1/things/{thing_id}` matches client.get(f"/v1/things/{x}") or ".../123"
    escaped = re.sub(r"\\\{[^}]*\\\}", r"[^\"']*", re.escape(path))
    return re.compile(rf"""client\.{method.lower()}\(\s*f?["']{escaped}["']""")


def test_every_route_has_an_integration_test() -> None:
    source = "\n".join(p.read_text() for p in INTEGRATION_DIR.rglob("test_*.py"))
    # The OpenAPI document is the stable public view of every documented route
    # (app.routes only holds lazy router wrappers in recent FastAPI versions).
    paths = build_app().openapi()["paths"]
    assert paths, "no routes found; the coverage check would pass vacuously"
    missing = [
        f"{method.upper()} {path}"
        for path, operations in paths.items()
        for method in operations
        if not _call_pattern(method, path).search(source)
    ]
    assert not missing, (
        "No integration test calls these endpoints; add one in tests/integration/:\n  "
        + "\n  ".join(missing)
    )
