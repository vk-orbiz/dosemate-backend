# models/ — pure domain objects
Files: one `<noun>.py` per aggregate (`User`, `Session`); `error.py` = `ErrorBody` envelope.
Pattern: frozen pydantic model, `ConfigDict(frozen=True, from_attributes=True)` so repos can `model_validate(orm_row)`; keep input types separate from stored types if they differ.
Do: domain vocabulary only; `bytes` for binary data.
Don't: import anything but the stdlib and pydantic (no fastapi, sqlalchemy, asyncpg or other `app` packages); hold wire formats (base64) or secrets in plaintext.
