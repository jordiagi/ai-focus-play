# WP-4 — Migrate the radar index onto existing databases (defect 3)

## Problem (reproduced)
`ix_radar_match_time` is declared in `database.py` and is created on a **fresh**
database, but `init_db()` migrates *columns* only and never creates *indexes*. Any
database that predates the index therefore never gets it, and the hottest query in
the app plans as a full `SCAN` plus a temp B-tree sort.

Proof on a DB with the index dropped:
```
EXPLAIN QUERY PLAN SELECT * FROM radar_frames
  WHERE match_id=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp;
-- SCAN radar_frames
-- USE TEMP B-TREE FOR ORDER BY
```

## Files OWNED
- `backend/src/storage/database.py`
- `backend/tests/unit/test_db_migrations.py`  (new)

## Files READ (do not edit)
`backend/src/storage/repository.py`, `backend/src/config.py`

## Contract
Extend the existing migration path in `init_db()` so it also reconciles **indexes**,
not just columns, on an already-existing database. Be generic: reconcile every index
the models declare, rather than hardcoding this one index name. Must be idempotent —
running `init_db()` repeatedly is normal and must not error.

## Acceptance (run it; paste real output)
```
bash scripts/local/verify.sh d3
```
Expected final line: `RESULT: pass=1 fail=0 skip=0`

The probe copies the **live** database, drops the index explicitly, runs `init_db()`,
and re-plans the query. Creating the index only on a fresh database is exactly the
bug and will not pass. Verifying against `create_all` on an empty file proves nothing.

Also:
```
backend/.venv/bin/python -m pytest backend/tests -q
```
must not regress.

## Out of scope
Any other defect. Any other file. Do not "optimise" other queries or add indexes that
the models do not declare.
