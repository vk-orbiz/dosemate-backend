# storage/postgres/ — schema, engine, migrations
Files: `models/` (ORM rows = the schema, one file per aggregate, registered in `models/__init__.py`), `base.py` (`Base`, naming convention), `engine.py` (async engine/sessionmaker, URL derivation), `migrate.py` (entry point + legacy adoption), `migrations/` (Alembic `env.py`, `versions/NNNN_slug.py`).
Do: change the schema by editing an ORM row, then `uv run alembic revision --autogenerate -m "..." --rev-id 000N` and REVIEW the file (correct `downgrade()`, convention names); see skill `add-migration`.
Don't: edit an applied revision; hand-write DDL for model changes; put data queries here (they belong in `repo/`); import repo/service/transport.
Migrations run at startup only when `DOSEMATE_RUN_MIGRATIONS_ON_STARTUP` is true (default everywhere except production); production runs `python -m app.storage.postgres.migrate` as a release step.
