# repo/ — the only place database statements live
Files: `<noun>.py` (`UserRepo(sessions)`). There are no entities: ORM rows live in `storage/postgres/models/`.
Pattern: copy `user.py`; constructor takes the `async_sessionmaker`; one session per method (`self._sessions()` to read, `self._sessions.begin()` to write); `select()` + bound parameters; return `Domain.model_validate(row)`.
Do: translate `IntegrityError` (`exc.orig.sqlstate`, `23505` = unique) and missing rows to `DomainError`s; scope owned data by `user_id`; load relationships explicitly (no lazy loading in async).
Don't: import service/transport/asyncpg/alembic; return ORM rows; build SQL from user values; commit outside the session helpers.
Satisfies `service/protocols.py` structurally (no inheritance).
