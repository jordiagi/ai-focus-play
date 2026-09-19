# WP-3 — CV determinism and honest ball/track output (defects 2, 8 + two open items)

## Problems (all reproduced)

1. **Team assignment is non-deterministic.** `cv_engine.py:197` does
   `det["team"] = "home" if best_k == 0 else "away"` over a **K=3** `cv2.kmeans`
   with random init, collapsed onto two labels. In 4 of 6 runs both kits collapsed
   to `"away"`. Which cluster is index 0 is an accident of initialisation.
2. **State leaks across matches.** `cv_engine` is a module-level singleton
   (`cv_engine.py:563`) and `self.team_centers` is never reset in `process_video`,
   so match B inherits match A's kit centroids.
3. **The grass mask eats yellow and lime kits.** `cv_engine.py:86` masks HSV hue
   30-85 as "grass", which overlaps those kit colours, so `_extract_torso_chroma`
   returns `None` for them.
4. **`outcome="saved"` is invented** (`cv_engine.py:438`). The model allows
   `"goal"/"saved"/"missed"/"blocked"` but nothing distinguishes them. We cannot tell
   a save from a block or an off-target shot without GK-contact detection.
5. **Unconfirmed tracks are rendered.** `tracker.py:43` sets `track.confirmed` and
   `tracker.py:115` returns every track anyway, so one real player plus one noise
   blob per frame renders as 8 players.
6. **Coasted ball coordinates escape the pitch.** `cv_engine.py:244` does not clamp
   the Kalman-coasted value; a ball was measured at x=130.1 m on a 105 m pitch.

## Files OWNED
- `backend/src/services/pipeline/cv_engine.py`
- `backend/src/services/pipeline/tracker.py`
- `backend/tests/unit/test_tracker.py`
- `backend/tests/unit/test_team_clustering.py`
- `backend/tests/unit/test_ball_tracking.py`
- `backend/tests/unit/test_cv_determinism.py`  (new)

## Files READ (do not edit)
`backend/src/api/routes/matches.py`, `backend/src/domain/models/match.py`

## Contract

**Do not change the module-level `cv_engine` symbol at `cv_engine.py:563`** — it is
imported by `matches.py:19`, which WP-2 owns. Reset per-match state at the top of
`process_video` instead.

- Make team assignment **deterministic and reproducible**: fixed seed / `n_init`, and
  label the clusters by a *physically grounded* rule rather than cluster index. A
  defensible rule: the two kits differ in mean torso chroma; pick the mapping by a
  stable, data-dependent criterion (e.g. order clusters by hue angle) so the same
  input always yields the same labels. Document the rule in a comment.
- Reset `team_centers` (and any other per-match state) at the start of every
  `process_video` call.
- Fix the grass mask so a yellow or lime kit is not swallowed. Do NOT simply widen
  the mask until it also eats grass — verify both directions.
- Replace the invented `"saved"` with `"unknown"`.
- Filter unconfirmed tracks out of `SoccerTracker.update`'s return value, but a
  genuinely new player must still appear within ~2 frames.
- Clamp coasted ball coordinates to the pitch. Clamping must NOT flip a coasted
  sample to `detected=True`.
- **Do not invent data anywhere.** Where a quantity is unmeasured, emit `None`.

## Acceptance (run it; paste real output)
```
bash scripts/local/verify.sh d8
backend/.venv/bin/python -m pytest backend/tests -q
```
`d8` must end `RESULT: pass=1 fail=0 skip=0`; pytest must not regress from 18 passing.

Additionally, write `backend/tests/unit/test_cv_determinism.py` proving:
- the same synthetic input processed **5 times in one process** yields identical team
  labels (this is the probe that catches a seed that was added but state that still
  leaks);
- processing **two different inputs in one process** gives the same result for the
  second as processing it alone (catches the `team_centers` leak specifically);
- a synthetic lime/yellow torso patch yields non-`None` chroma;
- one persistent detection plus one fresh noise blob per frame yields exactly 1
  tracked player from frame 3 onward;
- no ball coordinate exceeds the pitch bounds.

## Out of scope
Every other defect and file. Do not rewrite the pipeline architecture, do not add a
model, do not touch the GPU path.
