# DoseMate Backend

FastAPI + asyncpg (raw SQL) + PostgreSQL, organised as a layered "ports and adapters" architecture.
Currently exposes three endpoints: health, signup and login (JWT).

New here? Read [CONTRIBUTING.md](CONTRIBUTING.md). Working with a coding agent? Read [agent.md](agent.md) too.

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, Python 3.12+ (uv can fetch it).

```bash
uv sync                       # install dependencies into .venv
cp .env.example .env          # local configuration
docker compose -f development/docker-compose.yml up --build -d   # Postgres 18 + the API
```

| What | Where |
|---|---|
| API | http://localhost:8010 |
| API docs (Scalar) | http://localhost:8010/docs |
| Postgres (host) | `localhost:5434`, user/password/db `dosemate` |

Ports are overridable with `APP_PORT` and `POSTGRES_PORT` if they clash with something on your machine.

To run the API on the host (with auto-reload) against the compose Postgres:

```bash
docker compose -f development/docker-compose.yml up -d postgres
uv run uvicorn app.main:app --reload
```

Stop everything with `docker compose -f development/docker-compose.yml down` (add `-v` to wipe the database).

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/v1/health` | Liveness check |
| POST | `/v1/auth/signup` | Create an account with `{email, password}` (password 8 to 128 characters) |
| POST | `/v1/auth/login` | Returns a bearer JWT: `{access_token, token_type, expires_in, user_id}` |

Every error uses one envelope: `{"message": str, "code": str, "data": any | null}`.

```bash
curl -X POST localhost:8010/v1/auth/signup -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"supersecret1"}'
curl -X POST localhost:8010/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"supersecret1"}'
```

Passwords are stored only as salted PBKDF2-HMAC-SHA256 hashes. Unknown emails and wrong passwords return the same `401`.

## Configuration

All settings come from `app/core/config.py` and use the `DOSEMATE_` prefix. Values are read from real environment
variables, then `.env`, then `.env.production`. See [.env.example](.env.example).

| Variable | Default | Notes |
|---|---|---|
| `DOSEMATE_ENV` | `development` | `development`, `test` or `production`. Production disables `/docs` and `/openapi.json`. |
| `DOSEMATE_DATABASE_URL` | `postgresql://dosemate:dosemate@localhost:5434/dosemate` | |
| `DOSEMATE_JWT_SECRET` | dev default | At least 32 characters; the dev default is rejected in production. |
| `DOSEMATE_JWT_TTL_SECONDS` | `3600` | |
| `DOSEMATE_CORS_ORIGINS` | `[]` | JSON list. |
| `DOSEMATE_LOG_LEVEL` | `INFO` | |
| `DOSEMATE_DB_POOL_MIN_SIZE`, `DOSEMATE_DB_POOL_MAX_SIZE` | `1`, `10` | |

## Architecture

```
transport  ->  service  ->  (service/protocols)  <-  repo  ->  storage
                 everyone may import: core, models
```

```
app/
  main.py                 composition root: builds and wires everything, exposes `app`
  core/                   config, logger, domain errors
  models/                 pure domain objects
  storage/postgres/       pool, migrations, table-name constants
  repo/                   the only layer that writes SQL; entities/ are row shapes
  service/                business logic; protocols.py = what services need from repos
  transport/http/         server, routes, handlers, dto, validators, middleware, deps, error_map
tests/
  unit/                   service tests with fake repos, validators, architecture rules
  integration/            httpx against the real app and a real Postgres
```

The rules (enforced by `tests/unit/test_architecture.py` and reviewed by humans) are listed in
[agent.md](agent.md).

## Development commands

```bash
uv run ruff check . && uv run ruff format --check .   # lint + format check
uv run mypy app                                       # strict types
uv run pytest tests/unit                              # fast, no database
uv run pytest                                         # everything; needs Postgres on DOSEMATE_DATABASE_URL
```

Integration tests create and drop their own throwaway database on the server in `DOSEMATE_DATABASE_URL`;
they never touch your development data.

## Docker

The multi-stage `Dockerfile` installs locked dependencies with uv and runs as a non-root user:

```bash
docker build -t dosemate-backend .
```
