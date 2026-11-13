# service/ — business rules
Files: `<noun>.py` (`AuthService`), `protocols.py` (ports the services need, e.g. `UserRepository`), `jwt.py`.
Pattern: constructor takes Protocols (and other services); methods are `async` and document `Raises X`.
Do: raise `DomainError` subclasses; run CPU-heavy work via `asyncio.to_thread`; add a unit test with a fake repo per method and per error path.
Don't: import repo/storage/transport/asyncpg/fastapi; raise `HTTPException`; read env or keep global state.
