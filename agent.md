# AGENT.md — FastAPI backend architecture guide

This file tells coding agents (and humans) how to work in this repository. Follow it for every change. If a request conflicts with it, say so before deviating.

Read this together with [CONTRIBUTING.md](CONTRIBUTING.md) (workflow, git conventions) and [.specify/memory/constitution.md](.specify/memory/constitution.md) (the Spec Kit constitution, which restates these rules).

## Stack
Python 3.12+, FastAPI, pydantic v2 / pydantic-settings, asyncpg (raw SQL), PyJWT, email-validator, pytest, ruff, mypy (strict), uv. Database: PostgreSQL.

## Layout and responsibilities

```
app/
  main.py                 composition root: construct and wire everything here, nowhere else
  core/                   config.py, logger.py, errors.py   (no imports from other app packages)
  models/                 pure domain objects                (no framework, db, or http imports)
  storage/postgres/       db.py (pool + migrations), tables.py (table-name constants)
  repo/                   SQL + entity->model mapping; repo/entities/ = row shapes
  service/                business logic; protocols.py = what services need from repos
  transport/http/         server.py, routes/, handlers/, dto/, validators/, middleware/, deps.py, error_map.py, protocols.py
tests/
  unit/                   service tests with fake repos, validators, architecture + route-coverage checks
  integration/            httpx against the real app and a real Postgres (one test per endpoint)
```

## Dependency rule (never violate)
```
transport  ->  service  ->  service/protocols  <-  repo  ->  storage
        everyone may import: core, models
```
- `service` must not import `repo`, `storage`, `transport`, or `asyncpg`.
- `repo` must not import `service` or `transport`.
- `transport` must not import `repo`, `storage`, or `service` (handlers and deps use `transport/http/protocols.py`; `main.py` passes in the concrete services).
- `models` and `core` import nothing from the rest of `app`.
- Interfaces (`typing.Protocol`) are defined by the **consumer**: `service/protocols.py` for what services need (e.g. `UserRepository`), `transport/http/protocols.py` for what handlers and deps need (e.g. `AuthSvc`, `JWTSvc`). Concrete classes satisfy them structurally; do not inherit.
- Enforced by `tests/unit/test_architecture.py` (import rules, and that only `core/config.py` reads the environment).

## Numbered rules (cited as "rule N" in code comments)
1. Dependencies point inward only; `core` and `models` import nothing from the rest of `app`.
2. `service` never imports `repo`, `storage` or `transport`; Protocols are defined by the consumer and satisfied structurally.
3. Repos return domain models, never entities or raw records; entities stay inside `repo/`.
4. Repos and services raise `DomainError`s; only `transport/http/error_map.py` maps them to HTTP.
5. No global singletons: build everything in `main.py`, store on `app.state`, expose via `deps.py`.
6. Every error response is `{"message", "code", "data"}`.
7. SQL lives only in `repo/`, table names from `storage/postgres/tables.py`; multi-table writes use one transaction.
8. Routes are versioned under `/v1`.
9. Only `core/config.py` reads the environment.

## Agent aids
- Each layer folder has a short `CLAUDE.md` (purpose, pattern, do/don't); it loads when you work there.
- Skills in `.claude/skills/`: `add-endpoint`, `add-migration`; Spec Kit commands `speckit-*` (constitution: `.specify/memory/constitution.md`).
- CI (`.github/workflows/ci.yml`) runs ruff, mypy, all tests and `tests/smoke` (scaffold + wire + type-check).

## Layer rules

**models/** frozen dataclasses (`@dataclass(frozen=True, slots=True)`), domain vocabulary only (`User`, `Signup`, `Credentials`, `Session`, `ErrorBody`). Binary data stays `bytes`; wire encoding (base64) belongs to dto/validators.

**repo/**
- Only place SQL appears. Parameterised queries only (`$1`), never interpolate user values. Table names come from `storage/postgres/tables.py` (f-string the constants only).
- Return domain models, never `asyncpg.Record` or entities. Entities (`repo/entities/`) have `from_record`, `from_model` and `to_model`, and never leave `repo/`.
- Catch driver errors and raise a domain error from `core/errors.py` (for example `asyncpg.UniqueViolationError` -> `EmailAlreadyExists`, no row -> `UserNotFound`). Never leak driver exceptions.
- Writes touching more than one table go in a single transaction (`async with conn.transaction()`).
- One repo class per aggregate/table, e.g. `UserRepo`; the constructor takes the `Postgres` object (`UserRepo(db)`) and uses `db.pool`.

**storage/postgres/**
- `db.py`: `Postgres` owns the asyncpg pool (constructed unconnected in `main.py`, connected and closed in the lifespan). Schema lives in `_MIGRATIONS`, an ordered tuple of `(version, ddl)`. Only DDL lives here.
- To change the schema, **append** a new `(version, ddl)` with the next integer version. Never edit an applied migration. Migrations run at startup under a Postgres advisory lock and are recorded in `schema_migrations`.
- `tables.py`: table-name constants (`USERS`, `SCHEMA_MIGRATIONS`). Add one per new table.

**service/**
- Business rules, validation of domain invariants, hashing, orchestration of repos.
- Constructor takes Protocols (plus other services such as `JWTService`, and a `Logger` if it needs to log). No global state, no `os.environ`, no `Request`/`Response`.
- Raises domain errors only. Never raises `HTTPException`.
- CPU-heavy work (password hashing) runs in `asyncio.to_thread`.

**transport/http/**
- `dto/`: pydantic schemas for request/response bodies only (`SignupRequest`, `LoginResponse`...). Request DTOs inherit `_Request` (`extra="forbid"`) and carry shape/size limits. Never return domain models or entities directly; never expose secrets (e.g. `password_hash`).
- `validators/`: convert DTO -> domain models and check semantic rules (valid email, password policy); raise `InvalidInput(message)`.
- `handlers/`: thin classes. Parse -> validate -> call one service method -> map to DTO. No SQL, no business rules, no `try/except` translating errors; domain errors propagate.
- `routes/`: `APIRouter` wiring only. All paths under `/v1/<resource>`. Declare `status_code`, `response_model` and the error `responses` (`ErrorResponse`) for OpenAPI.
- `error_map.py`: the **only** place mapping domain errors to HTTP status codes and error codes (`_ERROR_MAP`, resolved by walking the exception's MRO, so subclasses inherit their parent's mapping). Register new errors here. A `DomainError` with no mapping becomes a 500 `internal_error`.
- `server.py`: `create_app` builds the FastAPI app, includes routers, and registers the exception handlers (`DomainError`, `RequestValidationError`, `HTTPException`, `Exception`).
- `middleware/`: CORS and cross-cutting concerns; configured from `Settings`.
- `deps.py`: `Depends` providers that read from `app.state` (`get_auth_handler`, `get_jwt_svc`) and `get_current_user_id`, exposed as the `CurrentUserId` annotation. It reads the bearer token and raises `InvalidToken` (401) when it is missing or invalid. No route uses it yet; the first protected route (for example a todo API) adds `user_id: CurrentUserId` to its signature and passes the id down to the handler and service so data is scoped to the caller.

**core/errors.py** every error subclasses `DomainError` (`DomainError(message=None, *, data=None)`), for example `InvalidInput`, `NotFound` / `UserNotFound`, `EmailAlreadyExists`, `InvalidCredentials`, `InvalidToken`. No HTTP statuses or codes here. Subclass `NotFound` for "entity does not exist" errors so they map to 404 automatically.

**core/config.py** the only reader of environment variables (`Settings`, pydantic-settings). Add new settings as typed fields; the env prefix is `DOSEMATE_` (field `jwt_secret` is `DOSEMATE_JWT_SECRET`). Update `.env.example` and the table in `README.md`.

## Error response contract
All non-2xx responses use the `ErrorBody` envelope (`models/error.py`, documented in OpenAPI as `ErrorResponse`):
```json
{"message": "human readable", "code": "stable_snake_case", "data": null}
```
- Domain errors: status and code from `error_map.py`. Custom exception messages are shown only for statuses below 500.
- Request body validation failures: 422, `code: "invalid_input"`, `data` is a list of `{field, message}`.
- Unknown route: 404 `not_found`. Other `HTTPException`s: the status phrase as a snake_case code.
- Unknown exceptions are logged (`logger.exception`) and returned as 500 `internal_error` with a generic message.
- Never return stack traces or driver messages.

## Dependency injection
- Construct everything in `main.py` (`build_app`) with constructor injection, in order: settings, logger, `Postgres`, repos, services, handlers. Store them on `app.state`, and expose them via `deps.py`.
- No module-level singletons, no importing a ready-made global `db`/`settings` inside layers; pass what is needed in.
- Tests substitute fakes by constructing services with fake repos, or via `app.dependency_overrides`.

## Async and typing
- All I/O is `async`. Never call blocking code (password hashing, `requests`, sync DB drivers) on the event loop; use `asyncio.to_thread` if unavoidable.
- Full type hints; `mypy --strict` must pass. Use `Protocol`, not ABCs, for ports.
- Use `ruff` for lint and format.

## Naming
- Files: `snake_case.py`, one concern per file, named for the domain noun (`user.py`, `auth.py`, `todo.py`).
- Classes: `AuthService`, `UserRepo`, `AuthHandler`, `UserEntity`, `SignupRequest`, `SignupResponse`.
- Same-name files across layers (`user.py`, `auth.py`) is intentional: it makes a feature traceable top to bottom.

## Checklist: adding a feature (e.g. "todos")
Shortcut for a user-owned CRUD resource: `uv run python scripts/make_api.py todo --fields "title:str description:str? done:bool" --wire` (run with `--dry-run` first). It writes the new per-layer files and tests (steps 1, 4, 5, 7, 10) and, with `--wire`, edits the shared files (steps 2, 3, 5, 6, 8, 9); without `--wire` it prints the snippets to paste. It refuses to overwrite without `--force`. Then replace the generic logic with the real business rules. Field types: `str`, `int`, `bool`, `float`, optional with `?`. Templates: `scripts/templates/`.

1. `models/todo.py` – domain type.
2. `core/errors.py` – new errors (`TodoNotFound(NotFound)`...).
3. `storage/postgres/tables.py` – table constant (`TODOS`); `storage/postgres/db.py` – append migration `(next_version, ddl)` to `_MIGRATIONS`.
4. `repo/entities/todo.py` + `repo/todo.py` – SQL, returns models.
5. `service/protocols.py` – add `TodoRepository`; `service/todo.py` – logic.
6. `transport/http/protocols.py` – add `TodoSvc`.
7. `dto/todo.py`, `validators/todo.py`, `handlers/todo.py`, `routes/todo.py` (use `CurrentUserId` for protected routes); `deps.py` – add `get_todo_handler` and a `TodoHandlerDep` annotation.
8. `error_map.py` – status mapping for new errors.
9. `main.py` – construct repo + service + handler, attach to `app.state`; `server.py` – include router.
10. Tests: unit test for service with fake repo; integration test for each endpoint (`tests/unit/test_route_coverage.py` fails the push if an endpoint has none).
11. `ruff check`, `mypy app`, `pytest` all green.

## Current APIs only (banned patterns)
Libraries move faster than model training data. Use the current API; the toolchain enforces this (`mypy` `deprecated` error code, `pytest` `filterwarnings = ["error"]`, ruff `UP` and `DTZ`). Versions in use: FastAPI 0.16x, Pydantic 2.x, Starlette 1.x, asyncpg 0.3x.

| Don't | Do |
|---|---|
| `@app.on_event("startup" / "shutdown")` | `lifespan=` with `@asynccontextmanager` (see `main.py`; that decorator is current, not deprecated) |
| `model.dict()`, `.json()`, `.parse_obj()`, `.copy()` | `model_dump()`, `model_dump_json()`, `model_validate()`, `model_copy()` |
| `class Config:` inside a pydantic model | `model_config = ConfigDict(...)` |
| `@validator`, `@root_validator` | `@field_validator`, `@model_validator` |
| `datetime.utcnow()`, `datetime.utcfromtimestamp()`, naive datetimes | `datetime.now(UTC)` |
| `typing.List`, `Dict`, `Optional[X]`, `Union[X, Y]` | `list[...]`, `dict[...]`, `X \| None`, `X \| Y` |
| `asyncio.get_event_loop()` | `asyncio.get_running_loop()`; `asyncio.run()` at the entry point |
| `Depends()` default values in signatures | `Annotated[T, Depends(...)]` (see `deps.py`) |

If a library warns about deprecation, fix the call; do not silence the warning. When unsure about an API, check the library's current docs instead of recalling it.

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
