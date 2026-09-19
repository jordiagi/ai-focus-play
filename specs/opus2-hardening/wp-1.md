# WP-1 — Enforce AIFP_READ_ONLY (defect 1)

## Problem (reproduced, not inferred)
`AIFP_READ_ONLY=1` is unenforced. With the flag set, `DELETE /api/matches/{id}`
and `POST /api/matches/{id}/drawings` both succeed, and `/api/capabilities`
reports `read_only: true` **and** `allow_uploads: true` simultaneously.

Mechanisms:
- `backend/src/app/main.py:70` hardcodes `"allow_uploads": True` as a literal, so it
  can never track the flag.
- Enforcement exists in only four places — `repository.py:153,179` and
  `matches.py:275,294` — all of which are highlights routes. Upload, delete-match,
  drawings, teams/swap and journal are ungated.
- `backend/src/config.py:10` reads the env var at **import** time. Flipping it inside
  an already-running process does nothing; only a fresh process observes a change.

This is not theoretical: a probe run against the live DB really did delete the demo
match, because the DELETE was not blocked.

## Files OWNED (you may edit only these)
- `backend/src/app/main.py`
- `backend/src/config.py`
- `backend/src/api/guards.py`  (new)
- `backend/tests/unit/test_backend.py`
- `backend/tests/unit/test_upload_pipeline.py`

## Files READ (do not edit)
`backend/src/api/routes/matches.py`, `backend/src/storage/repository.py`

## Contract
Implement enforcement as **ASGI middleware in `main.py`** (optionally with helpers in
the new `guards.py`) — NOT as `if READ_ONLY:` added throughout `matches.py`.
`matches.py` is owned by WP-2; editing it is an ownership violation and will be
rejected.

- When `READ_ONLY` is on, every mutating HTTP method (`POST`, `PUT`, `PATCH`,
  `DELETE`) under `/api/` returns **403** with a JSON body explaining why.
- All `GET` requests, `/media/*`, `/docs` and `/api/capabilities` keep working.
- `/api/capabilities` must report `allow_uploads` as the **computed** value
  (`not READ_ONLY`), never a literal.
- The existing `internal=` gates in `repository.py` stay as defence in depth. Do not
  remove them; do not edit that file.

## Acceptance (run it; paste real output)
```
bash scripts/local/verify.sh d1
```
Expected final line: `RESULT: pass=1 fail=0 skip=0`

That probe launches two separate uvicorn processes — one with `AIFP_READ_ONLY=1`, one
with `=0` — against an isolated copy of the DB, and checks both that writes are
blocked when the flag is on **and that they still succeed when it is off**. Middleware
that blocks unconditionally fails just as hard as middleware that blocks nothing.

Also required:
```
backend/.venv/bin/python -m pytest backend/tests -q
```
must not regress (18 passing before you start).

## Out of scope
Any other defect. Any file not listed above. Do not touch the frontend.
