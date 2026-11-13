# repo/ — the only place SQL lives
Files: `<noun>.py` (`UserRepo(db)`), `entities/<noun>.py` (row shape: `from_record`, `from_model`, `to_model`).
Pattern: copy `user.py`; use `self._db.pool`; module-level `_SQL` constants built from `tables.X`.
Do: `$1` params only; return domain models; translate driver errors to `DomainError` (UniqueViolation -> `EmailAlreadyExists`, no row -> `XNotFound`); scope owned data by `user_id`.
Don't: import service/transport; return `Record` or entities; interpolate user values into SQL.
Satisfies `service/protocols.py` structurally (no inheritance).
