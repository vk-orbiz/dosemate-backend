# AGENT.md — FastAPI backend architecture guide

This file tells coding agents (and humans) how to work in this repository. Follow it for every change. If a request conflicts with it, say so before deviating.

Read this together with [CONTRIBUTING.md](CONTRIBUTING.md) (workflow, git conventions) and [.specify/memory/constitution.md](.specify/memory/constitution.md) (the Spec Kit constitution, which restates these rules).

## Stack
Python 3.12+, FastAPI, pydantic v2 / pydantic-settings, SQLAlchemy 2.x (async ORM, `asyncpg` driver), Alembic, PyJWT, email-validator, pytest, ruff, mypy (strict), uv. Database: PostgreSQL.

## Layout and responsibilities

```
app/
  main.py                 composition root: construct and wire everything here, nowhere else
  core/                   config.py, logger.py, errors.py   (no imports from other app packages)
  models/                 frozen pydantic domain models      (stdlib + pydantic only; no framework, db, or http imports)
  storage/postgres/       base.py (Base + naming convention), models/ (ORM rows: the schema), engine.py,
                          migrate.py (migration entry point), migrations/ (Alembic env + versions)
  repo/                   SQLAlchemy statements; converts ORM rows to domain models
  service/                business logic; protocols.py = what services need from repos
  transport/http/         server.py, routes/, dto/ (request validation), middleware/, deps.py, error_map.py, protocols.py
alembic.ini               dev-CLI config only (the app builds its Alembic config in code)
tests/
  unit/                   service tests with fake repos, DTO validation, architecture + route-coverage checks
  integration/            httpx against the real app and a real Postgres (one test per endpoint), migration tests
```

## Dependency rule (never violate)
```
transport  ->  service  ->  service/protocols  <-  repo  ->  storage
        everyone may import: core, models
```
- `service` must not import `repo`, `storage`, `transport`, `sqlalchemy`, `asyncpg` or `fastapi`.
- `repo` must not import `service` or `transport`.
- `transport` must not import `repo`, `storage`, or `service` (routes and deps use `transport/http/protocols.py`; `main.py` passes in the concrete services).
- `models` and `core` import nothing from the rest of `app`.
- Interfaces (`typing.Protocol`) are defined by the **consumer**: `service/protocols.py` for what services need (e.g. `UserRepository`), `transport/http/protocols.py` for what routes and deps need (e.g. `AuthSvc`, `JWTSvc`). Concrete classes satisfy them structurally; do not inherit.
- Third-party confinement: `sqlalchemy` only in `storage/` and `repo/`; `alembic` and `asyncpg` only in `storage/`; `fastapi` and `starlette` only in `transport/` and `main.py`; `models/` uses the standard library and `pydantic` only.
- Enforced by `tests/unit/test_architecture.py` (import rules above, and that only `core/config.py` reads the environment). The checker itself is tested against sample violations.

## Numbered rules (cited as "rule N" in code comments)
1. Dependencies point inward only; `core` and `models` import nothing from the rest of `app`.
2. `service` never imports `repo`, `storage` or `transport`; Protocols are defined by the consumer and satisfied structurally.
3. Repos return domain models, never ORM rows or driver objects; ORM rows stay inside `storage/` and `repo/`.
4. Repos and services raise `DomainError`s; only `transport/http/error_map.py` maps them to HTTP.
5. No global singletons: build everything (engine, sessionmaker, repos, services) in `main.py`, store on `app.state`, expose via `deps.py`.
6. Every response, success or error, is `{"message", "code", "data"}`: errors use `ErrorBody`, successes use `Envelope[T]` (`data` holds the endpoint's own payload).
7. Database statements live only in `repo/`; the schema lives only in the ORM rows (`storage/postgres/models/`) and Alembic revisions; multi-table writes share one session and transaction.
8. Routes are versioned under `/v1`.
9. Only `core/config.py` reads the environment.

## Agent aids
- Each layer folder has a short `CLAUDE.md` (purpose, pattern, do/don't); it loads when you work there.
- Skills in `.claude/skills/`: `add-endpoint`, `add-migration`; Spec Kit commands `speckit-*` (constitution: `.specify/memory/constitution.md`).
- CI (`.github/workflows/ci.yml`) runs ruff, mypy, all tests (including the migration tests), applies the migrations to a fresh database and fails on model/migration drift (`alembic check`).

## Layer rules

**models/** frozen pydantic models (`ConfigDict(frozen=True, from_attributes=True)`), domain vocabulary only (`User`, `Session`, `ErrorBody`). Imports: stdlib and `pydantic` only. `from_attributes` lets repos build them from ORM rows with `model_validate(row)`. Binary data stays `bytes`; wire encoding (base64) belongs to dto.

**repo/**
- Only place database statements appear: SQLAlchemy 2.0 `select()` / `insert()` / `update()` / `delete()` with bound parameters. Never build SQL by interpolating values.
- Return domain models (`User.model_validate(row)`), never ORM rows. There is no separate entity layer.
- The constructor takes the `async_sessionmaker[AsyncSession]` built in `main.py`. Each method opens its own session (`async with self._sessions() as s:` for reads, `async with self._sessions.begin() as s:` for writes). `expire_on_commit` is off.
- Catch `sqlalchemy.exc.IntegrityError` (check `exc.orig.sqlstate`, e.g. `23505` unique violation) and raise a domain error from `core/errors.py` (`EmailAlreadyExists`; no row -> `UserNotFound`). Never leak SQLAlchemy or driver exceptions.
- A write touching more than one table or repo must use one session and transaction. Add a small unit-of-work helper when the first such write appears; do not commit twice.
- No lazy loading in async code: load relationships explicitly (`selectinload`, `joinedload`) in the query.
- One repo class per aggregate, e.g. `UserRepo`.

**storage/postgres/**
- `models/`: SQLAlchemy ORM rows (`Mapped[...]`, `mapped_column`), one file per aggregate, registered in `models/__init__.py`. They are the single source of truth for the schema and never leave `storage/` and `repo/`.
- `base.py`: `Base` and the constraint naming convention (it mirrors Postgres' default names; do not change it without a migration plan). `str` maps to `text` and `datetime` to `timestamptz`.
- `engine.py`: builds the async engine and sessionmaker; the only place the `postgresql+asyncpg://` URL is derived from `Settings.database_url`.
- `migrations/`: Alembic (`env.py` is async; target metadata is `Base.metadata`; the URL comes from `Settings`). `versions/NNNN_slug.py`, ids `0001`, `0002`, ... Never edit an applied revision; add a new one.
- `migrate.py`: `python -m app.storage.postgres.migrate` and the lifespan hook. Runs `alembic upgrade head` under a Postgres advisory lock; adopts databases created by the old hand-rolled migrator by stamping `0001` (see CONTRIBUTING for the cut-over runbook).
- Migrations run at startup only when `DOSEMATE_RUN_MIGRATIONS_ON_STARTUP` is true (default: every environment except production). In production run the migrate command as a release step before starting the new version.

**service/**
- Business rules, validation of domain invariants, hashing, orchestration of repos.
- Constructor takes Protocols (plus other services such as `JWTService`, and a `Logger` if it needs to log). No global state, no `os.environ`, no `Request`/`Response`.
- Raises domain errors only. Never raises `HTTPException`.
- CPU-heavy work (password hashing) runs in `asyncio.to_thread`.

**transport/http/**
- `dto/`: pydantic schemas for request/response bodies. Request DTOs are the validation layer: they inherit `_Request` (`extra="forbid"`) and carry shape, size, format (`EmailStr`) and input-policy validation plus normalisation, using `Field`, `Annotated` validators, `field_validator` and `model_validator`. Failures become a 422 `invalid_input` through the `RequestValidationError` handler. Business rules do not belong in DTOs. Never return domain models directly; never expose secrets (e.g. `password_hash`).
- `routes/`: `APIRouter` functions that take a validated DTO and a service dependency (`AuthSvcDep`), call one service method, map the result to a response DTO and return it wrapped with `ok(...)` (`Envelope[T]`). No SQL, no business rules, no `try/except` translating errors; domain errors propagate. Keep each route under ~10 lines; if it grows, push logic down into the service. All paths under `/v1/<resource>`. Declare `status_code`, `response_model=Envelope[...]` and the error `responses` (`ErrorBody`) for OpenAPI.
- `error_map.py`: the **only** place mapping domain errors to HTTP status codes and error codes (`_ERROR_MAP`, resolved by walking the exception's MRO, so subclasses inherit their parent's mapping). Register new errors here. A `DomainError` with no mapping becomes a 500 `internal_error`.
- `server.py`: `create_app` builds the FastAPI app, includes routers, and registers the exception handlers (`DomainError`, `RequestValidationError`, `HTTPException`, `Exception`).
- `middleware/`: CORS and cross-cutting concerns; configured from `Settings`.
- `deps.py`: `Depends` providers that read from `app.state` (`get_auth_svc`, `get_jwt_svc`) and `get_current_user_id`, exposed as the `CurrentUserId` annotation. It reads the bearer token and raises `InvalidToken` (401) when it is missing or invalid. No route uses it yet; the first protected route (for example a todo API) adds `user_id: CurrentUserId` to its signature and passes the id down to the service so data is scoped to the caller.

**core/errors.py** every error subclasses `DomainError` (`DomainError(message=None, *, data=None)`), for example `InvalidInput`, `NotFound` / `UserNotFound`, `EmailAlreadyExists`, `InvalidCredentials`, `InvalidToken`. No HTTP statuses or codes here. Subclass `NotFound` for "entity does not exist" errors so they map to 404 automatically.

**core/config.py** the only reader of environment variables (`Settings`, pydantic-settings). Add new settings as typed fields; the env prefix is `DOSEMATE_` (field `jwt_secret` is `DOSEMATE_JWT_SECRET`). Update `.env.example` and the table in `README.md`.

## Response contract
All responses share one shape, `{"message", "code", "data"}`. The HTTP status says whether it is a success or an error.

**Success (2xx)**: `Envelope[T]` (`transport/http/dto/common.py`). Routes declare `response_model=Envelope[XResponse]`, return `ok(XResponse(...))` (optionally with a message), and `data` carries the endpoint's own DTO. `code` is `"ok"`. Bodiless responses use 204. `tests/unit/test_response_envelope.py` reads OpenAPI and fails if any 2xx JSON response is not an `Envelope_*` schema.
```json
{"message": "OK", "code": "ok", "data": {"user_id": "...", "email": "a@b.com"}}
```

**Errors (non-2xx)**: the `ErrorBody` envelope (`models/error.py`, also the OpenAPI schema for errors):
```json
{"message": "human readable", "code": "stable_snake_case", "data": null}
```
- Domain errors: status and code from `error_map.py`. Custom exception messages are shown only for statuses below 500.
- Request validation failures (DTO validation): 422, `code: "invalid_input"`, `message: "Invalid request"`, `data` is a list of `{field, message}`. A `DomainError` such as `InvalidInput` raised below transport keeps its own message.
- Unknown route: 404 `not_found`. Other `HTTPException`s: the status phrase as a snake_case code.
- Unknown exceptions are logged (`logger.exception`) and returned as 500 `internal_error` with a generic message.
- Never return stack traces or driver messages.

## Dependency injection
- Construct everything in `main.py` (`build_app`) with constructor injection, in order: settings, logger, engine and sessionmaker, repos, services. Store them on `app.state`, and expose them via `deps.py`.
- No module-level singletons, no importing a ready-made global `db`/`settings` inside layers; pass what is needed in.
- Tests substitute fakes by constructing services with fake repos, or via `app.dependency_overrides`.
- The engine is created lazily (no connection until first use) and disposed in the lifespan.

## Async and typing
- All I/O is `async`. Never call blocking code (password hashing, `requests`, sync DB drivers) on the event loop; use `asyncio.to_thread` if unavoidable. Alembic commands are synchronous: run them with `asyncio.to_thread` from async code (`migrate.py` does).
- Full type hints; `mypy --strict` must pass. Use `Protocol`, not ABCs, for ports.
- Use `ruff` for lint and format.

## Naming
- Files: `snake_case.py`, one concern per file, named for the domain noun (`user.py`, `auth.py`, `todo.py`).
- Classes: `AuthService`, `UserRepo`, `AuthHandler`, `UserEntity`, `SignupRequest`, `SignupResponse`.
- Same-name files across layers (`user.py`, `auth.py`) is intentional: it makes a feature traceable top to bottom.

## Checklist: adding a feature (e.g. "todos")
Inside-out, one small file per layer. Mirror the auth feature (`login`) for style.

1. `models/todo.py` – frozen pydantic domain model.
2. `core/errors.py` – new errors (`TodoNotFound(NotFound)`...).
3. `storage/postgres/models/todo.py` – ORM row (`Mapped`/`mapped_column`, FK to `users.id`, an index for every foreign key and filter column); import it in `storage/postgres/models/__init__.py`.
4. Migration: `uv run alembic revision --autogenerate -m "create todos" --rev-id 0002` (next number), then **review the generated file**: names follow the convention, `downgrade()` is correct, nothing unrelated was picked up. Apply it with `uv run python -m app.storage.postgres.migrate`, then `uv run alembic check` must be clean.
5. `repo/todo.py` – statements, returns models, maps `IntegrityError`.
6. `service/protocols.py` – add `TodoRepository`; `service/todo.py` – logic.
7. `transport/http/protocols.py` – add `TodoSvc`.
8. `dto/todo.py` (validation lives here), `routes/todo.py` (return `ok(...)`; use `CurrentUserId` for protected routes); `deps.py` – add `get_todo_svc` and a `TodoSvcDep` annotation.
9. `error_map.py` – status mapping for new errors.
10. `main.py` – construct repo + service, attach to `app.state`; `server.py` – include router.
11. Tests: unit test for service with fake repo; DTO validation tests; integration test for each endpoint (`tests/unit/test_route_coverage.py` fails the push if an endpoint has none).
12. `ruff check`, `mypy app`, `pytest`, `alembic check` all green.

## Current APIs only (banned patterns)
Libraries move faster than model training data. Use the current API; the toolchain enforces this (`mypy` `deprecated` error code, `pytest` `filterwarnings = ["error"]`, ruff `UP` and `DTZ`). Versions in use: FastAPI 0.16x, Pydantic 2.x, Starlette 1.x, SQLAlchemy 2.x, Alembic 1.x, asyncpg 0.3x.

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
| `session.query(...)` / the `Query` API | `select()` with `await session.scalars(...)` / `session.execute(...)` |
| `declarative_base()` from `sqlalchemy.ext.declarative` | `class Base(DeclarativeBase)` (see `storage/postgres/base.py`) |
| `Column(...)` attributes | `Mapped[...]` + `mapped_column(...)` |
| `create_engine`, sync `Session` / `sessionmaker` | `create_async_engine`, `AsyncSession`, `async_sessionmaker` |
| Lazy-loaded relationships touched in async code | `selectinload` / `joinedload` in the query |
| `default=datetime.utcnow` or naive datetimes on columns | `datetime.now(UTC)` set in code, `timestamptz` columns |
| SQL built by f-string or concatenation with values | Bound parameters / SQLAlchemy constructs |
| Committing `alembic revision --autogenerate` output unreviewed, or editing an applied revision | Review it, fix `downgrade()`, keep names per the convention; add a new revision instead of editing |

If a library warns about deprecation, fix the call; do not silence the warning. When unsure about an API, check the library's current docs instead of recalling it.

## Do / Don't
- Do keep routes thin (about 10 lines); push logic down into the service.
- Do add a unit test for every new service method and a failing-path test for every new error.
- Don't catch `Exception` in routes or services to return custom responses.
- Don't import `fastapi` anywhere outside `transport/http/` and `main.py`.
- Don't put business rules in DTOs, or HTTP concerns in services.
- Don't write database statements outside `repo/`, and don't hand-write DDL: change the ORM row and generate a migration.
- Don't add dependencies without noting why in the PR description.
- Don't edit an applied migration revision; add a new one.

## Commands
```
uv sync                       # install
uv run uvicorn app.main:app --reload
uv run ruff check . && uv run ruff format .
uv run mypy app
uv run pytest
uv run python -m app.storage.postgres.migrate                    # apply migrations (alembic upgrade head)
uv run alembic revision --autogenerate -m "msg" --rev-id 000N    # new revision from model changes (then review it)
uv run alembic check                                             # fails if models and migrations drifted
uv run alembic downgrade -1                                      # roll back one revision (local only)
docker compose -f development/docker-compose.yml up --build
```
