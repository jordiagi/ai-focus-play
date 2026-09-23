## Package: P2 — FootballFreeKick / FootballFoul detector

Owner:        codex / gpt-5.6-sol
Files OWNED:  `backend/src/services/pipeline/gpu_job/mosaic/detect_setpieces.py` (NEW — create it; it must not exist before you start)
Files READ:   `specs/complete-veo-parity/spec.md` (§3.1, §3.3 bind you), `backend/src/services/pipeline/gpu_job/mosaic/detect_restarts.py`, `detect_out_of_play.py`, `detect_goals.py`, `merge_predictions.py`, `scripts/local/score-benchmark.py`, `benchmarks/raw/veo_events_447.csv`, `benchmarks/veo_reference.json`, every artifact under `backend/.local/artifacts/mosaic/`
Out of scope: **every other file in the repo**, and in particular `detect_shots.py`, which another package owns and is being written at the same time. Do not edit `STATE.md`, `PLAN.md`, the spec, any existing detector, `merge_predictions.py`, or the scoring harness.

### The job

Test the one Tier-C design that `PLAN.md` proposed and nobody ran:
`FootballFreeKick` (15 events) and `FootballFoul` (15 events).

### Why this is not a retread

`STATE.md` item **B9** declares FreeKick "not attempted" because *its position cloud
sits inside ThrowIn's with no separating cue*. That rejects **position** as the cue.
`PLAN.md`'s Tier C never proposed position. It proposed:

> a stoppage with the ball **inside** the pitch, then a stationary restart

which is the exact **complement** of the working `OutOfPlay` detector — that one fires
where the ball *leaves* the region. This is a different discriminator and it has not
been measured. Your job is to measure it, not to make it succeed.

### What you may rely on (already measured, do not re-derive)

Identical to the shot package — read `specs/complete-veo-parity/wp-1.md` §"What you
may rely on" for the artifact schemas (`ball_track.json`, `ball5_pano.json`,
`pitch_frame.json`, the `(xi, eta)` snippet, the period bounds). In addition:

- `pred_oop.json` / `detect_out_of_play.py` — the stoppage signature you are taking
  the complement of. Read how it scores the coverage collapse; **reuse that feature,
  do not reinvent it.**
- `pitch_polygon.json` / `play_region.json` — the derived pitch region. Note the
  honest caveat already on record: only 8 % of its boundary lands on a detected line
  (2.35× chance). It is coarse. That coarseness is a real risk to this package and
  you should say so in the output doc if it bites.
- Benchmark tolerance is **3.0 s** for both types. Read it from
  `benchmarks/veo_reference.json`; do not hardcode it and do not change it.

### The two types are timestamped differently — score them separately

Veo stamps the **foul** at the offence and the **free kick** at the restart. They are
not the same instant, so do not emit one prediction for both. Emit each type
separately and score each separately.

### Hard protocol rules — identical to P1

1. Fit on period 1 only (5 fouls, 5 free kicks there — low n; say so). Touch period 2
   exactly once with the configuration frozen.
2. Apply the prediction budget (B14) exactly as `detect_restarts.py` does.
3. Compute and write all three controls: `chance` (≥200 trials), `oop_proxy`
   (relabel `pred_oop.json` as the type — the control that matters), and both
   periods stated separately.
4. Emit no team.
5. Record `"command": " ".join(sys.argv)` in the `--out` doc.
6. Veo's `x`/`z` may inform a period-1 threshold; they may never place a prediction.

### The gate, pre-registered

`FootballFreeKick` PASSES iff, on period 2 held out: F1 ≥ 0.20 **and** ≥ 2.0 × the
chance control **and** strictly greater than the `oop_proxy` control.

`FootballFoul` is **not gated** — `PLAN.md` records that its onset timing is
unrecoverable because we lost the whistle. Publish its number whatever it is, and do
not tune toward it.

With n = 5 in period 1, a threshold fitted to a handful of events will look better
than it is. Report the period-1 number *and* say plainly that it is fitted on 5
events. Do not let a good period-1 figure become the headline.

### Deliverables

- `detect_setpieces.py`, CLI mirroring `detect_restarts.py` plus `--oop-pred`.
- `backend/.local/artifacts/mosaic/pred_setpieces.json`
- `backend/.local/artifacts/mosaic/manifest_setpieces.json` — `attempted` must list
  exactly the types you actually emit, and `not_attempted` must carry a reason for
  any you decided against **before** scoring, not after.
- `backend/.local/artifacts/mosaic/score_setpieces.json`

### Contract

A measured FAIL reported honestly is a **complete** package. `PLAN.md` already calls
this tier "marginal"; a negative result here is the expected outcome and is worth
exactly as much as a positive one, because it closes the last open question in the
detection axis.

### Acceptance — run it and paste the real output

```sh
cd /home/ai/workspaces/users/jordi/ai-focus-play
V=backend/.venv/bin/python; A=backend/.local/artifacts/mosaic
$V backend/src/services/pipeline/gpu_job/mosaic/detect_setpieces.py \
   --track $A/ball_track.json --candidates $A/ball5_pano.json \
   --frame $A/pitch_frame.json --oop-pred $A/pred_oop.json \
   --polygon $A/pitch_polygon.json \
   --pred $A/pred_setpieces.json --manifest $A/manifest_setpieces.json \
   --out $A/score_setpieces.json
$V -c "import json;d=json.load(open('$A/score_setpieces.json'));print(json.dumps({k:d[k] for k in d if k!='command'},indent=1)[:2500])"
```

**Expected output:** a JSON doc carrying, as named numeric fields, for **each** of
`FootballFreeKick` and `FootballFoul`: period-1 F1, period-2 held-out F1, n_pred, the
chosen budget K, the chance control mean F1 over ≥200 trials, and the `oop_proxy`
control F1. A doc missing any of those for either type fails acceptance regardless of
the numbers.

### Report

Return JSON only:
```json
{"package":"P2-setpieces","status":"complete|partial|blocked",
 "gate":{"freekick_f1_p2":0.0,"ratio_to_chance":0.0,"beats_oop_proxy":true,
         "verdict":"PASS|FAIL","foul_f1_p2_ungated":0.0},
 "files_changed":["..."],"acceptance_command":"...","acceptance_output":"<real, pasted>",
 "deviations":["..."],"not_done":["..."]}
```
