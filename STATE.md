# STATE — live progress tracker

**Purpose:** survive interruption. If you are resuming (any agent, any harness), read
this file first, then `PLAN.md`. Update the status table as you go — a stale status here
is worse than none.

**Last updated:** 2026-09-20 · by Claude Opus 5 · **D-0 falsified; D-A panorama built but
NO METRES; switched to D-B — player occupancy gives a coarse pitch region, not a sharp
boundary.** Tailscale re-authed, gpu-box in use

---

## Resume in 60 seconds

1. `PLAN.md` — the roadmap and the reasoning. `context.md` — environment + traps.
   `OPUS2.md` — the 9 defects already closed and how they were verified.
   Current probe baseline: **`pass=9 fail=0 skip=0`**, 35 tests.
2. **Ground truth is now on disk** at `benchmarks/raw/` (see below). It does **not**
   need re-capturing unless the match changes.
3. Check blockers below before touching gpu-box.
4. `bash scripts/local/verify.sh all` should print `pass=9 fail=0 skip=0`. If it
   doesn't, something regressed — fix that before new work.

---

## Status: consolidated 2026-09-20

Work is **stopped at a deliberate stopping point**, not abandoned mid-flight. Everything
below is committed, verified and reproducible. Metric pitch calibration was attempted
three times, failed each time for a diagnosed structural reason, and is parked as **D-A**
in `specs/deferred.md` along with the pragmatic alternative **D-B** (pixel-space Tier A
detection, which needs no metres). Pick either up when the feature is wanted.

**D-0 was then tried and falsified** (2026-09-20, below). Four approaches to recovering
pitch geometry have now been measured and rejected; the fifth, D-A, is the only one left
that attacks the root cause, and D-0 sharpened its design.

---

## Recommended next step

**Sharpen the D-B pitch boundary, then build the first Tier A detector.**

D-B is started. Player occupancy in panorama pixel space now gives a *derived* pitch
region (no annotation, no metres) holding 86 % of players, but its boundary beats chance
by only **2.35x** and just 8 % of it lands on a detected line. That is enough for the
coarse zone uses and **not** enough for "ball crosses a boundary", which is what
corner / throw-in / goal kick need. The obvious next move is to fit a smooth
quadrilateral to the occupancy instead of trusting a ragged density contour.

After that, the first scored detector needs the **ball in panorama space**: `frame →
panorama` is solved and `detect_players.py` shows the remote detection loop costs
seconds, so the missing piece is tiled ball detection (G1 measured 0.83 candidate
presence tiled vs 0.68-0.72 full-frame) plus trajectory association.

**Metric calibration stays parked.** Five approaches measured, none validated — and D-B
step 3 added an independent reason to leave it: inverting the player cloud onto the
fitted plane yields a **square** pitch (105.8 x 104.5 m, aspect 1.01) because near the
horizon a few pixels is tens of metres.

---

## D-B result (2026-09-20) — zones derived, but coarse

| step | state |
| :-- | :-- |
| 1. player detection (gpu-box) | ☑ 600 in-play frames, **15,380 persons**, 16.5 s on one H100 |
| 2. occupancy in panorama space | ☑ **95.7 % registered**, 14,607 foot points, 92 % in one blob |
| 3. pitch region polygon | ◐ **derived and tested — 2.35x chance, not a sharp boundary** |
| 4. ball in panorama space | ☐ not started |
| 5. Tier A detectors + scoring | ☐ not started |

**The premise is now measured, not assumed.** Inverting the same 14,607 points onto the
fitted ground plane gives an oriented box of **105.8 x 104.5 m, aspect 1.01** — a square,
where a pitch is ~1.5 — with a 124 m depth spread. Metres are not merely unnecessary
here, they are unusable; pixel space is fine.

**The zone test, run because containing the players is not the same as being the pitch:**

| density pct | area frac | players inside | boundary on a line | chance | lift |
| --: | --: | --: | --: | --: | --: |
| 70 | 0.159 | 0.922 | 0.034 | 0.033 | 1.03 |
| **80** | 0.109 | 0.864 | **0.083** | 0.036 | **2.35** |

Usable as a soft "on the playing surface" test; **not** a touchline. Of D-B's three zone
uses it serves the coarse one (Goal) and not the sharp one (corner / throw-in / goal
kick).

---

---

## D-A result (2026-09-20) — panorama YES, calibration NO

| step | state |
| :-- | :-- |
| 0. is a consistent mosaic possible? | ☑ 3-frame loop closure **0.97 px**, flat in span |
| 1. stitch the panorama | ☑ **4414x1190, 125.4° FOV**, players dissolved |
| 2. line evidence map | ☑ centre circle, halfway, touchlines, penalty areas |
| 3a. which field is ours | ☑ **213/220 event frames located (96.8 %)** |
| 3b. fit the pitch pose | ✗ **pose converges, outline does not** — no metres |

**The pose now agrees across independent methods:**

| quantity | value | agreeing sources |
| :-- | :-- | :-- |
| camera height | **6.71 m** | centre circle (known 9.15 m radius) |
| ground normal | **0.87° off vertical** | centre circle; matches wave correction |
| in-plane rotation γ | **168.6-171.1°** | three routes within 2.5° |
| pitch width W | **68.5-69.8 m** | touchline offset, line-evidence scan |
| centre circle fit | **0.0 px median, 68 % within 3 px** | event cloud confirms it is ours |

**But the outline does not fit:** touchlines 24-39 px out, goal lines 31-51 px, halfway
24 px (<=3 px fractions 0-14 %), while the circle stays at 0.0 px. L stays unstable
(101-120 m, often on a bound).

**Two measurements that removed whole hypotheses:**

- **Not panorama distortion.** Line half-width in the accumulated map grows only
  **1.17x** centre to edge (1.96 → 2.30 px); the panorama registers to a few px
  throughout.
- **Frame centre tracks the ball in azimuth only.** The event cloud is a narrow
  elevation band barely taller than the centre circle — the virtual camera pans and
  zooms but hardly tilts. corr(veo_x, azimuth) = **+0.904** and monotone across all ten
  deciles; corr(veo_z, azimuth) = +0.08. Azimuth-only fit residual **4.9°** against a
  39.9° baseline.
- **Which field is ours is now settled.** The bright foreground curves along the bottom
  of the panorama — which every line fit had been chasing — fall *outside* the play
  region. They belong to a nearer field.

Three degeneracies were found by unit-testing against synthetic ground truth rather
than by reading output: `pitch_model` scaled the penalty areas with the pitch (which is
the only thing breaking the similarity degeneracy); the objective was piecewise
constant, so Nelder-Mead descended a staircase; and letting camera height float has a
**trivial global optimum at h = 0** where all rays collapse to the camera centre — both
scipy optimisers drove straight to it.

---

---

## D-A result (2026-09-20) — panorama YES, calibration NO

| step | state |
| :-- | :-- |
| 0. is a consistent mosaic possible? | ☑ 3-frame loop closure **0.97 px** median, flat in span |
| 1. stitch the panorama | ☑ **4414x1190, 125.4° FOV**, whole pitch, players dissolved |
| 2. line evidence map | ☑ centre circle, halfway, both touchlines, both penalty areas |
| 3. fit the pitch pose | ✗ **pose plausible, pitch does not fit** — no metres |

**The line map was the first big gain.** The RGB median composite is what removes the
players, but it also averages away a 1-2 px line. Detecting lines per frame — where they
are sharp — and compositing the *response* took alignment from 0.096 to 0.26 and median
error from 118 px to 15 px.

**The centre-circle anchor was the second.** A circle of known radius (9.15 m) seen by a
calibrated camera determines the plane, so it pins normal, height and centre at once:

| | 8-D search | centre-circle anchor |
| :-- | :-- | :-- |
| camera height | 1-2 m, **on the bound** | **6.71 m** — plausible for a pole |
| ground normal | unconstrained | **0.87° off vertical** — matches wave correction |
| parameters on bounds | several, every run | **none** |
| pitch size | on bounds | **104.3 x 69.6 m**, read off the line offsets |
| centre circle fit | — | **median 0.0 px, 68 % within 3 px** |

**But no standard pitch aligns with the rest.** An exhaustive 0.5° rotation scan over a
grid of L and W, pose held fixed, never gets the outline above ~25 % within 3 px
(touchlines 16-42 px, goal lines 17-36 px, halfway 17-31 px) while the circle stays at
0.0 px.

**It is not panorama distortion** — the obvious suspect, so it was measured: line
half-width grows only **1.17x** from centre to edge (1.96 → 2.30 px). The panorama
registers to a few pixels throughout.

**It looks like the multi-pitch complex.** Only **one** touchline-parallel line sits at a
pitch-like distance from the fitted circle (-34.9 m, found nine times); a real pitch
centre would have two, symmetric at ±W/2.

Two degeneracies were found and fixed by unit-testing against synthetic ground truth,
not by reading output: letting `h` float has a **trivial global optimum at h=0** (all
rays collapse to the camera centre; both scipy optimisers drove straight to it), and the
parameters span 0.05-200 in magnitude so the solve needs an explicit `x_scale`.

---

---

## D-0 result (2026-09-20) — FALSIFIED, in ~30 min of CPU

The falsification test `specs/deferred.md` demanded was run exactly as pre-registered.
Scripts: `backend/src/services/pipeline/gpu_job/camera/` (README there is the full
record). All CPU, on the local 720p proxy — **not blocked by the Tailscale outage**.

| criterion | result | |
| :-- | --: | :-- |
| C1 ROC AUC of camera speed >= 0.80 | 0.613 | fail |
| C2 median in-play speed >= 2x halftime | 1.70 | fail |
| C3 both boundaries within +/-30 s | 0.7 s / 2825 s | fail |

**The premise was wrong.** "Out of play → camera goes static" is false here: Veo's
virtual camera keeps roaming through halftime at ~10 px/s, following warm-up activity on
an empty pitch. A kickoff detector built on the surviving step signature scored **0/8**.

**Three things worth keeping:**

1. **Dense registration works.** 12,343 pairs at 2 fps over the full match, median
   **612 inliers, 99.6 % above the gate**, 11 min of CPU. Registration is not the weak link.
2. **Kickoffs are a free ground truth for a repeated view.** All 8 are centre-circle
   restarts; registering those frames directly against each other gives a median offset
   of **58 px** (max 122). No calibration, no annotation needed. D-0's positional claim
   was right.
3. **Chaining drifts 10.6x.** Integrating per-pair `dx` reports **616 px** median
   (max 1490) between those same 58 px-apart frames — a third of the full 4578 px pan
   range. Over a 30-minute window the chained trajectory looks bounded and fine; only the
   full match exposes it. **Do not validate registration on a short window.**

Caution for whoever picks this up: *sweep* (how far the camera ranged over the last W s)
reaches AUC 0.80 at W=60 s and 0.91 at W=240 s, but that was selected post-hoc on the
same window and the gain is just W fitting inside the 795 s halftime. It buys nothing at
the few-second scale of the 64 `FootballOutOfPlay` events. Not a result.

---

## Blockers

| Blocker | Impact | Who clears it |
| :-- | :-- | :-- |
| ~~Tailscale SSH to gpu-box expired~~ | **CLEARED 2026-09-20.** `doctor.sh` exits 0: 4x H100, 63.9 GB min free, tmpfs mounted, torch 2.11.0+cu128, video sha256 `ef7552326b0ab24e` | done |
| Veo Bearer token is ephemeral (~minutes) | Only matters if ground truth needs re-capturing; it does not right now | Re-run the capture procedure in `PLAN.md` |

Track 2 (frontend/UI) is **not** blocked by either. All D-0 and D-A work so far is CPU-only
on the local 720p proxy and needed neither.

---

## Ground truth captured (2026-09-19)

Pulled from Veo's own API in an authenticated browser session. **This replaces the old
13-event benchmark, whose second-half timestamps were wrong by up to 752 s.**

| File | Contents |
| :-- | :-- |
| `benchmarks/raw/veo_events_447.csv` | **447 events** — `video_time_ms, period_id, period_time_ms, event_type, team, player_jersey, outcome, x, z`. 14 types. 334 carry a jersey, 355 carry pitch coords |
| `benchmarks/raw/veo_highlights_31.csv` | 31 AI highlight clips (goal / shot_on_goal), clip-start seconds |

Verified on disk: type histogram matches the API exactly; 6 goals in both files.

**Time base (measured, exact, linear):** period 1 `video = period_time + 562`;
period 2 `video = period_time + 3674`. Kickoff 562.3; H1 ends 2879.3; halftime 795 s;
H2 starts 3674.4; last event 6132.1. Halves are 2317.0 s and 2457.7 s — **not 2400**.

**Do not re-derive these from match-clock strings.** That is exactly how the old
benchmark went wrong.

---

## Work package status

Legend: ☐ not started · ◐ in progress · ☑ done & verified · ⊘ blocked · ⏸ deferred by decision · ✗ abandoned

### Cross-cutting (do first, cheap, no GPU)

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| X1 | Delete surviving `pass_strings` fabrication and `or 20.0` thirds fallbacks | ☑ | `c38d62f` |
| X2 | Add probe `d10` — no invented analytics literal anywhere | ☑ | **Negative-tested**: FAILS on pre-fix code, PASSES after |
| X3 | `PitchRadar` must draw nothing for an undetected ball | ☑ | Now renders "Ball not detected" instead |

### Track 1 — GPU pipeline (⊘ blocked on Tailscale re-auth)

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| G0 | Rebuild `benchmarks/veo_reference.json`; fix `scripts/config.env` time base; decode Veo's x/z convention | ☑ | `c38d62f`. Coords decoded: x=length, z=width, absolute. Centre spot lands 2 m off ideal — Veo's own bias, recorded not corrected |
| G1 | **Measure ball-detection rate** — the go/no-go gate | ☑ | **Both halves measured.** tiled 0.833 / 0.828 — **gate passes**. full-frame 0.677 / 0.716 — fails one half. Caveat below: this is candidate presence, not correctness |
| G2 | Pitch calibration | ⏸ **STOPPED** | Three approaches measured and failed (1854 m → 10-15 m → 88-110 m). Cause is structural, not tuning: all pretrained models are broadcast-trained and each of our frames shows too little pitch. Parked as **D-A** in `specs/deferred.md` |
| G3 | Tier A detectors (7 types) | ⏸ | |
| G4 | Possession HMM → Tier B (4 types + Pass count) | ⏸ | Conditional on G1 gate |
| G5 | Scoring harness (macro-F1, chance baseline, parity count, period split) | ☑ | Built and validated on 4 cases: refuses without manifest; empty→honest zeros; perfect→1.0; **random detector scores BELOW its chance baseline** |
| G6 | Ingest artifacts → `analysis_mode="ml"` | ⏸ | `ml_ingest.py` does not exist yet |
| D-A | Panorama + line map (frame → panorama) | ◐ | **BUILT** 2026-09-20: panorama 4414x1190 125.4° FOV; line map shows centre circle, halfway, both touchlines, both penalty areas. Loop closure 0.97 px |
| D-A3 | Ray-space pitch pose fit | ✗ | **Pose converges across 3 independent methods** (h=6.71 m, normal 0.87° off vertical, γ within 2.5°, W 68.5-69.8 m; circle fits 0.0 px / 68%). **But the outline does not** (24-51 px). **No metres.** Recommend D-B instead |
| D-A4 | Play region from Veo events | ☑ | 213/220 event frames located (96.8%). Settles which field is ours; foreground lines are a different pitch. Frame centre tracks the ball in **azimuth only** |
| D-0 | Camera motion as the event signal | ✗ | **Falsified 2026-09-20.** Premise "stoppage = static camera" is false; kickoff detector 0/8. Yielded the 10.6x chaining-drift constraint on D-A |
| G7 | Jersey recognition | ⏸ | Last. **No roster available**, so open-set with abstention, or Veo-label leakage that must be declared. Honest ceiling ~25-40% vs Veo's 75% |

### Track 3 — D-B, pitch-relative detection without metres

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| B1 | Player detection on gpu-box | ☑ | 600 in-play frames, 15,380 persons, 16.5 s on one H100. `detect_players.py` |
| B2 | Occupancy map in panorama space | ☑ | 95.7% registered, 14,607 foot points, 92% in one blob |
| B3 | Pitch region polygon, derived + tested | ◐ | 86% of players inside, boundary **2.35x chance** (8% on-line). Coarse, not a touchline |
| B4 | Ball in panorama space | ☐ | Needs tiled detection (G1: 0.83 tiled vs 0.68-0.72 full-frame) + trajectory association |
| B5 | Tier A detectors + benchmark scoring | ☐ | The actual deliverable; harness already exists |

### Track 2 — UI / route parity — ☑ **COMPLETE**

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| U1 | Hash router; wire the 6 drawers to Veo's routes; real deep-link Share | ☑ | **codex**, merged `35a0659`. Verified behaviourally: loading `/#/events/` directly opens the panel |
| U2 | Jersey numbers only, never invented names; jersey bar from `lineup` | ☑ | **agy/gemini-3.8-flash-high**, merged `c9054d9`. 36 tests, 0 invented names, follows Veo's blank-number convention |
| U3 | Events drawer 15-type status surface **+ singular stat labels** | ☑ | **codex** (re-dispatch after claude hit a 429 quota limit). All 15 types declared; model validator refuses `detected` without a count or `unavailable` without a reason |

---

## G1 result so far (the gate the roadmap hangs on)

Slice 1200-1800 s of period 1, 3000 frames at 5 fps, `yolo11x`, conf 0.05, COCO
`sports ball`, tiles 3x2 with 0.15 overlap above y=0.22h.

Two slices, one per half, 3000 frames each, so the figure is not a cherry-picked window.

| config | period 1 (1200-1800s) | period 2 (4200-4800s) |
| :-- | --: | --: |
| full frame @1280 | **0.677 — fails** (median gap 0.2s) | 0.716 (median gap **0.4s**, at the limit) |
| **tiled @640** | **0.833 — passes** (0.2s) | **0.828 — passes** (0.2s) |

Tiled is stable at ~0.83 across both halves. Full-frame straddles the gate and fails on
one of them, so it is not merely worse, it is unreliable.

The full-frame configuration is effectively what the Colab notebook used, and it
**misses the gate**. Tiling is what clears it — which is the single most useful thing
this measurement has established.

**Caveat that must travel with this number.** `detection_rate` means a COCO
`sports ball` candidate was present at conf>0.05 *somewhere in the frame*. It does
**not** verify the candidate is the ball — a head or a line marking can fire. This is
candidate presence, not correctness. Do not quote it as tracking accuracy. Trajectory
association plus validation against known ball positions is a separate step, and the
honest per-trajectory number will be lower.

---

## G2 registration — feasibility proven, calibration NOT yet working

### Feasibility: yes, with a measured confidence gate

46 frames across 600-6100 s, SIFT + RANSAC. Median 3231 keypoints per frame, so
features are not the problem. **Inliers do not decay with time separation** — the
constraint is *view overlap*, not drift, because the virtual camera pans across the
pitch and distant views share no content. Anchor placement is set-cover over the pan
range, not over time.

**The confidence gate is measured, not guessed.** Round-trip test (`H_AB · H_BA`
should be identity):

| inliers | round-trip error |
| --: | :-- |
| 678, 271, 181, 126, 74 | **0.31–3.93 px** — excellent |
| 33, 33 | **36–52 px** — garbage |

Registration is bimodal. Use **min_inliers >= 100**. Anchors needed for full coverage
at that gate: **4** (at 50 or 70 it is 3). An earlier "4 anchors → 100%" figure was
computed at min_inliers=30 and was therefore meaningless; re-measured, the conclusion
happens to survive.

### Calibration: TWO attempts failed. Do not retry the same way.

| | attempt 1 (71 restarts, gate 30) | attempt 2 (355 events, gate 100) |
| :-- | :-- | :-- |
| correspondences | 46 | 217 |
| max error | 1854 m — degenerate | 50-81 m — stable |
| median error | 3.3-8.2 m | **10-15 m (worse)** |
| RANSAC inlier fraction | — | **only ~40%** |

The strict gate fixed the degenerate blowups. It did not fix accuracy, and the ~40%
inlier fraction is the tell: **most correspondences do not agree with any single
homography, so the correspondences themselves are bad.** For an interception or tackle
Veo's coordinate marks where the *action* was, not where a detected ball is, and
"best ball candidate anywhere in frame" is unverified — a head or a shoe also fires.

**Conclusion: ball-position correspondences cannot calibrate this. Stop trying.**

### What the footage actually looks like (viewed, not assumed)

This is a **multi-pitch complex**. A single frame contains our match pitch plus **four
or more goals belonging to adjacent fields**, tents, parked cars, a building, crowd,
and a second blue line system crossing diagonally. Two consequences:

- **The camera is low and very oblique.** Our pitch recedes sharply and the far half
  compresses into a thin band, so a few pixels of error there is many metres. That is
  a physical limit, and it is consistent with the 10-15 m median we measured.
- **Most SIFT features are off the pitch plane** — trees, tents, crowd, other pitches.
  A homography fitted through them does not describe the pitch plane, which is the
  plane we actually need.

The anchor at t=960 s is much more promising than the midfield one: it shows a penalty
area with genuinely identifiable landmarks (penalty box corners, six-yard box, goal
posts, penalty arc) and the white match lines are separable from the blue ones.

### The right method: learned pitch-keypoint calibration (researched 2026-09-19)

My two failures shared one root cause: **I used generic SIFT features.** On this footage
those land on trees, tents, parked cars and adjacent pitches — all *off the pitch plane*,
which is the one plane we need. The established solution does not use generic features at
all.

This is a solved research problem with an annual benchmark — the **SoccerNet Camera
Calibration challenge**. The pitch is a planar target of known dimensions, so a homography
follows from four lines. 2025-era pipelines (NBJW, **PnLCalib**, Broadtrack) all do
*learned landmark/line detection* then solve for the camera. Semantics is exactly what
fixes our multi-pitch problem: a model trained on pitch classes knows a halfway line from
a stray blue line on an adjacent field.

**PnLCalib is installed and running on the box** (`/opt/PnLCalib`, weights `SV_kp` /
`SV_lines`, GPL-2.0 — fine locally, relevant only if this is ever distributed).

Measured across 46 frames. **Coverage is not accuracy**, so each calibration was scored
by projecting the known 105x68 pitch model back into the image and measuring how much of
it lands on real white-line pixels (bright + desaturated; the other field's lines are
blue and saturated, so they are excluded by construction). This test needs no ball
detection and no Veo coordinates, so it cannot be fooled by the noise that broke the
SIFT attempts.

| thresholds | calibrated | median alignment | well-aligned (>=0.50) |
| :-- | --: | --: | --: |
| 0.3434 / 0.7867 (default) | 12/46 | 0.26 | 4 (9%) |
| **0.15 / 0.30 (best)** | 27/46 | **0.29** | **12 (26%)** |
| 0.10 / 0.20 | 39/46 (85%) | 0.19 | 11 (24%) |

Dropping the threshold to 0.10 lifts "success" to 85% while **degrading** alignment and
producing no more well-aligned frames — the same failure shape as `min_inliers=30`. That
85% is mostly confidently-wrong calibration. **Use 0.15 / 0.30.**

Caveats that may understate true accuracy: the pitch model is fixed at 105x68 and a U16
field is likely ~100x64, so part of the misalignment could be model mismatch rather than
camera error; and faint or worn lines may fall outside the white mask.

### End-to-end metric test: PnLCalib pretrained FAILS on this footage

The decisive measurement — metres, not proxy scores. For each of 355 Veo events:
calibrate the frame, keep it only if independently well-aligned, detect the ball, invert
onto the ground plane, compare against Veo's own (x,z).

| stage | count |
| :-- | --: |
| event frames tried | 355 |
| calibrated | 253 |
| **independently well-aligned (>=0.5)** | **16 (4.5%)** |
| scored | 10 |

**Median error 88 m (restarts) / 110 m (open play)** on a 105 m pitch. Essentially
random. Note the well-aligned rate collapsed from 26% on wide frames to 4.5% on *event*
frames, which are action close-ups showing little pitch structure.

**Conclusion: PnLCalib's pretrained weights do not transfer here.** Fair test, fair
failure. The Roboflow `football-field-detection` model shares the problem — it was
trained on 317 frames from TV matches.

### Why, and what it implies

Every available pretrained pitch-calibration model is trained on **broadcast TV**
footage. Ours is amateur, low, extremely oblique, set in a multi-pitch complex, and is
itself a *virtual pan-and-zoom crop* with heavy zoom variation.

And the framing of the whole problem was wrong. **Veo is not solving our problem.** Veo
calibrates its own camera rig against the *full panorama* — known intrinsics, known
mounting, whole pitch in view. We are trying to calibrate from a ball-following crop of
that panorama, which discards exactly the context that makes calibration tractable. "Veo
can do it from an upload" is true, but Veo holds the raw camera feed and we hold a
derived crop.

### Next: rebuild the panorama by stitching, then calibrate THAT

The individual frames fail because each shows too little pitch. But registration between
frames is already proven (0.31-3.93 px above 100 inliers). So:

1. **Stitch frames into a pitch mosaic** — recovering, approximately, the panorama Veo
   will not export.
2. **Calibrate the mosaic once.** It shows the whole pitch, which is far closer to the
   broadcast-style input the pretrained models expect.
3. **Propagate**: every frame inherits metric coordinates through
   `frame → mosaic (registration) → pitch (one homography)`.

This attacks the root cause rather than the symptom, and both ingredients are measured
rather than assumed.

### The reframe — still useful as a fallback



**Most Tier A detection does not need metres — it needs pitch-relative regions.**

- Shot: ball speed and direction toward the goal mouth. Definable in **anchor pixel
  space** if the goal mouth is marked there. No metric needed.
- Corner / throw-in / goal kick: ball crossing a boundary. Boundaries can be drawn as
  polygons in anchor pixel space.
- Goal: the restart signature (ball near the centre spot, players split by half). Needs
  only coarse position.

Precise metric coordinates are genuinely required for only two things: the radar
display and speed in m/s. So a sensible next step is **annotate the pitch polygon and
key zones directly in each anchor's pixel space**, ship Tier A detection on that, and
treat accurate metric calibration as a separate, later problem for the radar. That
inverts the current dependency, where everything waits on a homography that has now
failed twice.

---

## Incident log (read before touching worktrees)

**2026-09-19 — the worktree symlink that ate the venv.** I created `.venv`/`.local`
symlinks inside each UI worktree so agents could run acceptance commands. `.gitignore`
had `backend/.venv/` and `backend/.local/` **with a trailing slash**, which matches a
*directory* but **not a symlink**, so `git add -A` in a worktree tracked them and merging
replaced the real directories with self-referential links.

Lost and rebuilt: the venv (now **Python 3.14.7**, not the previous 3.12.14 — all pinned
deps install and import fine), the seeded DB, the demo fixtures, and the 916 MB 720p
proxy. Nothing was unrecoverable: everything in `.local` was either seed data or derived
from the source mp4, which is intact in `~/Downloads` and on gpu-box.

Two things worth keeping:
- The ignore patterns are now **slash-free**, so a symlink is caught. Verified with
  `git check-ignore`.
- After the rebuild the CV determinism signature was **identical** (`61075316940f2cb1`)
  across a Python 3.12 → 3.14 change, and the regenerated demo clips were byte-identical
  in size. That is real evidence the pipeline is deterministic, obtained by accident.

---

## Done already (do not redo)

- 9 defects closed and verified — `verify.sh all` → `pass=9 fail=0 skip=0`, 35 tests.
  Full record in `OPUS2.md`.
- gpu-box provisioned: torch 2.11.0+cu128, CUDA 12.8, 4× H100, uv-managed CPython 3.12.
  `scripts/remote/provision.sh` is idempotent (re-run → `cached`, exit 10).
- Match video uploaded to `/workspace/aifp/media/video.mp4`, **sha256 verified**
  (`ef7552326b0ab24e...`), 185,003 frames, decodes on the box.
- `scripts/` built: doctor, provision, push-video (resumable), push-code, job-status,
  pull-artifacts, restore, verify, plus the agent dispatch wrapper.
- Veo ground truth captured (above).
- `scripts/local/score-benchmark.py` (G5) — validated on four cases including a random
  detector scoring BELOW its own chance baseline.
- **Track 2 complete**: U1 (hash routing), U2 (jersey-only identity), U3 (15-type status
  surface) all merged and independently verified. Baseline **`pass=9 fail=0 skip=0`, 36 tests**.
- 720p proxy rebuilt and verified (1280x720, duration 6172.933433 exact).

---

## Decisions already made (don't relitigate)

- **Both tracks in parallel**; UI is file-disjoint from GPU work.
- **Done bar:** everything honestly reachable; explicitly excluding what we cannot do.
- **Jersey recognition: yes**, but sequenced last.
- `/workspace` is a 64 GB tmpfs — ephemeral by design; `restore.sh` rebuilds it.
- `cv_engine.py` is **frozen** as the `demo` fallback. Do not extend it.

---

## Answered by the user (2026-09-19) — both close off an easier path

- **No panorama export.** Veo does not allow exporting or downloading the full panoramic
  / interactive view. So the ball-following crop is all we get and **per-frame homography
  (G2) is mandatory** — the mosaic-registration design is now the plan, not one option of
  two. Budget accordingly; this is the most expensive layer.
- **No roster / team sheet available from Veo.** So jersey recognition cannot be framed
  as a closed-set classification over a declared squad. That leaves two honest options,
  and the choice must be stated in the output either way:
  1. **Open-set**: read digits with abstention, cluster per track, never assert a number
     below the confidence margin. Lower coverage, no leakage.
  2. **Derive the number set from Veo's 334 attributed events** — which is *leakage
     dressed as a prior* and must be labelled as such wherever the result is reported.
  Default to (1). Do not quietly do (2).
