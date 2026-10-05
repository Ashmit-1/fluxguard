# Turso Database Integration

This guide describes the backend's Turso integration and its scope. **Turso currently stores authentication data only**; it does not replace every local or browser-side data store in the application.

## What changed

The backend auth store now connects directly to a hosted Turso database with the `turso-serverless` DB-API driver over HTTP.

- Required configuration: `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`.
- The app validates both values and fails during startup if either is missing. It does not fall back to a local SQLite path.
- `app/auth/database.py` opens a short-lived remote connection for each auth database operation, enables foreign keys, and closes the connection afterward.
- At startup, the app creates the existing `users` and `sessions` tables and session indexes in Turso with `CREATE ... IF NOT EXISTS`, then deletes expired sessions.
- The existing schema was not changed.
- `app/auth/routes.py` and `app/auth/utils.py` use the Turso connection for signup, login, session creation, and session validation. Signup handles the driver's `IntegrityError` for duplicate usernames.
- `app/api/__init__.py` initializes the remote auth database during application startup; there is no local auth connection to close at shutdown.

## Configuration

For local development, provide these variables in the backend environment (for example, in `backend/.env`):

```dotenv
TURSO_DATABASE_URL=libsql://<your-database>.turso.io
TURSO_AUTH_TOKEN=<your-database-auth-token>
```

Do not commit the auth token. For Cloud Run, configure the URL as an environment variable and provide the token through Cloud Run's secret integration or another secret manager. The backend needs access to create the auth tables/indexes on startup as well as read and write auth records.

## Local SQLite file and migration status

The old local SQLite connection code was removed from the application: there is no longer a `sqlite3.connect(...)`, `DATABASE_URL` local-path setting, or default `auth.db` fallback in the auth database module.

The files `backend/auth.db`, `backend/auth.db-shm`, and `backend/auth.db-wal` may still exist in a development checkout. **They are legacy files and are not read by the current application. They have not been deleted, and their contents have not been migrated to Turso.** The app creates the auth tables in Turso if needed, but that does not copy local users or sessions. Existing local accounts therefore will not automatically exist in Turso.

## Data that is still outside Turso

This integration is limited to authentication:

- **AML transaction analysis:** `app/tools/engine.py` still uses an in-memory DuckDB connection to query `app/data/SAML-D.csv`. It does not use a local DuckDB database file, but these analytical SQL queries do not run against Turso.
- **Chat history:** The backend accepts prior turns in each chat request but does not persist them. The web app stores conversations in browser storage through LocalForage (normally IndexedDB), so they remain on that browser profile and are not stored in Turso.

Moving either of those stores to Turso would require a separate design and implementation. In particular, moving transaction analysis requires importing the dataset and adapting the DuckDB-specific query engine; chat persistence requires adding server-side conversation storage. Neither was done as part of the auth database switch.

## Files involved

- `app/auth/database.py` — Turso configuration, connection lifecycle, schema initialization, and session cleanup.
- `app/auth/routes.py` — signup/login database operations and Turso integrity-error handling.
- `app/auth/utils.py` — session creation and validation database operations.
- `app/api/__init__.py` — auth DB initialization in the FastAPI lifespan.
- `pyproject.toml` and `uv.lock` — `turso-serverless` dependency.

The root `README.md`, `backend.md`, and `auth-spec.md` also describe the updated storage boundary where those documents are maintained. Docker configuration and frontend code were not changed by this integration.
