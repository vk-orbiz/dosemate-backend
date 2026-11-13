# DoseMate Backend Constitution

Details, file layout and examples: `agent.md` (single source of truth). Plans are checked against these principles.

## Principles

1. **Layered architecture (non-negotiable).** `transport -> service -> service/protocols <- repo -> storage`; `core` and `models` import nothing from the rest of `app`. No layer imports one it must not (enforced by `tests/unit/test_architecture.py`).
2. **Consumer-defined Protocols.** Ports are `typing.Protocol`s in `service/protocols.py` and `transport/http/protocols.py`; implementations satisfy them structurally.
3. **Domain errors below transport.** Repos and services raise `DomainError` subclasses; only `transport/http/error_map.py` maps them to HTTP. No `HTTPException`, no `try/except` in handlers.
4. **One error envelope.** Every non-2xx is `{"message", "code", "data"}`; unknown errors are logged and returned as 500 `internal_error`; no stack traces or driver messages.
5. **SQL only in `repo/`.** Parameterised, table names from `tables.py`, models returned (never entities or records), driver errors translated. Schema changes append a migration to `_MIGRATIONS`; never edit an applied one.
6. **Composition root.** Everything is built in `main.py`, stored on `app.state`, exposed through `deps.py`. No singletons. Only `core/config.py` reads the environment (`DOSEMATE_` prefix).
7. **Thin transport.** DTOs for bodies only, validators convert DTO to model (`InvalidInput`), handlers call one service method, routes live under `/v1`. Protected routes use `CurrentUserId` and scope every query by the owner (other users' rows are 404).
8. **Async, typed, tested.** All I/O async (blocking work via `asyncio.to_thread`), `mypy --strict`, ruff. A unit test per service method and error path, an integration test per endpoint.

## Constraints and workflow

- Stack: Python 3.12+, FastAPI, pydantic v2, asyncpg (raw SQL), PyJWT, PostgreSQL, uv. New dependencies need a reason in the PR.
- Security: passwords only as salted PBKDF2 hashes; unknown email and wrong password are indistinguishable; secrets never committed.
- CRUD resources are generated with `scripts/make_api.py` (skill `add-endpoint`); schema changes follow skill `add-migration`.
- Branch `<type>/<number>-<name>` from `main`, Conventional Commits, one logical change per commit. Before pushing: ruff, mypy, pytest (CI also runs `tests/smoke`).

## Governance

This file supersedes other practice; `agent.md` and `CONTRIBUTING.md` must stay consistent with it. Amend via PR (update the docs and, for a changed rule, `test_architecture.py`); every review verifies compliance and justifies any deviation.

**Version**: 1.1.0 | **Ratified**: 2026-11-13 | **Last Amended**: 2026-11-13
