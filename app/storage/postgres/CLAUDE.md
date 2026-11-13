# storage/postgres/ — pool, migrations, table names
Files: db.py (`Postgres` pool; `_MIGRATIONS` = ordered `(version, ddl)` tuples), tables.py (name constants).
Do: APPEND a migration with the next integer version for every schema change; add a constant per table; see skill `add-migration`.
Don't: edit an applied migration; put data queries here (they belong in `repo/`); import repo/service/transport.
Migrations run at startup under an advisory lock and are recorded in `schema_migrations`.
