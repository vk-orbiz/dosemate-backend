# Contributing

This guide gets you from clone to a working, hook-protected setup, and explains how to work with coding agents,
CodeGraph and Spec Kit in this repository. For what the API does, see [README.md](README.md).

## 1. One-time setup

```bash
git clone <repo> && cd backend
uv sync                                   # dependencies + dev tools (ruff, mypy, pytest, pre-commit)
cp .env.example .env
docker compose -f development/docker-compose.yml up -d postgres
uv run pre-commit install                 # installs the commit and push hooks
uv run pytest                             # everything should pass
```

If a port is already taken (for example another Postgres on 5432), set `POSTGRES_PORT` and/or `APP_PORT` for
compose and update `DOSEMATE_DATABASE_URL` in `.env` to match.

## 2. Git hooks

Hooks are defined in [.pre-commit-config.yaml](.pre-commit-config.yaml).

| Stage | Checks |
|---|---|
| `git commit` | `ruff check`, `ruff format --check` |
| `git push` | `mypy app` (strict) and `pytest tests/unit` |

Fix format failures with `uv run ruff format .` and many lint failures with `uv run ruff check --fix .`.
`--no-verify` skips the hooks; do not rely on that, CI must run the same checks plus the integration tests.

**Every endpoint needs an integration test.** `tests/unit/test_route_coverage.py` reads the app's OpenAPI document
and fails the push unless some test under `tests/integration/` calls each path and method as
`client.<method>("<path>", ...)`. Business logic also needs unit tests with fake repos (see
`tests/unit/test_auth_service.py`).

## 3. Architecture rules

```
transport  ->  service  ->  (service/protocols)  <-  repo  ->  storage
```

The rules (numbered 1 to 9, cited in code comments) and the per-layer conventions live in
[agent.md](agent.md); that is the single source of truth. `tests/unit/test_architecture.py` enforces the import
rules (including which layers may import `sqlalchemy`, `alembic`, `asyncpg` and `fastapi`) and rule 9, and `tests/unit/test_route_coverage.py` requires an integration test per endpoint.

## 4. Adding an endpoint

Follow the inside-out checklist in [agent.md](agent.md) (or the `add-endpoint` and `add-migration` skills): domain model,
ORM row and migration, repo, service, DTOs, route, wiring, tests. Then run
`uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest && uv run alembic check`.

### Database migrations

The schema is defined by the ORM rows in `app/storage/postgres/models/`. Migrations are Alembic revisions in
`app/storage/postgres/migrations/versions/`, generated from the rows and reviewed by hand.

```bash
uv run python -m app.storage.postgres.migrate                                   # apply (alembic upgrade head)
uv run alembic revision --autogenerate -m "create todos" --rev-id 0002         # create from model changes
uv run alembic check                                                           # no drift between models and migrations
uv run alembic downgrade -1                                                    # roll back one (local only)
uv run alembic upgrade base:head --sql                                         # print SQL for review
```

- **Review every generated revision**: only your change, convention-named constraints, a correct `downgrade()`, and any
  backfill or `server_default` a change to a populated table needs. Use the next number as `--rev-id`.
- **Never edit an applied revision**; fix mistakes with a new one. CI fails if there is more than one head or if the models
  and migrations drift.
- **When migrations run**: at app startup in development and test (`DOSEMATE_RUN_MIGRATIONS_ON_STARTUP`, default on); in
  production set it to `false` and run `python -m app.storage.postgres.migrate` once per release before the new version
  starts. It takes a Postgres advisory lock, so concurrent runs are safe.
- **Rolling back a release**: schema changes should be backward compatible with the previous app version (add before you
  remove). `downgrade` is for development; in production prefer a forward fix.

#### Runbook: first production deploy of the Alembic version (cut-over)

Databases created by the old hand-rolled migrator have a `schema_migrations` table and no `alembic_version`. The migrate
command recognises this and **stamps** revision `0001` without re-running any DDL (the two schemas are identical; this is
tested). If the history is anything other than version `1` it refuses and changes nothing.

1. Take a backup: `pg_dump --format=custom "$DATABASE_URL" > before-alembic.dump`.
2. Set `DOSEMATE_RUN_MIGRATIONS_ON_STARTUP=false` for the new release.
3. Run the release step once: `python -m app.storage.postgres.migrate`. Expect `adopted legacy migration history
   revision='0001'` then `database is at head`.
4. Verify: `SELECT version_num FROM alembic_version;` returns `0001`, and `schema_migrations` still exists.
5. Start the new version.

Rollback: the cut-over only adds the `alembic_version` table, so the previous app version keeps working against the same
database (its `schema_migrations` is untouched). `schema_migrations` and the legacy branch in `migrate.py` are removed in a
later release, once every environment is on Alembic.

## 5. Working with coding agents

[agent.md](agent.md) is the contract for agents and humans: layout, layer rules and conventions. Point your agent at it
(Claude Code also loads [.claude/CLAUDE.md](.claude/CLAUDE.md)). Ask the agent to say so when a request conflicts with it.

Good habits:
- Give agents the architecture rules and a concrete target ("add `GET /v1/users/me`, with the unit and integration tests").
- Always have them run `ruff`, `mypy` and `pytest` before finishing, and review the diff against the rules above.
- Never paste secrets into prompts. `.env` is git-ignored; keep it that way.

### CodeGraph (code navigation for agents)

CodeGraph builds a local knowledge graph of the code and gives agents a structural view through MCP, so they read less
and grep less.

```bash
npm i -g @colbymchenry/codegraph       # once per machine
codegraph init                         # builds .codegraph/ (git-ignored; it syncs itself afterwards)
```

The repo already contains the project-level wiring: [.mcp.json](.mcp.json) registers the MCP server, and
[.claude/settings.json](.claude/settings.json) allows its tools and adds a prompt hook. Restart your agent after the first
`codegraph init`. If `.codegraph/` is missing, agents skip it. CodeGraph sends anonymous usage stats by default; run
`codegraph telemetry off` (or set `CODEGRAPH_TELEMETRY=0`) to opt out.

### Spec Kit (spec-driven development)

[Spec Kit](https://github.com/github/spec-kit) is already initialised for Claude Code: templates and scripts in
`.specify/`, and slash commands in `.claude/skills/speckit-*`.

```bash
uv tool install specify-cli            # optional: the `specify` CLI itself (add ~/.local/bin to your PATH)
```

Use it from your agent, in this order, for any non-trivial feature:

| Command | Purpose |
|---|---|
| `/speckit-constitution` | Amend the project principles (already filled in: [.specify/memory/constitution.md](.specify/memory/constitution.md)). Keep it consistent with section 3 and [agent.md](agent.md). |
| `/speckit-specify` | Describe what to build and why |
| `/speckit-clarify` | Optional: resolve ambiguities before planning |
| `/speckit-plan` | Choose the technical approach (must respect the layer rules) |
| `/speckit-tasks` | Break the plan into ordered tasks |
| `/speckit-analyze`, `/speckit-checklist` | Optional consistency and quality checks |
| `/speckit-implement` | Execute the tasks |
| `/speckit-converge` | Repeat with implement until it reports `Converged` |

Commit the spec artifacts with the feature. Small fixes do not need the full flow.

## 6. Git conventions

### Branch names

Format: `<type>/<short-kebab-description>`, lowercase, ASCII, at most about 50 characters, no spaces or underscores.

| Type | Use for | Example |
|---|---|---|
| `feat` | new behaviour or endpoint | `feat/user-profile-endpoint` |
| `fix` | bug fix | `fix/login-timing-leak` |
| `refactor` | no behaviour change | `refactor/split-auth-service` |
| `test` | tests only | `test/route-coverage-edge-cases` |
| `docs` | documentation only | `docs/contributing-guide` |
| `chore` | tooling, deps, CI, config | `chore/bump-ruff` |
| `hotfix` | urgent production fix, branched from `main` | `hotfix/jwt-expiry` |

- Branch from an up-to-date `main`. Never commit directly to `main`.
- One branch per feature or fix; keep it short-lived and delete it after merge.
- Ticket or Spec Kit feature number goes right after the type: `feat/123-user-profile`, `feat/003-password-reset`.
- Agents: create the branch before making changes, and never reuse a branch for unrelated work.

### Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `<type>(<optional scope>): <summary>`.

- Types match the branch types, plus `perf` and `build`. Scope is the layer or feature, for example `auth`, `repo`, `transport`, `storage`, `deps`.
- Summary: imperative mood ("add", not "added"), lowercase, no trailing period, 72 characters or fewer.
- Body (optional): explain why, not what, wrapped at about 72 characters. Breaking changes: `!` after the type and a `BREAKING CHANGE:` footer.
- One logical change per commit. Never commit `.env`, secrets or generated indexes.

Examples: `feat(auth): add signup and login endpoints`, `fix(repo): map unique violation to EmailAlreadyExists`.

## 7. Pull requests

- Keep changes small and focused; one feature per PR, from a branch named per section 6.
- Before pushing: `uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest`.
- Include tests for new behaviour: unit tests for logic, an integration test for every endpoint.
- Describe what changed and why, and call out any rule you had to bend.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `role "dosemate" does not exist` | The app is talking to a different Postgres than compose. Check `DOSEMATE_DATABASE_URL` and the port. |
| `port is already allocated` | Set `POSTGRES_PORT` / `APP_PORT`, or stop the other container. |
| Integration tests fail to connect | Start Postgres: `docker compose -f development/docker-compose.yml up -d postgres`. |
| `specify: command not found` | Add `~/.local/bin` to your PATH. |
| Hooks not running | `uv run pre-commit install`. |
