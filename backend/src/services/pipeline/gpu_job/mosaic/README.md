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
| `calibrate_panorama.py` | ray-space pitch pose — **does not converge**, see below |

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

## The next step, and why it should work

**Anchor the fit on the centre circle.** It is now crisply and unambiguously detected in
the line map, and it removes exactly the degeneracies being exploited:

- its centroid fixes the ray to the pitch centre, giving `tx, ty` once the normal is
  chosen, and
- its known 9.15 m radius against its apparent angular size fixes the **camera height**,
  which is the parameter currently running to its bound.

That leaves roughly four free parameters instead of eight, over a well-conditioned
search. The halfway line — unambiguous, vertical, at the panorama centre — then fixes the
in-plane rotation.
