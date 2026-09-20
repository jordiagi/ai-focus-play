# Deferred work

Parked deliberately, not forgotten and not failed-and-hidden. Each entry says what it
would buy, what is already proven, and what the real risk is — so a future session can
judge whether to pick it up without re-deriving any of it.

---

## D-0. FALSIFIED (2026-09-20) — camera motion is not the event signal

**Status:** tested and **rejected**. Kept here because how it failed constrains D-A.
Full record: `backend/src/services/pipeline/gpu_job/camera/README.md`.

**The test it was given.** The pre-registered kill-test in this entry was run exactly as
written: the recovered trajectory must show the 795 s halftime gap. It does not.

| criterion | result | |
| :-- | --: | :-- |
| C1 ROC AUC of camera speed >= 0.80 | 0.613 | fail |
| C2 median in-play speed >= 2x halftime | 1.70 | fail |
| C3 both boundaries recovered within +/-30 s | 0.7 s / 2825 s | fail |

**Why.** The premise "out of play → camera goes static" is **false on this footage**.
Veo's virtual camera keeps roaming during halftime at a median ~10 px/s, following
warm-up activity on an empty pitch, and play itself contains plenty of slow stretches.

A kickoff detector built on the surviving step signature scored **0/8 at +/-3 s**,
placing all 8 predictions in period 2 — the raw step score scales with camera speed and
the second half is simply faster.

**What was true.** Registration is not the weak link: 12,343 pairs at 2 fps over the full
match, **median 612 inliers, 99.6 % above the gate**, 11 min of CPU. And D-0's other
prediction — "kickoff = the camera returns to the same central view" — is **correct**.
All 8 kickoffs are centre-circle restarts, and registering those frames directly against
each other gives a median view offset of **58 px** (max 122). That is a free physical
ground truth for a repeated view, needing no calibration and no annotation.

**The finding that matters.** Integrating per-pair `dx` along the trajectory reports a
median offset of **616 px** (max 1490) between those same kickoff frames — a **10.6x
drift factor**, with the worst case a third of the camera's entire 4578 px pan range.
Chained frame-to-frame registration cannot deliver absolute camera position over match
timescales. Over a 30-minute window it looks bounded and fine; only the full match
exposes it. See **D-A**, which this makes stricter.

## D-A. Rebuild the pitch panorama by stitching, then calibrate that

**Status:** **step 2 of 3 done (2026-09-20).** The panorama is built; calibrating it is
not. Full record: `backend/src/services/pipeline/gpu_job/mosaic/README.md`.

| step | state |
| :-- | :-- |
| 0. is a consistent mosaic possible? | ☑ **yes** — 3-frame loop closure 0.97 px median, flat in loop span, 181/186 frames in one component |
| 1. stitch the panorama | ☑ **4414x1190, 125.4° FOV**, whole pitch, both goals, players dissolved by median compositing |
| 2a. line evidence map | ☑ centre circle, halfway line, both touchlines, both penalty areas — composited from the SHARP source frames, not the median panorama |
| 2b. fit the pitch pose | ✗ **attempted, does not converge — still no metric coordinates** |
| 3. propagate to every frame | ☐ blocked on 2b; `frame → panorama` itself is solved (per-frame R and focal) |

**Step 2b: the pose is now solved, the pitch is not.** Anchoring on the centre circle
removed every parameter degeneracy — camera height **6.71 m** (was pinned at a 1-2 m
bound), ground normal **0.87° off vertical** (matches wave correction), **nothing on
bounds**, pitch **104.3 x 69.6 m** read off the line offsets, and the circle itself fits
to **median 0.0 px, 68 % within 3 px**.

But an exhaustive 0.5° rotation scan over a grid of L and W, with that pose held fixed,
never gets the pitch outline above ~25 % within 3 px (touchlines 16-42 px, goal lines
17-36 px, halfway 17-31 px). **Still no metric coordinates.**

It is **not** panorama distortion — measured, not assumed: line half-width in the
accumulated map grows only **1.17x** from centre to edge (1.96 → 2.30 px). The evidence
points at the **multi-pitch complex**: only *one* touchline-parallel line sits at a
pitch-like distance from the fitted circle (-34.9 m, detected nine times), where a real
pitch centre would have two symmetric at ±W/2.

**Next: use Veo's own events to isolate our pitch.** Every one of the 447 events carries
a video timestamp, and `frame → panorama` is solved. The virtual camera follows the ball,
so projecting each event frame's centre into the panorama traces where play actually
happened; that point cloud outlines *our* pitch and the rest of the lines can be dropped
before fitting. No annotation, no ball detection, ground truth already on disk.

Verified correct and reusable: the spherical projection (matches OpenCV's warper to the
pixel), the closed-form ray-space line solution, and the pose-from-circle solver (both
recover synthetic ground truth exactly). Two traps found by unit-testing rather than by
reading output: letting camera height float has a **trivial global optimum at h = 0**
where all rays collapse to the camera centre and both scipy optimisers drive straight to
it; and the parameters span 0.05-200 in magnitude, so the solve needs an explicit
`x_scale` or it walks to the bounds from every start.

**Before starting step 2:** the pan spans **129.5°**, so **no single homography maps the
panorama to the pitch plane** — no pinhole image can contain this pitch, which is
precisely why Veo ships a panorama and calibrates with known intrinsics instead. Fit the
ground plane in *ray* space: every panorama pixel is a ray, the pitch is the plane those
rays strike, and the free parameters are the plane normal (2), in-plane rotation and 2D
offset (3), and scale (1). Score with the white-line alignment metric already built in
`../pitch/score_alignment.py`.

**Why it is needed.** Metric (metre-space) pitch coordinates are currently unavailable —
three approaches failed, documented in `STATE.md`. The cause is structural: every
pretrained pitch-calibration model is trained on **broadcast TV** footage, while ours is
amateur, low, extremely oblique, set in a multi-pitch complex, and is itself a
*ball-following virtual crop*. Each individual frame simply shows too little pitch to
calibrate.

**The insight.** Veo is not solving our problem. Veo calibrates its own camera rig
against the **full panorama**, with known intrinsics and the whole pitch in view. We hold
a derived crop of that panorama. Veo will not export the panorama (confirmed by the
user), so the move is to *reconstruct* it.

**The approach.**
1. Stitch sampled frames into a pitch mosaic.
2. Calibrate the mosaic **once** — it shows the whole pitch, which is far closer to the
   broadcast-style input the pretrained models expect.
3. Propagate: every frame inherits metres via `frame → mosaic → pitch`.

**Already proven, do not re-measure:**
- Frame-to-frame registration works: **0.31–3.93 px** round-trip error when RANSAC
  inliers >= 100. Below ~40 inliers it is garbage (36–52 px). The gate is measured.
- It also works **densely**: 12,343 pairs at 2 fps over the full match, median 612
  inliers, **99.6 % above the gate**, 11 min of CPU on the local 720p proxy (D-0).
- Inlier counts depend on **view overlap, not time separation**, so mosaic construction
  should be ordered by view, not chronologically.
- 4 anchors at gate 100 cover 100% of sampled frames.
- PnLCalib is installed on gpu-box at `/opt/PnLCalib` with weights, and runs.

**Hard constraint measured by D-0 — build the mosaic on anchors, never by chaining.**
Integrating per-pair `dx` accumulates a **10.6x drift factor**: between frames that are
genuinely 58 px apart (kickoffs, verified by direct registration), chaining reports
616 px median and 1490 px worst case — a third of the whole 4578 px pan range. So the
anchor/set-cover design is **required, not one option of two**, and every frame must be
registered to an anchor rather than to its predecessor. A short validation window will
hide this: over 30 minutes the chained trajectory looks bounded and well-behaved.

**Real risks.** Stitching a zooming virtual camera into one consistent mosaic is not
trivial; accumulated drift, exposure changes across the match (mean brightness falls
146 → 78 as the light goes), and the adjacent pitches all fight it. It may still fail.

**What unblocks if it works:** the radar minimap, speeds in m/s, possession distances,
and the metric half of Tier B.

---

## D-B. Pixel-space Tier A detection (no metres required)

**Status:** not started. This is the pragmatic path to real event detection *without*
solving calibration.

**The insight.** Most Tier A detection does not need metres — it needs pitch-relative
**regions**:

| event | what it actually needs |
| :-- | :-- |
| Shot | ball speed + direction toward the goal mouth — definable in anchor pixel space |
| Corner / throw-in / goal kick | ball crossing a boundary — a polygon in pixel space |
| Goal | the restart signature (ball near centre spot, players split by half) — coarse |

Metres are genuinely required for only two things: **the radar display and speeds in
m/s**. So Tier A event detection can ship against the real 447-event benchmark while
calibration remains unsolved, with the radar honestly showing "not available".

**Approach.** Define the pitch polygon and key zones in each anchor's pixel space, map
each frame to its anchor by the proven registration, and run detection there.

**Note on the honesty rule.** Zones must be derived automatically, not hand-drawn — the
user's standing instruction is no manual annotation. The open question is how to obtain
them without a working calibration; one candidate is deriving them from the *aggregate*
of detected player positions and ball trajectories over the match, which is
self-supervising and needs no labels.

**What unblocks if it works:** 7 of 14 event types (~196 of 447 events, 44% of mass),
and 5 of the 13 stat rows — scored honestly against the real benchmark.

---

## D-C. Smaller items noted along the way

- **Pitch dimensions are assumed 105x68.** A U16 field is likely ~100x64. Some of the
  measured misalignment may be model mismatch rather than camera error. Cheap to test by
  scaling the pitch model, and it would sharpen every metric number.
- **G7 jersey recognition** — sequenced last by design; unlocks zero event types. No
  roster is available from Veo, so it must be open-set with abstention, or Veo-label
  leakage that is declared as such.
- **`RadarBall.x/y` are non-Optional** in the data model, so "no ball" cannot be
  expressed structurally. The UI now draws nothing when `detected` is false, but the
  schema still requires coordinates.
- **One pre-existing lint warning** at `frontend/src/App.tsx:86` (`set-state-in-effect`),
  untouched.
