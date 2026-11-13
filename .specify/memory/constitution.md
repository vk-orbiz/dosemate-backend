# DoseMate Backend Constitution

Details, file layout and examples: `agent.md` (single source of truth). Plans are checked against these principles.

## Principles

1. **Layered architecture (non-negotiable).** `transport -> service -> service/protocols <- repo -> storage`; `core` and `models` import nothing from the rest of `app`. No layer imports one it must not, and third-party packages are confined to their layers: `sqlalchemy` to `storage` and `repo`, `alembic` and `asyncpg` to `storage`, `fastapi` to `transport` and `main`, `models` uses the standard library and `pydantic` only (enforced by `tests/unit/test_architecture.py`).
2. **Consumer-defined Protocols.** Ports are `typing.Protocol`s in `service/protocols.py` and `transport/http/protocols.py`; implementations satisfy them structurally.
3. **Domain errors below transport.** Repos and services raise `DomainError` subclasses; only `transport/http/error_map.py` maps them to HTTP. No `HTTPException`, no `try/except` in routes.
4. **One response envelope.** Every response is `{"message", "code", "data"}`: successes are `Envelope[T]` with the endpoint's payload in `data` (enforced from OpenAPI by a test), errors are `ErrorBody`; unknown errors are logged and returned as 500 `internal_error`; no stack traces or driver messages.
5. **Database access only in `repo/`; the schema only in ORM rows and Alembic.** Repos use SQLAlchemy 2.0 async statements with bound parameters, return pydantic domain models (never ORM rows), and translate `IntegrityError` to domain errors. The ORM rows in `storage/postgres/models/` are the single source of truth for the schema; every change is an Alembic revision generated from them and reviewed by hand. Never edit an applied revision. Multi-table writes share one session and transaction.
6. **Composition root.** Everything (engine, sessionmaker, repos, services) is built in `main.py`, stored on `app.state`, exposed through `deps.py`. No singletons. Only `core/config.py` reads the environment (`DOSEMATE_` prefix).
7. **Thin transport, pydantic validation.** Request DTOs are the single validation layer (shape, size, format, input policy, normalisation; failures are 422 `invalid_input`); business rules live in services. Routes call one service method and map the result to a response DTO, and live under `/v1`. Protected routes use `CurrentUserId` and scope every query by the owner (other users' rows are 404).
8. **Async, typed, tested.** All I/O async (blocking work via `asyncio.to_thread`), `mypy --strict`, ruff. A unit test per service method and error path, an integration test per endpoint.

## Constraints and workflow

- Stack: Python 3.12+, FastAPI, pydantic v2, SQLAlchemy 2.x (async, `asyncpg` driver), Alembic, PyJWT, PostgreSQL, uv. New dependencies need a reason in the PR.
- Security: passwords only as salted PBKDF2 hashes; unknown email and wrong password are indistinguishable; secrets never committed.
- New resources follow the checklist in `agent.md` (skill `add-endpoint`); schema changes follow skill `add-migration`. Migrations run at startup only where `DOSEMATE_RUN_MIGRATIONS_ON_STARTUP` is on (default: all but production); production runs `python -m app.storage.postgres.migrate` as a release step.
- Branch `<type>/<number>-<name>` from `main`, Conventional Commits, one logical change per commit. Before pushing: ruff, mypy, pytest, `alembic check` (CI also applies the migrations to a fresh database).

## Governance

This file supersedes other practice; `agent.md` and `CONTRIBUTING.md` must stay consistent with it. Amend via PR (update the docs and, for a changed rule, `test_architecture.py`); every review verifies compliance and justifies any deviation.

**Version**: 2.1.0 | **Ratified**: 2026-11-13 | **Last Amended**: 2026-11-13

Changelog: 2.1.0 adds the uniform success envelope (principle 4). 2.0.0 replaces raw asyncpg/hand-rolled migrations/entities/validators/handlers with SQLAlchemy + Alembic + pydantic DTO validation (principles 1, 3, 5, 6, 7 reworded).
