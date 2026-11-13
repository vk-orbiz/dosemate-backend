---
name: add-endpoint
description: Add an API resource or endpoint to this backend following the layered architecture. Use for any new route.
user-invocable: true
---

# Add an endpoint

Work inside-out, one small file per layer. Mirror the auth feature (`login`) for style; the full checklist and rules are in
`agent.md`.

1. `models/<noun>.py`: frozen pydantic domain model (`from_attributes=True`).
2. `core/errors.py`: new errors (`XNotFound(NotFound)` maps to 404 automatically); `error_map.py` only if it needs its own status.
3. `storage/postgres/models/<noun>.py`: ORM row, imported in `models/__init__.py`; then skill `add-migration` for the revision.
4. `repo/<noun>.py`: `select()` statements, returns models, maps `IntegrityError`. Scope owned data by `user_id`.
5. `service/protocols.py`: port; `service/<noun>.py`: logic that raises domain errors.
6. `transport/http/protocols.py`: `XSvc`; `dto/<noun>.py`: request DTOs carry ALL input validation (`Field`, `EmailStr`,
   `field_validator`) and normalisation, limits included; `routes/<noun>.py` (`/v1/...`, `response_model=Envelope[X]`, return `ok(X(...))`, error
   `responses` with `ErrorBody`); `deps.py`: `get_x_svc` + `XSvcDep`.
7. `main.py`: construct repo + service, attach the service to `app.state`; `server.py`: `include_router`.
8. Tests: service unit test with a fake repo (every method and error path), DTO validation tests, and one integration test per
   endpoint calling `client.<method>("<path>", ...)` (route coverage fails the push otherwise).
9. `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest && uv run alembic check`.

Protected route: add `user_id: CurrentUserId`, pass it down, and scope every query by it (other users' rows are 404).
