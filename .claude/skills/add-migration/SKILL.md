---
name: add-migration
description: Add or change a database table in this backend (edit the ORM row, generate and review an Alembic revision). Use for any schema change.
user-invocable: true
---

# Add a migration

The schema is defined by SQLAlchemy ORM rows in `app/storage/postgres/models/`; Alembic revisions in
`app/storage/postgres/migrations/versions/` are generated from them and then reviewed by hand.

1. Edit or add the row class (`Mapped[...]` / `mapped_column`), one file per aggregate, and import it in
   `app/storage/postgres/models/__init__.py` so it registers on `Base.metadata`.
   Use `uuid` ids (`Mapped[UUID]`), `datetime` (`timestamptz`), non-null by default, `CheckConstraint(..., name="...")`
   for invariants, `ForeignKey(..., ondelete=...)`, and an index for every foreign key / filter column.
   Do not name constraints by hand except check constraints: the naming convention in `base.py` does the rest.
2. Generate the revision with the next number (needs the dev database; `DOSEMATE_DATABASE_URL` or `.env`):
   `uv run python -m app.storage.postgres.migrate && uv run alembic revision --autogenerate -m "create things" --rev-id 0002`
3. **Review the generated file.** It must contain only your change, use convention names, drop the autogenerate
   comments, and have a correct `downgrade()`. Add `server_default`s or data backfills by hand where a change needs them
   (for example a new NOT NULL column on a table with rows).
4. Never edit or reorder an applied revision. Fix a mistake with a new revision.
5. Apply and verify: `uv run python -m app.storage.postgres.migrate`, `uv run alembic check` (must report no drift),
   `uv run alembic downgrade -1 && uv run alembic upgrade head` (round trip, local DB only).
6. Queries go in `repo/` only. `uv run pytest` (needs Postgres): integration tests build their database through the same
   Alembic path, and `tests/integration/test_migrations.py` checks head, drift and round trips.
7. Preview SQL for review without a database: `uv run alembic upgrade base:head --sql`.
