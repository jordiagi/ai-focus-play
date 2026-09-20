# STATE — live progress tracker

**Purpose:** survive interruption. If you are resuming (any agent, any harness), read
this file first, then `PLAN.md`. Update the status table as you go — a stale status here
is worse than none.

**Last updated:** 2026-09-19 · by Claude Opus 5 · G2: PnLCalib fails end-to-end (88-110 m); pivoting to mosaic stitching

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

## Blockers

| Blocker | Impact | Who clears it |
| :-- | :-- | :-- |
| **Tailscale SSH to gpu-box expired** | All Track 1 (GPU) work blocked. `scripts/remote/doctor.sh` will fail with a timeout | **User** — visit the re-auth URL Tailscale prints |
| Veo Bearer token is ephemeral (~minutes) | Only matters if ground truth needs re-capturing; it does not right now | Re-run the capture procedure in `PLAN.md` |

Track 2 (frontend/UI) is **not** blocked by either.

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

Legend: ☐ not started · ◐ in progress · ☑ done & verified · ⊘ blocked · ✗ abandoned

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
| G2 | Pitch calibration | ◐ | **PnLCalib pretrained FAILS end-to-end** (4.5% of event frames well-aligned; median error 88-110 m). All pretrained models are broadcast-trained. **Next: stitch a pitch mosaic and calibrate that**, since single crops show too little pitch |
| G3 | Tier A detectors (7 types) | ☐ | |
| G4 | Possession HMM → Tier B (4 types + Pass count) | ☐ | Conditional on G1 gate |
| G5 | Scoring harness (macro-F1, chance baseline, parity count, period split) | ☑ | Built and validated on 4 cases: refuses without manifest; empty→honest zeros; perfect→1.0; **random detector scores BELOW its chance baseline** |
| G6 | Ingest artifacts → `analysis_mode="ml"` | ☐ | `ml_ingest.py` does not exist yet |
| G7 | Jersey recognition | ☐ | Last. **No roster available**, so open-set with abstention, or Veo-label leakage that must be declared. Honest ceiling ~25-40% vs Veo's 75% |

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
