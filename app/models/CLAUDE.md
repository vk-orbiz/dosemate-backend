# models/ — pure domain objects
Files: one `<noun>.py` per aggregate (`User`, `Signup`, `Credentials`, `Session`); `error.py` = `ErrorBody` envelope.
Pattern: `@dataclass(frozen=True, slots=True)`; keep input types separate from stored types (`Todo` vs `TodoDraft`).
Do: domain vocabulary only; `bytes` for binary data.
Don't: import fastapi, pydantic, asyncpg or any other `app` package; hold wire formats (base64) or secrets in plaintext.
