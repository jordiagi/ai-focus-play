## Package: P1 — FootballShot detector

Owner:        codex / gpt-5.6-sol
Files OWNED:  `backend/src/services/pipeline/gpu_job/mosaic/detect_shots.py` (NEW — create it; it must not exist before you start)
Files READ:   `specs/complete-veo-parity/spec.md` (§3.1, §3.2 bind you), `backend/src/services/pipeline/gpu_job/mosaic/detect_restarts.py`, `detect_goals.py`, `detect_out_of_play.py`, `merge_predictions.py`, `scripts/local/score-benchmark.py`, `benchmarks/raw/veo_events_447.csv`, `benchmarks/veo_reference.json`, and every artifact under `backend/.local/artifacts/mosaic/`
Out of scope: **every other file in the repo.** Do not edit `STATE.md`, `PLAN.md`, the spec, any existing detector, `merge_predictions.py`, or the scoring harness. Do not create artifacts outside `backend/.local/artifacts/mosaic/`. Do not change any existing artifact.

### The job

Build the one Tier-A event type that was never attempted: `FootballShot`, 25 events
in the 447-event benchmark (14 in period 1, 11 in period 2).

### What you may rely on (already measured, do not re-derive)

- `ball_track.json` — a bare JSON **list** of 10,994 points
  `{"t": seconds, "u": px, "v": px, "size": px, "conf": 0..1}` in **panorama** pixels
  at a ~5 fps grid, 58.6 % coverage of the match.
- `ball5_pano.json` — raw per-frame ball candidates before Viterbi.
- `pitch_frame.json` — the non-metric `(xi, eta)` frame:
  ```python
  xi  = (u - fr["u_lo"]) / (fr["u_hi"] - fr["u_lo"])
  vf, vn = np.polyval(fr["p_far"], u), np.polyval(fr["p_near"], u)
  eta = (v - vf) / max(vn - vf, 1.0)
  ```
  `xi` runs along the pan ("length-ish"), `eta` across it. **`xi=0` is not a goal line
  and `eta=0/1` are not touchlines.** Every threshold you use must be *fitted*, never
  assumed from geometry.
- `pred_restarts_teamed.json` carries `goal_xi` — the already-validated defend-end map
  (B10: 24/24 on true times, 8/8 held out). **Reuse it. Do not re-fit it.**
- Period bounds: p1 = `[562.3, 2879.3]`, p2 = `[3674.4, 6132.1]` video seconds.
- The benchmark's `match_tolerance_s` for `FootballShot` is **5.0 s** (read it from
  `benchmarks/veo_reference.json`; do not hardcode and do not change it).

### The signal you are looking for (period-1 evidence only)

The 14 period-1 shots are bimodal along the pitch length in Veo's own normalised
coordinates — x in 0.05–0.25 (n=8) and 0.77–0.93 (n=6), never the middle third. So a
shot is the ball in an attacking third moving fast toward that end's goal. Express
that in `(xi, eta)` and fit every threshold on period 1.

You are free to choose the feature. Sensible candidates: signed `d(xi)/dt` toward
`goal_xi`, the magnitude of panorama-pixel speed, the ball's `size` (a struck ball
nearer the camera is bigger), and the track's local coverage.

### Hard protocol rules — violating any of these invalidates the package

1. **Fit on period 1 only.** Sweep, tune, look at, and iterate on period 1 as much as
   you like. **Touch period 2 exactly once**, at the end, with the configuration
   frozen. Do not tune anything after seeing a period-2 number. If you look at period
   2 and then change a parameter, say so explicitly in `deviations`.
2. **Apply the prediction budget (B14)** the same way `detect_restarts.py` does:
   sweep `K` over `[1.0, 1.5, 2.0, 3.0]` capping `n_pred` at `K × n_ref(period 1)`,
   choose the smallest `K` whose period-1 F1 is within 5 % of unconstrained.
3. **Compute three controls and write all three into the output doc:**
   - `chance`: a random detector emitting the same K predictions uniformly over the
     in-play span, ≥ 200 trials, report mean and p90 F1.
   - `oop_proxy`: **the control that matters.** Load `pred_oop.json`, relabel every
     one of its predictions as `FootballShot`, score that, report its F1. Your
     detector must beat this or it has found stoppages, not shots.
   - `period1_vs_period2`: both F1s, stated separately, never averaged.
4. **Emit no team.** Shot team attribution is not in scope; omit the field rather
   than guessing. The metric rewards guessing — see `STATE.md:221`.
5. **Record the command.** The `--out` doc's first two keys must be
   `"job"` and `"command": " ".join(sys.argv)`, exactly as `detect_restarts.py` does.
6. **Do not import, read, or key off Veo's `x`/`z` columns at inference time.** They
   are the scoreboard. Using them to *choose* a threshold on period 1 is training
   supervision and is allowed (that is how every existing detector works); using them
   to *place* a prediction is leakage and fails the package.

### Deliverables

- `detect_shots.py` with a CLI mirroring `detect_restarts.py`:
  `--track --candidates --frame --restart-pred --bench --pred --manifest --out --fps --budgets --budget-tolerance --p1 --p2`
- `backend/.local/artifacts/mosaic/pred_shots.json` → `{"events":[{"video_s","event_type":"FootballShot","period"}]}`
- `backend/.local/artifacts/mosaic/manifest_shots.json` → `{"attempted":["FootballShot"],"tuned_on":"period1","not_attempted":{...}}`
- `backend/.local/artifacts/mosaic/score_shots.json` → the self-scoring doc with `command`, the budget sweep, both periods, and all three controls.

### Contract

The package is **complete** whichever way the gate falls. A measured FAIL, reported
honestly with its numbers, is a successful package. A PASS you cannot reproduce is a
failed one.

### Acceptance — run it and paste the real output

```sh
cd /home/ai/workspaces/users/jordi/ai-focus-play
V=backend/.venv/bin/python; A=backend/.local/artifacts/mosaic
$V backend/src/services/pipeline/gpu_job/mosaic/detect_shots.py \
   --track $A/ball_track.json --candidates $A/ball5_pano.json \
   --frame $A/pitch_frame.json --restart-pred $A/pred_restarts_teamed.json \
   --pred $A/pred_shots.json --manifest $A/manifest_shots.json --out $A/score_shots.json
$V -c "import json;d=json.load(open('$A/score_shots.json'));print(json.dumps({k:d[k] for k in d if k!='command'},indent=1)[:2000])"
```

**Expected output:** a JSON doc that contains, as named numeric fields, each of:
period-1 F1, period-2 (held-out) F1, the chosen budget K, the chance control's mean
F1 over ≥200 trials, and the `oop_proxy` control's F1. Any doc missing one of those
five fields fails acceptance regardless of what the numbers say.

### Report

Return JSON only:
```json
{"package":"P1-shots","status":"complete|partial|blocked",
 "gate":{"S1_f1_p2":0.0,"S2_ratio_to_chance":0.0,"S3_beats_oop_proxy":true,"verdict":"PASS|FAIL"},
 "files_changed":["..."],"acceptance_command":"...","acceptance_output":"<real, pasted>",
 "deviations":["..."],"not_done":["..."]}
```
