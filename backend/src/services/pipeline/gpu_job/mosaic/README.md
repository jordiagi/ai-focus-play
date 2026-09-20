# Panorama reconstruction (D-A)

Veo calibrates its own rig against the **full panorama** — known intrinsics, whole pitch
in view. We hold a ball-following crop of that panorama, and Veo will not export the
original (confirmed by the user). Every per-frame calibration attempt failed because a
single frame of this footage shows too little pitch. D-A's answer: **reconstruct the
panorama**, then calibrate that once.

**Status: the panorama is built and the line evidence is good. The pose fit is NOT
solved** — there are still no metric coordinates. Step 3 was attempted and failed; the
failure is diagnosed below rather than hidden, because the diagnosis names the next
step.

All CPU, on the local 720p proxy.

## Scripts, in the order they were used

| script | question it answers |
| :-- | :-- |
| `measure_loop_closure.py` | is a globally consistent mosaic even possible here? |
| `build_mosaic.py` | planar mosaic — **failed**, kept because the failure is the reason for the next script |
| `build_panorama.py` | rotating-camera panorama — **works** |
| `build_line_map.py` | line evidence, composited from the sharp source frames — **works** |
| `calibrate_panorama.py` | ray-space pitch pose, 8-D search — **degenerate**, kept for why |
| `calibrate_from_circle.py` | pose anchored on the centre circle — **circle fits exactly, pitch does not** |

## Step 0 — the planar model holds (so drift is fixable)

D-0 measured that chaining frame-to-frame drifts **10.6x**. That could mean the model is
wrong, or merely that the estimate is bad. The distinction decides whether D-A is
possible at all, and the existing 0.31–3.93 px round-trip figure could not tell them
apart: A→B→A fits `H_BA` as the inverse of the same correspondences, so it is
self-consistent by construction.

A closed loop over **three** frames can tell them apart. Composing A→B→C→A must give the
identity, and any residual is model error that no optimisation will remove.

| 4000 triangles, 186 frames, gate >=100 inliers | px |
| :-- | --: |
| median closure error | **0.97** |
| p90 | 3.12 |

And it is **flat in loop span** — 0.62 px across <300 s, 1.93 px across 4500 s. The
planar model holds; the drift is an estimation problem with loop closures available to
fix it. 181 of 186 frames sit in one connected component (2798 gated edges, median
degree 29).

## Step 1 — a planar mosaic cannot work (the bowtie)

`build_mosaic.py` solves the whole graph globally — widest-bottleneck init, then sparse
bundle adjustment over all 2798 edges — and reaches a **1.34 px median edge residual**.
The geometry is right and the render is still garbage: frames warp onto one frame's
*image plane*, the camera's pan spans **129.5°**, and everything past 90° stretches
toward infinity. Kept in the tree as the reason step 2 exists.

## Step 2 — the rotating-camera model works

The correct model is the one matching what Veo does: a camera rotating about a fixed
centre with varying focal, compositing onto a **sphere**, which has no 90° singularity.
OpenCV's stitching detail API, then a per-pixel **median** across frames.

Result: **4414 x 1190, 125.4° horizontal FOV, 90.2% coverage**, whole pitch with both
goals, median stack depth 14. The median is what makes it usable — pitch is stationary
while players move through it, so compositing dissolves the players and leaves the line
markings. Artifacts land in `backend/.local/artifacts/mosaic/`.

## The lesson worth keeping

**OpenCV's `BundleAdjusterRay` does not refine focal length**, and
`HomographyBasedEstimator` assigns *one* focal to every camera. On a zooming camera that
silently forces a constant-focal model and dumps the error into the rotations, which is
what washed out the line markings in the first attempt. `BundleAdjusterReproj` does
refine focal and went degenerate here — it returned a **negative** focal.

On this match the focal varies **2.41x**, and only 25% of frames sit within ±10% of the
median. The assumption is not close, and nothing in the API says it is being made.

The fix is in `relative_focals()`: for an edge between similar views the homography's
local scale at the image centre is `f_j/f_i`, giving one linear equation per edge in log
space. Solving all 2798 at once is drift-free for the same reason the mosaic is — it
uses every loop rather than a chain — and the result is handed to Ray, which then only
has to solve rotations.


## Step 3 — ray-space calibration: attempted, NOT solved

Because the pan spans 125 degrees, **no single homography maps the panorama to the
pitch plane** — no pinhole image can contain this pitch. Every earlier attempt in this
repo assumed a homography, and that assumption was wrong before any tuning started. The
right object is the ray: each panorama pixel is a direction, the pitch is the plane those
rays strike, and the calibration is 8 numbers (normal tilt/roll, camera height, in-plane
rotation, 2D offset, pitch L and W).

**What is verified correct.** The spherical projection matches OpenCV's own
`PyRotationWarper.warpPoint` to the pixel. The closed-form solution — two parallel
ground lines give the vanishing direction, a perpendicular one gives the plane normal —
recovers all 8 parameters *exactly* from synthetic ground truth. The geometry is not the
problem.

**Two real defects were found and fixed on the way**, both of which had been silently
degrading everything:

- `pitch_model` scaled a 105x68 template, which stretched the penalty areas with the
  pitch. Their sizes are fixed by the Laws (16.5, 40.32, 5.5, 18.32, 9.15) and that
  fixedness is the *only* thing breaking the scale degeneracy — a pure similarity of the
  whole pitch reprojects identically. Scaling them removed the information the fit needs.
- The objective was piecewise constant (nearest-neighbour sampling plus an 8 px recall
  grid), so Nelder-Mead was descending a staircase and doing nothing. Now bilinear.

**Step 3a, the line map, is a large measured gain.** Calibrating against the RGB median
composite was hopeless because the median is what removes the players but also averages
away a 1-2 px line. Detecting lines per frame — where they are sharp — and compositing
the *response* instead gives a map where the centre circle, halfway line, both
touchlines and both penalty areas are all clearly present:

| evidence image | model points on a line (<=3 px) | median distance |
| :-- | --: | --: |
| RGB median composite | 0.096 | 118 px |
| **warped line-response map** | **0.26** | 15-46 px |

**But the fit still does not converge.** Best runs reach 0.26 with the camera height
pinned at the 1-2 m bound and L or W on a bound too. A Veo camera is on a pole; 1 m is
not a plausible answer, and parameters resting on bounds are the standard tell that the
optimiser is exploiting a degeneracy rather than finding the pitch. Different restarts
land on different local optima (median distance 15 px vs 46 px). **Do not read the 0.26
as nearly matching PnLCalib's 0.29 — both are failures, and this one is not even
physically plausible.**

**Why it fails, specifically.** Great-circle RANSAC resolves only three or four
*distinct* physical lines (circles 0/2/5 are the same line found three times, offsets
agreeing to 3 decimals), and the near-horizon ones are ill-conditioned — one returned an
offset of 62 camera-heights. With so few independent constraints the orthogonality
criterion barely discriminates: R = 0.84 at exact vertical against 0.89 at its optimum,
with several comparable peaks.

## Step 3b — centre-circle anchor: the degeneracies are gone, the pitch still will not fit

Anchoring on the centre circle worked exactly as intended for the *pose*. A circle of
known radius (9.15 m, fixed by the Laws at every pitch size) seen by a calibrated camera
determines the plane, so it pins the ground normal, the camera height and the pitch
centre in one solve.

| | 8-D search (3) | centre-circle anchor (3b) |
| :-- | :-- | :-- |
| camera height | 1.0-2.0 m, **on the bound** | **6.71 m** — plausible for a pole |
| ground normal | unconstrained | **0.87° off vertical** — matches wave correction |
| parameters on bounds | several, every run | **none** |
| pitch size | 87-115 m, on bounds | **104.3 x 69.6 m**, read off the line offsets |
| centre circle fit | — | **median 0.0 px, 68 % within 3 px** |

Two degeneracies had to be removed first, and both were found by unit-testing against
synthetic ground truth rather than by reading output:

- Letting `h` float gives a **trivial global optimum at h = 0**, where every ray
  collapses to the camera centre and any centre at distance r fits with exactly zero
  residual. Both scipy optimisers drove straight to it. Fix: fix h = 1, let the radius
  float, recover h = 9.15/rho.
- The parameters span 0.05 to 200 in magnitude, so the solve needs an explicit
  `x_scale`. Without it, it walked to the bounds from every start.

**But no standard pitch aligns with the rest of the lines.** An exhaustive scan — every
in-plane rotation at 0.5°, over a grid of L and W, with the circle-derived pose held
fixed — never gets the outline above about 25 % within 3 px:

| element | median error | within 3 px |
| :-- | --: | --: |
| centre circle | **0.0 px** | **0.68** |
| halfway line | 17-31 px | 0.06-0.20 |
| touchlines | 16-42 px | 0.04-0.25 |
| goal lines | 17-36 px | 0.00-0.19 |

**It is not panorama distortion.** That was the obvious suspect — perfect at the centre,
bad at the edges — so it was measured: line half-width in the accumulated map grows only
**1.17x** from centre to edge (1.96 px to 2.30 px). The panorama registers to a few
pixels throughout, which cannot explain a 20-40 px misalignment.

**The evidence points at the multi-pitch complex.** Only **one** touchline-parallel line
is found at a pitch-like distance from the fitted circle (-34.9 m, detected nine times
over); a genuine pitch centre would have two, symmetric at +/-W/2. The detected lines
appear to span more than one field — which is the same structural problem that defeated
the three earlier calibration attempts, reappearing after the panorama removed the
"too little pitch per frame" problem.

## The next step

**Use Veo's own events to decide which lines are ours.** The 447-event ground truth
carries a video timestamp for every event, and `frame -> panorama` is solved (per-frame
R and focal). The virtual camera follows the ball, so projecting each event frame's
centre into the panorama traces where play actually happened. That point cloud outlines
**our** pitch; lines outside it belong to adjacent fields and can be dropped before
fitting. It needs no annotation and no ball detection, and it uses ground truth already
on disk.
