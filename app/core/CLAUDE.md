# core/ — config, logger, domain errors
Files: config.py (`Settings`, `DOSEMATE_` prefix), logger.py (`Logger` Protocol + `ConsoleLogger`), errors.py (`DomainError` tree).
Do: add settings as typed fields (+ `.env.example`, README table); subclass `DomainError` (or `NotFound` for "does not exist"); keep messages safe.
Don't: import any other `app` package; put HTTP status codes here; read `os.environ` outside config.py.
Register new errors in `transport/http/error_map.py` (a `NotFound` subclass needs nothing).
