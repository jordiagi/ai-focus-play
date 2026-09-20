# Panorama reconstruction (D-A)

Veo calibrates its own rig against the **full panorama** — known intrinsics, whole pitch
in view. We hold a ball-following crop of that panorama, and Veo will not export the
original (confirmed by the user). Every per-frame calibration attempt failed because a
single frame of this footage shows too little pitch. D-A's answer: **reconstruct the
panorama**, then calibrate that once.

**Status: the panorama is built. It is not yet calibrated** — metric coordinates are
still unavailable, and that is the next step.

All CPU, on the local 720p proxy.

## Scripts, in the order they were used

| script | question it answers |
| :-- | :-- |
| `measure_loop_closure.py` | is a globally consistent mosaic even possible here? |
| `build_mosaic.py` | planar mosaic — **failed**, kept because the failure is the reason for the next script |
| `build_panorama.py` | rotating-camera panorama — **works** |

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
