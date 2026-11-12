# AGENT.md — FastAPI backend architecture guide

This file tells coding agents (and humans) how to work in this repository. Follow it for every change. If a request conflicts with it, say so before deviating.

## Stack
Python 3.12+, FastAPI, pydantic v2 / pydantic-settings, asyncpg (raw SQL), PyJWT, pytest, ruff, mypy (strict), uv.

## Layout and responsibilities

```
app/
  main.py                 composition root: construct and wire everything here, nowhere else
  core/                   config.py, logger.py, errors.py   (no imports from other app packages)
  models/                 pure domain objects                (no framework, db, or http imports)
  storage/postgres/       pool, migrations, table-name constants
  repo/                   SQL + entity->model mapping; repo/entities/ = row shapes
  service/                business logic; protocols.py = what services need from repos
  transport/http/         server.py, routes/, handlers/, dto/, validators/, middleware/, deps.py, error_map.py, protocols.py
  utils/                  small pure helpers
tests/{unit,integaration}
```

## Dependency rule (never violate)
```
transport  ->  service  ->  service/protocols  <-  repo  ->  storage
        everyone may import: core, models, utils
```
- `service` must not import `repo`, `storage`, `transport`, or `asyncpg`.
- `repo` must not import `service` or `transport`.
- `transport` must not import `repo` or `storage`.
- `models` and `core` import nothing from the rest of `app`.
- Interfaces (`typing.Protocol`) are defined by the **consumer**: `service/protocols.py` for what services need, `transport/http/protocols.py` for what handlers need. Concrete classes satisfy them structurally; do not inherit.
- Enforce with an import-linter or ruff `banned-api` rule if available; otherwise check in review.

## Layer rules

**models/** frozen dataclasses or pydantic models, domain vocabulary only. Binary data stays `bytes`; wire encoding (base64) belongs to dto/validators.

**repo/**
- Only place SQL appears. Parameterised queries only (`$1`), never f-string user values. Table names come from `storage/postgres/tables.py`.
- Return domain models, never `asyncpg.Record` or entities.
- Catch driver errors, log them, raise a domain error from `core/errors.py` (`UserNotFound`, `EmailAlreadyExists`, `UnknownError`...). Never leak driver exceptions.
- Writes touching more than one table go in a single transaction (`async with conn.transaction()`), usually in a dedicated `*_repo` like `uservault.py`.
- One repo class per aggregate/table; constructor takes `(db, log)`.

**service/**
- Business rules, validation of domain invariants, hashing, orchestration of repos.
- Constructor takes Protocols + `Logger`. No global state, no `os.environ`, no `Request`/`Response`.
- Raises domain errors only. Never raises `HTTPException`.

**transport/http/**
- `dto/`: pydantic schemas for request/response bodies only. Never return domain models or entities directly; never expose secrets (e.g. `auth_key`).
- `validators/`: convert DTO -> domain models, decode base64, check semantic rules; raise `RequestValidationFailed(code, message)`.
- `handlers/`: thin classes. Parse -> validate -> call one service method -> map to DTO -> set headers/status. No SQL, no business rules, no `try/except` translating errors.
- `routes/`: `APIRouter` wiring only. All paths under `/v1/<resource>`.
- `error_map.py`: the **only** place mapping domain errors to HTTP status codes. Register new errors here when you add them.
- `middleware/`: CORS and cross-cutting concerns; configured from `Settings`.
- `deps.py`: `Depends` providers (services from `app.state`, `get_current_user_id`).

**core/errors.py** every error subclasses `AppError` with a stable snake_case `code` and a safe `message`. No HTTP statuses here.

**core/config.py** the only reader of environment variables. Add new settings as typed fields with the `BLINDKEY_VAULT_` prefix; update `.env.example`.

## Error response contract
All non-2xx responses:
```json
{"message": "human readable", "code": "stable_snake_case", "data": null}
```
Never return stack traces or driver messages. Unknown exceptions are logged and returned as `internal_server_error` (500).

## Dependency injection
- Construct everything in `main.py` (constructor injection), store services on `app.state`, expose via `deps.py`.
- No module-level singletons, no importing a ready-made global `db`/`settings` inside layers; pass what is needed in.
- Tests substitute fakes by constructing services with fake repos or via `app.dependency_overrides`.

## Async and typing
- All I/O is `async`. Never call blocking code (hashing large inputs, `requests`, sync DB drivers) on the event loop; use `asyncio.to_thread` if unavoidable.
- Full type hints; `mypy --strict` must pass. Use `Protocol`, not ABCs, for ports.
- Use `ruff` for lint and format.

## Naming
- Files: `snake_case.py`, one concern per file, named for the domain noun (`auth.py`, `vault.py`).
- Classes: `AuthService`, `UserRepo`, `AuthHandler`, `UserEntity`, `RegisterUserRequest`.
- Same-name files across layers (`user.py`, `auth.py`) is intentional: it makes a feature traceable top to bottom.

## Checklist: adding a feature (e.g. "secrets")
1. `models/secret.py` – domain type.
2. `core/errors.py` – new errors (`SecretNotFound`...).
3. `storage/postgres/tables.py` + migration – table/constants.
4. `repo/entities/secret.py` + `repo/secret.py` – SQL, returns models.
5. `service/protocols.py` – add `SecretRepository`; `service/secret.py` – logic.
6. `transport/http/protocols.py` – add `SecretSvc`.
7. `dto/secret.py`, `validators/secret.py`, `handlers/secret.py`, `routes/secret.py`.
8. `error_map.py` – status mapping for new errors.
9. `main.py` – construct repo + service, attach to `app.state`; `server.py` – include router.
10. Tests: unit test for service with fake repo; integration test for each endpoint.
11. `ruff check`, `mypy app`, `pytest` all green.

## Do / Don't
- Do keep handlers under ~20 lines per method; push logic down.
- Do add a unit test for every new service method and a failing-path test for every new error.
- Don't catch `Exception` in handlers or services to return custom responses.
- Don't import `fastapi` anywhere outside `transport/http/` and `main.py`.
- Don't put business rules in validators, or HTTP concerns in services.
- Don't write SQL outside `repo/`.
- Don't add dependencies without noting why in the PR description.

## Commands
```
uv sync                       # install
uv run uvicorn app.main:app --reload
uv run ruff check . && uv run ruff format .
uv run mypy app
uv run pytest
docker compose -f development/docker-compose.yml up --build
```
