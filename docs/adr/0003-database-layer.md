# 0003 — Database layer: migrations in the package, explicit transactions

- **Status:** Accepted
- **Date:** 2026-11-03
- **Task:** 4 (database)

## Context

The plan specifies SQLAlchemy 2 (sync), Alembic with batch mode, SQLite with WAL, `foreign_keys` and `busy_timeout`, and puts migrations in `backend/alembic/`. Three details were open:

1. **Where migrations live.** The installed app must migrate a library on start-up from a PyInstaller build with an arbitrary working directory.
2. **Locking.** Two processes write to the same file: the API (`serve`) and the job worker (Task 6b). In WAL mode a transaction that reads first and then writes fails *immediately* with "database is locked" if another writer committed in between. `busy_timeout` does not help, because waiting could deadlock.
3. **Transaction control.** Python's `sqlite3` module in its default (legacy) mode decides itself when to emit BEGIN. This does not mix well with SQLAlchemy's transactions and SAVEPOINTs.

## Decision

- **Migrations live in the package: `backend/src/tez/migrations/`.** *Deviation from plan (approved):* the plan has `backend/alembic/`. Inside the package they ship with the build and are found from any working directory. `tez.core.migrations.migrate(db)` runs them from code. `backend/alembic.ini` is only for the developer CLI and points at a git-ignored `backend/.dev/dev.sqlite`. Revision ids are sequential (`--rev-id 0002`).
- **Write sessions start with `BEGIN IMMEDIATE`; read sessions with a plain `BEGIN`.**
  - `Database.write_session()` takes the write lock up front, so a second writer waits up to `busy_timeout` (5 s) instead of failing.
  - `Database.session()` never commits, so stray writes in it are discarded.
- **SQLAlchemy emits BEGIN.** Each connection sets `isolation_level = None` and a `begin` event emits the statement. This is the recipe in the SQLAlchemy SQLite dialect docs, and it makes SAVEPOINT work.
- **Pragmas are set on every connection:**
  - `journal_mode=WAL`, with a warning if it is unavailable, e.g. on some network drives;
  - `foreign_keys=ON`;
  - `busy_timeout=5000`;
  - `synchronous=NORMAL`, which with WAL is durable across application crashes and can lose only the last commit on an OS crash.
- **Migrations run with foreign keys off, then `PRAGMA foreign_key_check`.** Batch mode rebuilds a table by copy-and-rename, and with foreign keys on that could cascade or fail. A violation after migrating is an error.
- **One transaction per upgrade** (`transactional_ddl=True`). Alembic assumes SQLite DDL is not transactional, but it is. A migration that fails half-way leaves the schema untouched.
- **Constraint naming convention** on `Base.metadata`, since batch mode can only drop named constraints.

## Consequences

- Every new migration is checked automatically:
  - a stairway test (each revision up, down, up);
  - an "upgrade head → downgrade base" test;
  - a single-head check;
  - a test that the models match the migrations. A model change without a migration fails CI.
- Code that writes must use `write_session()`. Writing through `session()` silently does nothing; that is deliberate, and the API modules (Task 6+) follow the rule.
- Long write transactions block other writers for their whole duration. Keep them short (no network calls inside a write session).
- New model modules must be imported in `tez/models.py` so Alembic sees them.
