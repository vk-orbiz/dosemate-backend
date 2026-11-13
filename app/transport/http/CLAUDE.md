# transport/http/ — HTTP only
Flow: routes -> deps (service via `protocols.py`) -> service; request validation happens in `dto/`.
Files: routes/ (APIRouter, `/v1/<resource>`, declare `response_model` + error `responses` with `ErrorBody`), dto/ (pydantic bodies; requests `extra="forbid"` and carry ALL input validation and normalisation), deps.py (`Depends`; `AuthSvcDep`, `CurrentUserId`), error_map.py (ONLY place domain error -> status/code), server.py (app factory + exception handlers), protocols.py.
Do: keep routes ~10 lines (DTO in, one service call, `ok(DTO)` out); EVERY response is `{message, code, data}` (success = `Envelope[T]` from `dto/common.py` with `response_model=Envelope[X]`; error = `ErrorBody`); add an integration test per endpoint.
Don't: import repo/storage/service/sqlalchemy; put `try/except` in routes; return domain models directly; put business rules in DTOs; leak secrets or driver messages.
New resource: follow the checklist in `agent.md` (skill `add-endpoint`).
