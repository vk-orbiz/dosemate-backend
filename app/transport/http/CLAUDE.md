# transport/http/ — HTTP only
Flow: routes -> deps -> handlers -> validators/dto -> service (via `protocols.py`).
Files: routes/ (APIRouter, `/v1/<resource>`, declare `response_model` + error `responses`), handlers/ (thin classes), dto/ (pydantic bodies; requests `extra="forbid"`), validators/ (DTO -> model, raise `InvalidInput`), deps.py (`Depends`; `CurrentUserId` for protected routes), error_map.py (ONLY place domain error -> status/code), server.py (app factory + exception handlers), protocols.py.
Do: handlers stay < ~20 lines; every error uses `{message, code, data}`; add an integration test per endpoint.
Don't: import repo/storage/service; put `try/except` in handlers; return models or entities; leak secrets or driver messages.
New CRUD resource: `uv run python scripts/make_api.py <name> --fields "..." --wire` (skill `add-endpoint`).
