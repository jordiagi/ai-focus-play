## Package: P3 — the three invented Pydantic defaults, and a probe that catches them

Owner:        claude / sonnet
Files OWNED:  `backend/src/domain/models/match.py`, `scripts/local/verify.py`, `backend/tests/unit/test_analytics_defaults.py` (NEW)
Files READ:   `backend/src/services/pipeline/cv_engine.py`, `backend/src/storage/repository.py`, `backend/tests/unit/test_export_zip.py`, `backend/tests/unit/test_analytics_consistency.py`
Out of scope: everything else. Do **not** edit `cv_engine.py`, `repository.py`, `ml_ingest.py`, any frontend file, `STATE.md` or `PLAN.md`.

### The defect — confirmed live, not suspected

`STATE.md` item **X1** claims the `pass_strings` fabrication was deleted at `c38d62f`.
The *producers* were fixed. The **Pydantic field defaults were not**, and they are
live. Measured on 2026-09-23:

```
$ backend/.venv/bin/python -c "...; a=AnalyticsData(home_stats=TeamStats(), away_stats=TeamStats()); print(a.pass_strings)"
{'home': [18, 12, 8, 4, 3, 2, 1, 0], 'away': [24, 16, 11, 7, 4, 3, 2, 1]}
```

Three invented literals sit in `backend/src/domain/models/match.py:107-119`:

| field | invented default |
| :-- | :-- |
| `pass_locations` | `home {defensive 20.0, middle 55.0, attacking 25.0}`, `away {15.0, 50.0, 35.0}` |
| `possession_locations` | `home {25.0, 50.0, 25.0}`, `away {20.0, 52.0, 28.0}` |
| `pass_strings` | `home [18,12,8,4,3,2,1,0]`, `away [24,16,11,7,4,3,2,1]` |

`backend/tests/unit/test_export_zip.py:139` constructs `AnalyticsData(...)` without
these fields and therefore **materialises the fabricated decay curve today**.

Probe `d10` misses all three because it runs the *real engine*, which passes each
field explicitly. It also checks `pass_locations` against the *old* fallback literal
`[20,20,60]/[25,25,50]`, which is no longer the default — so it would not catch the
current one even by luck.

Note for whoever reads this later: these defaults are also mutable class-level
containers shared across instances. Fixing the honesty problem fixes that too.

### Contract

1. **No invented literal may survive as a default.** The honest default for each of
   the three fields is the empty shape: `{"home": {}, "away": {}}` for the two
   location dicts and `{"home": [], "away": []}` for `pass_strings`. Use a
   `default_factory` so instances do not share one object.
2. **Nothing that currently produces real numbers may change.** `cv_engine.py` and
   the seed already pass `pass_locations` / `possession_locations` / `pass_strings`
   explicitly; their output must be byte-identical after your change. Verify this,
   do not assume it.
3. **Add probe `d12` to `scripts/local/verify.py`**, registered alongside `d10`/`d11`
   in the probe table. It must assert on the **model defaults themselves**, not on
   engine output: constructing `AnalyticsData` with only the two required stats
   arguments must yield empty `pass_strings`, empty `pass_locations`, empty
   `possession_locations` and empty `heatmaps`, and must contain no numeric literal
   in any of them.
4. **`d12` must be negative-tested, and you must show the negative test.** This is
   the same bar `d10` and `d11` were held to. Temporarily restore one invented
   default, run `d12`, capture it **FAILING**, restore your fix, run it again,
   capture it **PASSING**. Both outputs go in your report. A probe that has only
   ever been seen to pass proves nothing.
5. **Fix the consequence in `test_export_zip.py`?** No — that file is not yours. If
   your change breaks it, say so in `not_done` and leave it; the integrator owns the
   call. (It should not break: an empty `pass_strings` is still a valid value.)

### Acceptance — run all of it and paste the real output

```sh
cd /home/ai/workspaces/users/jordi/ai-focus-play
backend/.venv/bin/python -c "
import sys; sys.path.insert(0,'backend/src')
from domain.models.match import AnalyticsData, TeamStats
a=AnalyticsData(home_stats=TeamStats(), away_stats=TeamStats())
b=AnalyticsData(home_stats=TeamStats(), away_stats=TeamStats())
print('pass_strings', a.pass_strings)
print('pass_locations', a.pass_locations)
print('possession_locations', a.possession_locations)
print('heatmaps', a.heatmaps)
a.pass_strings['home'].append(99)
print('shared-object leak:', b.pass_strings['home'])
"
bash scripts/local/verify.sh all
backend/.venv/bin/python -m pytest backend/tests -q 2>&1 | tail -3
```

**Expected output**, exactly:

- the first block prints four empty containers and `shared-object leak: []`
- `verify.sh all` prints `pass=11 fail=0 skip=0` and a `PASS  d12` line
- pytest prints `36 passed` (or more if you added tests), `0 failed`

### Report

Return JSON only:
```json
{"package":"P3-defaults","status":"complete|partial|blocked",
 "files_changed":["..."],"acceptance_command":"...","acceptance_output":"<real, pasted>",
 "d12_negative_test":{"with_fabrication_restored":"<real FAIL output>",
                      "after_fix":"<real PASS output>"},
 "deviations":["..."],"not_done":["..."]}
```
