# WP-5 — Seed truth and crash recovery (defects 5, 7)

## Problems (reproduced)

1. **The seeded demo analytics contradict the seeded demo events.** Fresh-DB probe:
   analytics claim `home goals=3, away goals=3`, while the seeded events contain
   exactly **one** goal per side. The shot map has 5 entries against 2 shot/goal
   events. `home_stats.tackles=41` and `home_stats.passes_completed=203` are pure
   literals — nothing computes them.
2. **No crash-recovery sweep.** `jobs.status` documents an `interrupted` state
   (`database.py:166`) that **nothing ever sets**; `repository.py:430` only reads it.
   A job that was `running` when the process died stays `running` forever. This was
   observed live: job `8b0441a3` sat at `running`, progress 0.0, indefinitely.

## Files OWNED
- `backend/src/storage/repository.py`
- `backend/tests/unit/test_analytics_consistency.py`

## Files READ (do not edit)
`backend/src/storage/database.py`, `backend/src/domain/models/match.py`

## Contract

**Make the seed honest, do not make the fiction self-consistent.** Inventing a
coherent set of fake totals is worse than the current bug, because it is harder to
detect. The governing rule:

> When a capability is not implemented, show that it is not implemented.

- Derive every seeded analytics number from the seeded events, or set it to `None`.
- `tackles`, `passes_completed`, `pass_strings` and any other quantity the pipeline
  never computes must be `None` so the UI renders `—`. Do not substitute plausible
  numbers.
- The shot map must contain exactly the seeded shot and goal events.
- Add a **startup crash-recovery sweep**: any job left in `running` (or `pending`)
  from a previous process is marked `interrupted` with a clear `error`. Be careful
  not to reap a job belonging to a live process if you can detect one.

## Acceptance (run it; paste real output)
```
bash scripts/local/verify.sh d5 d7
backend/.venv/bin/python -m pytest backend/tests -q
```
Expected final line from verify: `RESULT: pass=2 fail=0 skip=0`.

The d5 probe seeds a **fresh** database and compares analytics against the seeded
events, so patching rows in the existing DB will not pass. The d7 probe plants a
stale `running` job in a copy of the DB and checks that bringing the repository up
reclaims it.

## Out of scope
Other defects. Do not change `database.py` (WP-4 owns it). Do not wire in the real
match video in this package.
