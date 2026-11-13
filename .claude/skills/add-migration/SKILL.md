---
name: add-migration
description: Add or change a database table in this backend (append a migration, add the table constant). Use for any schema change.
user-invocable: true
---

# Add a migration

1. `app/storage/postgres/tables.py`: add `THINGS = "things"` (new tables only).
2. `app/storage/postgres/db.py`: append to `_MIGRATIONS` with the NEXT integer version. Never edit or reorder an applied one.
```python
_MIGRATIONS = (
    # ...existing entries stay untouched...
    (
        2,
        f"""
        CREATE TABLE {tables.THINGS} (
            id         uuid        PRIMARY KEY,
            user_id    uuid        NOT NULL REFERENCES {tables.USERS} (id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL
        );
        CREATE INDEX ON {tables.THINGS} (user_id, created_at DESC);
        """,
    ),
)
```
3. Alter an existing table with a new migration (`ALTER TABLE ...`), not by editing migration 1.
4. Use `uuid` ids, `timestamptz`, `NOT NULL` by default, `CHECK` constraints for invariants, an index for every foreign key / filter column.
5. Queries go in `repo/` only. Integration tests apply migrations to a throwaway database automatically (`tests/conftest.py` truncates `users` with CASCADE).
6. Verify: `uv run pytest` (needs Postgres, see CONTRIBUTING).
