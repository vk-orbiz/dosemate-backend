"""Every documented success response must use the `Envelope[...]` shape (`{message, code, data}`).

Reads the OpenAPI document, so a new endpoint that returns a bare DTO fails the push.
"""

from app.main import build_app

# Responses that are legitimately not JSON envelopes (none yet). Add `(method, path)` with a reason.
EXEMPT: set[tuple[str, str]] = set()


def test_every_success_response_uses_the_envelope() -> None:
    paths = build_app().openapi()["paths"]
    assert paths, "no routes found; the check would pass vacuously"
    bare = []
    for path, operations in paths.items():
        for method, operation in operations.items():
            if (method, path) in EXEMPT:
                continue
            for status, response in operation["responses"].items():
                if not status.startswith("2") or status == "204":
                    continue
                schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                if not schema.get("$ref", "").startswith("#/components/schemas/Envelope_"):
                    bare.append(f"{method.upper()} {path} -> {status}")
    assert not bare, "Success responses must be Envelope[...]:\n  " + "\n  ".join(bare)
