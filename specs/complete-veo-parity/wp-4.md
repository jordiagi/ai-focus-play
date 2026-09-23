## Package: P4 — the stats table for ML mode, and three reasons that are now false

Owner:        claude / sonnet
Files OWNED:  `backend/src/services/pipeline/ml_analytics.py` (NEW), `backend/src/services/pipeline/ml_ingest.py`, `backend/src/storage/repository.py`
Files READ:   `backend/src/domain/models/match.py`, `backend/src/services/pipeline/cv_engine.py`, `scripts/local/verify.py`, `STATE.md`, `backend/.local/artifacts/mosaic/score_*.json`
Out of scope: everything else — in particular `match.py` (already updated for you), `scripts/local/verify.py`, and **all of `frontend/`**, which another agent is editing right now.

### Two problems, one package

**Problem 1 — the stats panel is blank, not honest.**
`ml_ingest.py` calls `repo.clear_analytics()` so that an ML-analysed match has no
analytics row at all. The API then 404s and the frontend renders an empty drawer.
The docstring's reasoning is right — mixing the heuristic engine's possession with ML
events would misattribute one pipeline's numbers to the other — but dropping
everything overshoots. The honest answer is an **ML-provenance analytics object**:
rows that ML events genuinely support, and a measured reason for every row they do not.

**Problem 2 — three of the stated reasons are now false.** This is the more serious
one, because the app is currently telling the user something untrue.
`ml_ingest.py`'s `UNAVAILABLE` dict says:

| label | current text | why it is now wrong |
| :-- | :-- | :-- |
| `Shot` | "not attempted: needs shot direction toward a goal mouth, which needs the metric calibration D-A failed to obtain" | It **was** attempted (`detect_shots.py`, commit `070ba47`) and it failed for a different reason — and it needed no metric calibration to fail |
| `Free kick` | "not attempted: its position cloud sits inside Throw-in's with no separating cue (D-B step 10)" | It **was** attempted on a different cue entirely (`detect_setpieces.py`) and scored 0.000 held out |
| `Foul` | "not attempted: no cue measured; whistle audio is not analysed" | A cue **was** measured; it scored 0.143 held out on one lucky hit in four |

Replace all three with the measured outcome. Read the real numbers out of
`backend/.local/artifacts/mosaic/score_shots.json` and `score_setpieces.json` — do not
copy them from this file, and do not round them differently than the artifacts do.
`Save` and `Shot on goal` both say "requires shot detection first"; that is still
true, but it should now say shot detection was attempted and failed, not that it is
untried.

### The rule for which stat rows may carry a number

A row shows a count **only if its detector cleared its own control.** Otherwise the
row is listed in `unavailable` with the measured reason. Applying that rule to what
exists today:

| row | verdict | source |
| :-- | :-- | :-- |
| `goals` | **count it** | `FootballGoal`, F1 0.444, team-aware = team-agnostic |
| `throw_ins` | **count it** | `FootballThrowIn`, F1 0.244, team channel p = 0.020 |
| `corners` | **unavailable** | `FootballCornerKick` F1 0.100 — ties its random control, so it is not a result and its count is not either |
| `shots`, `free_kicks`, `fouls` | **unavailable** | measured failures above |
| `attempts`, `penalties`, `tackles`, `passes_completed`, `possession_won` | **unavailable** | no detector; reuse the existing measured reasons |
| `possession_percent`, `possession_minutes` | **unavailable** | Tier B closed by the pre-registered 15 fps gate: attribution 0.94 → 0.98, accuracy at chance, shirt AUC 0.503 |

`possession_percent` is a non-Optional float defaulting to **50.0**. You cannot
express "never measured" in its value, which is exactly why `AnalyticsData` now has an
`unavailable` map — put the key there. **Do not set it to 0.0**; a zero is as invented
as a fifty.

Counts are **per team**, and only where the team channel is itself a result. Where an
event's team is unknown, it must not be silently attributed to either side — if that
leaves a row unattributable, it is `unavailable`, not zero.

### Contract

1. New `ml_analytics.py` builds an `AnalyticsData` from the ML prediction set with
   `provenance="ml"` and the `unavailable` map filled per the table above. It must
   **pass every field explicitly** and rely on no Pydantic default.
2. `ml_ingest.py` stores that object instead of calling `clear_analytics`. Update its
   module docstring — it currently states the opposite policy as a deliberate refusal,
   and a docstring that contradicts the code is how the next session gets misled.
3. `shot_map`, `pass_locations`, `possession_locations`, `pass_strings` and `heatmaps`
   stay **empty** in ML mode. There is no shot detection, no pass detection and no
   metric calibration. Empty is the honest value.
4. Nothing about the heuristic/demo path may change. `provenance` defaults to
   `"heuristic"` and `unavailable` to `{}`, so an untouched engine keeps its behaviour.
   **Verify this — `d10` and `d5` must still pass.**

### Acceptance — run all of it and paste the real output

```sh
cd /home/ai/workspaces/users/jordi/ai-focus-play
bash scripts/local/verify.sh all
backend/.venv/bin/python -m pytest backend/tests -q 2>&1 | tail -3
backend/.venv/bin/python -c "
import sys,json; sys.path.insert(0,'backend/src')
from services.pipeline.ml_analytics import build_ml_analytics
A='backend/.local/artifacts/mosaic'
a=build_ml_analytics(json.load(open(A+'/pred_all.json')), json.load(open(A+'/manifest_all.json')), json.load(open(A+'/score_all.json')))
print('provenance', a.provenance)
print('goals', a.home_stats.goals, a.away_stats.goals)
print('throw_ins', a.home_stats.throw_ins, a.away_stats.throw_ins)
print('unavailable rows', len(a.unavailable))
for k,v in sorted(a.unavailable.items()): print(' ',k,'->',v[:80])
print('empty surfaces', a.shot_map, a.pass_strings, a.heatmaps)
"
grep -n "not attempted" backend/src/services/pipeline/ml_ingest.py
```

**Expected output:**
- `verify.sh all` → `pass=11 fail=0 skip=0` (d5, d10, d11, d12 all still passing)
- pytest → at least 42 passed, 0 failed
- the python block prints `provenance ml`, a real integer for `goals` and
  `throw_ins`, **at least 10** unavailable rows each with a reason, and empty
  `shot_map` / `pass_strings` / `heatmaps`
- the final grep **must not** list `Shot`, `Free kick` or `Foul` as "not attempted"

### Report

Return JSON only:
```json
{"package":"P4-ml-stats","status":"complete|partial|blocked",
 "files_changed":["..."],"acceptance_command":"...","acceptance_output":"<real, pasted>",
 "rows_counted":["..."],"rows_unavailable":{"row":"reason"},
 "deviations":["..."],"not_done":["..."]}
```
