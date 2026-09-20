# Deferred work

Parked deliberately, not forgotten and not failed-and-hidden. Each entry says what it
would buy, what is already proven, and what the real risk is — so a future session can
judge whether to pick it up without re-deriving any of it.

---

## D-A. Rebuild the pitch panorama by stitching, then calibrate that

**Status:** not started. This is the root-cause fix for metric pitch coordinates.

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
- Inlier counts depend on **view overlap, not time separation**, so mosaic construction
  should be ordered by view, not chronologically.
- 4 anchors at gate 100 cover 100% of sampled frames.
- PnLCalib is installed on gpu-box at `/opt/PnLCalib` with weights, and runs.

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
