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
| `locate_play_region.py` | which field is ours, from Veo's 447 events — **works** |
| `fit_pose_from_events.py` | pose from event azimuths — **constrains γ and L, not W** |

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

## Step 3c/3d — Veo's events: which field is ours, and the pose from azimuth

`locate_play_region.py` registers the frame at 220 event times into the panorama
(**213 located, 96.8 %**, gate >=100 inliers) and projects the frame centre. Two results:

**It confirms which field is ours.** The cloud straddles the fitted centre circle, and
the bright foreground structures — the big curves and V shapes along the bottom of the
panorama, which every line fit had been trying to match — fall **outside** it. They
belong to a nearer field. Masking to the play region keeps 44.6 % of line pixels.

**It also kills an assumption worth recording.** The cloud is a narrow elevation band
barely taller than the centre circle itself (v 427-591 of 1190). Veo's virtual camera
pans and zooms but hardly tilts, so frame-centre elevation is almost constant wherever
the ball is. **The frame centre is useless as a proxy for the ball's ground position in
elevation.** In azimuth it is excellent: corr(veo_x, azimuth) = **+0.904**, rising
monotonically across all ten deciles of pitch length, against corr(veo_z, azimuth) =
+0.08.

So `fit_pose_from_events.py` fits azimuth only — which is also scale-invariant, so it
cannot trade against camera height the way the line fit did. Residual **4.9° median**
against a 39.9° baseline for a meaningless pose.

## Where this leaves it: the pose converges, the outline does not

Independent methods now agree on most of the pose:

| quantity | value | agreeing sources |
| :-- | :-- | :-- |
| camera height | **6.71 m** | centre circle (radius 9.15 m) |
| ground normal | **0.87° off vertical** | centre circle; matches wave correction |
| in-plane rotation γ | **168.6-171.1°** | line offsets, circle anchor, event azimuths — three routes within 2.5° |
| pitch width W | **68.5-69.8 m** | touchline offset (69.8), line-evidence scan (68.5) |
| centre circle | **0.0 px median, 68 % within 3 px** | and the event cloud confirms it is on OUR pitch |

**And yet the pitch outline still will not fit.** Touchlines land 24-39 px out, goal
lines 31-51 px, halfway 24 px, with <=3 px fractions of 0-14 % — while the circle stays
at 0.0 px. Pitch length L remains unstable (101-120 m, often against a bound), because
azimuth constrains it only weakly and the goal lines are near the horizon.

**There are still no trustworthy metric coordinates.** Five approaches have now been
measured and none delivers a validated pitch: ball correspondences (1854 m, then
10-15 m), PnLCalib pretrained (88-110 m), 8-D ray-space search (degenerate),
centre-circle anchor (pose plausible, outline unfitted), and event azimuths (γ and L
only).

**Honest read of the remaining gap.** Everything that is locally anchored — the circle,
the camera height, the plane, the bearing — agrees across independent methods. Only the
pitch *outline* fails, and the touchlines are exactly what is hardest to observe here:
the far one sits on the horizon and the near one may fall outside the panorama or be
buried under the foreground field's markings. Before another fitting attempt, it is
worth establishing whether our pitch's own touchlines are present in the evidence at
all — because every fit so far has assumed they are.

---

# D-B — pitch-relative zones without metres

D-B ships Tier A detection in **pixel space**, so it needs the pitch region and a few
zones but no calibration. The standing rule is that zones are **derived, not drawn**.

| script | question it answers |
| :-- | :-- |
| `../detect_players.py` (gpu-box) | where are the players? 600 frames, 15,380 persons, 16.5 s on one H100 |
| `build_occupancy_map.py` | where do they stand in panorama space? |
| `derive_zones.py` | is the resulting region actually the pitch? |

## The premise is now measured, not assumed

D-B argues that metres are unnecessary. This run shows they are also **unusable**.
Inverting the 14,607 mapped player foot points onto the fitted ground plane gives an
oriented bounding box of **105.8 x 104.5 m — aspect 1.01**, a square, where a pitch is
about 1.5, with a 124 m spread in depth. Near the horizon the far half of the pitch
compresses into a few pixels, so a small pixel error is tens of metres. The same cloud
in panorama pixels is perfectly well behaved. That is the case for D-B, made with a
measurement rather than an argument.

## What the occupancy map gives

600 in-play frames (halftime excluded — the pitch is empty and the warm-up clusters in
one corner), **95.7 % registered** into the panorama at the >=100-inlier gate, **14,607
player points** mapped, 92 % of them in a single blob. The foot point is the
bottom-centre of the box, because that is the point on the ground; the box centre floats
half a body above it by a distance that varies with range.

## And what it does NOT give: a precise boundary

A region containing the players is not the same as the pitch, so the derivation was
tested: what fraction of the polygon's boundary lands on a detected line pixel, against
the fraction a random boundary of the same length achieves.

| density pct | area frac | players inside | boundary on a line | chance | lift |
| --: | --: | --: | --: | --: | --: |
| 60 | 0.229 | 0.974 | 0.021 | 0.033 | 0.64 |
| 70 | 0.159 | 0.922 | 0.034 | 0.033 | 1.03 |
| **80** | 0.109 | 0.864 | **0.083** | 0.036 | **2.35** |

**2.35x chance is real but weak.** The region is usable as a soft "is this on the playing
surface" test — it holds 86 % of players and the centre circle sits inside it — but its
boundary is *not* the touchline. Only 8 % of it lies on a detected line, and the lower
edge is visibly ragged.

So of D-B's three zone uses, occupancy supports the coarse one and not the sharp one:
**Goal** needs only coarse position and is served; **corner / throw-in / goal kick**
need the ball *crossing a boundary*, and an 8 %-aligned ragged contour is not that
boundary. Sharpening it is the next question, and the obvious candidate is to fit a
smooth quadrilateral to the occupancy rather than trusting a density contour.

## D-B steps 4-6 — the ball

`../detect_ball.py` (gpu-box) reuses G1's measured tiling. Over the **whole match at
5 fps, 23,874 frames, candidate rate 0.8344** — G1 measured 0.833 / 0.828 on two
isolated 600 s slices, so the gate was not a windowing artefact. `map_ball_to_panorama.py`
registers 94.1 % of those frames and maps 36,291 candidates into panorama space;
`associate_ball.py` picks a track by Viterbi.

### A test-design error, and the correction

The association was first scored by correlating the chosen candidate's panorama azimuth
with Veo's pitch-length coordinate `x`, against the camera's own aim as baseline. Every
variant lost:

| selector | corr with veo_x |
| :-- | --: |
| top confidence | 0.824 |
| Viterbi track | 0.833 |
| nearest to frame centre | 0.846 |
| conf >= 0.55, top confidence | 0.882 |
| **camera aim (frame centre)** | **0.909** |

**That test is contaminated and should not be used.** Veo's virtual camera aim and Veo's
event coordinates are both outputs of Veo's own internal ball tracking, so the baseline
and the target share a source. It asks an independent detector to beat Veo at
reproducing Veo, which it cannot do however good it is. The consistency of the ~0.82-0.88
band across completely different selectors was the clue.

### The uncontaminated test: the ball at kickoff

A kickoff puts the ball **on the centre spot**, whose panorama position comes from the
fitted centre circle — no Veo tracker involved. Reporting the **top-confidence**
candidate, because that is what a detector actually outputs (nearest-of-five would be
oracle selection):

| | median distance from the centre spot |
| :-- | --: |
| top-confidence candidate (n=8) | **94 px = 3.0 m** |
| ... with top-conf >= 0.45 (n=6) | **58 px = 1.9 m** |
| ... with top-conf < 0.45 (n=2) | 135 px = 4.4 m |
| arbitrary candidate, any time (control) | 619 px = **20 m** |

So the detector does find the ball, and confidence carries information — but read this
with three caveats. **n = 8.** Confidence is not a guarantee: two of the six confident
kickoffs were still 3.6 m and 4.4 m out. And at 5 fps a ±0.1 s timing offset moves a
just-kicked ball a metre or two, so part of the residual is sampling, not detection.

### The trajectory: fixed by letting the tracker say "no"

The 13.6 % of impossible steps was **my bug, not a detector limit**. The first Viterbi
had to pick a candidate in every frame; since barely half of frames hold a plausible
one, it was forced onto a false positive in most of them. Adding an explicit miss state
— states are (frame, candidate), transitions may skip frames at `miss_cost` each, and
virtual START/END nodes make the path span the run so the output is a full
assign-or-decline labelling:

| miss_cost | coverage | track points | median step | steps over vmax |
| --: | --: | --: | --: | --: |
| 0.8 | 0.284 | 5,333 | 80.7 px/s | **0.02 %** |
| **1.8** | **0.586** | **10,994** | 85.4 px/s | **0.51 %** |
| 2.5 | 0.700 | 13,134 | 83.0 px/s | 0.94 % |

**13.6 % → 0.1-0.9 %.** `miss_cost` is the decision threshold in disguise: a candidate
is worth taking when `-log(conf)` falls below it, so 1.2 means "assign above conf ~0.30".

Note the first attempt at this returned **37 points from 18,752 frames** — without the
START/END nodes the cheapest path is a single frame, because any state may begin a
chain at zero cost.

### How good is the track, really

| measure | value |
| :-- | --: |
| centre spot at kickoff, window ±0.6 s, all 8 kickoffs | **5.7-6.2 m** |
| ... stationary window before the whistle (only 3 kickoffs covered) | **3.9 m** |
| raw top-confidence candidate at the kickoff frame (n=8) | 3.0 m |
| control: track sampled at arbitrary times | **24.5 m** |

Real but coarse — roughly 4-6x better than chance. Two honest caveats: **n = 8**, and
the centre spot itself comes from an ellipse fit, so part of the residual is the
reference, not the track.

The contaminated correlation test did improve with the clean track (0.833 → **0.885**,
against a favoured baseline of 0.907), which is consistent with a better track but
cannot prove it — losing that test means nothing, only winning would.

## D-B step 8 — the first scored Tier A detector: FootballOutOfPlay

64 events, the largest Tier A type, and it needs **no metres**.

The signature was measured before anything was built — medians over the 64 events
against 600 random in-play times:

| window | at OutOfPlay | at random |
| :-- | --: | --: |
| ball speed, [-1, +0.5] s | **196 px/s** | 77 |
| track coverage, [+0.5, +3.5] s | **0.20** | 0.53 |
| ball speed, [+2, +6] s | **35 px/s** | 93 |

The physical story reads straight off it: the ball is struck hard, leaves the field,
stops being trackable, then sits still while someone fetches it. All 64 are followed by
a restart (38 throw-ins, 16 goal kicks, 9 corners) a median 17 s later.

### Result — RESTATED 2026-09-20, the original figures did not reproduce

**The numbers first published here (period 1 n=51 tp=12 F1 0.296; period 2 n=39 tp=14
F1 0.384; both n=90 tp=26 F1 0.338) cannot be regenerated.** The committed script run
against the stored `ball_track.json` does not produce them at any setting tried: an
8-cell `min_sep` sweep, a 5-cell `fps` sweep and a 48-cell sweep over NaN-rank handling,
candidate cap and `min_sep` together. The invocation was never recorded and the stored
`pred_oop.json` / `score_oop.json` were overwritten before the gap was noticed. See the
incident note in `STATE.md`.

What is reproducible, with `min_sep` selected by period-1 F1 over 2,3,4,5,6,8,10,12
(5.0 wins at 0.265) and the threshold then fitted on period 1:

| | n_pred | n_ref | tp | precision | recall | chance recall | F1 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| period 1 (dev) | 106 | 30 | 18 | 0.170 | 0.600 | 0.125 | 0.265 |
| **period 2 (held out)** | 81 | 34 | 22 | **0.272** | **0.647** | **0.097** | **0.383** |
| both periods | 187 | 64 | 40 | 0.214 | 0.625 | 0.209 | 0.319 |

Held-out F1 **0.383** is within 0.001 of the figure originally published, which is a
coincidence worth naming rather than leaning on: the *profile* is quite different —
recall 0.647 where the old row said 0.412, precision 0.272 where it said 0.359, and 187
predictions where it said 90. **Held-out recall is 6.7x chance, not the ~8x first
claimed.** The held-out half again scores higher than dev (gap -0.118).

`scripts/local/score-benchmark.py` reproduces the both-periods row from
`pred_all.json` (team-agnostic block: F1 0.319).

### What this result is not

- **Team is not predicted.** Veo labels each OutOfPlay Own or Opponent, and the repo's
  primary metric is team-aware, under which this scores **0 by construction**. The
  figures above are the team-agnostic block. The type cannot reach parity until team is
  attempted.
- **Precision is 0.289** — 64 of 90 predictions are wrong. Useful as a candidate
  generator, not as a finished event list.
- **One feature is a detector failure.** Coverage collapses because the ball leaves the
  region the tracker can follow. That is caused by the event so it is legitimate
  evidence, but it makes the detector depend on the tracker's weakness: improve the
  tracker and this feature weakens.
- Macro-F1 over the benchmark is still **1 of 14 types, 14 % of event mass**.

## D-B step 9 — an occupancy-derived coordinate frame, and what it is not

Restart types differ by **where the ball was**, so typing them needs a pitch-relative
coordinate. Neither panorama axis is one on its own: `u` mixes length with pan and `v`
mixes width with depth, because the pitch is a trapezoid here. `derive_pitch_frame.py`
fits two weighted quadratics through per-`u`-bin percentiles of the **player occupancy
cloud alone** — 14,607 foot points, no Veo coordinate anywhere — and normalises between
them:

    xi(u)    = (u - u_lo) / (u_hi - u_lo)
    eta(u,v) = (v - v_far(u)) / (v_near(u) - v_far(u))

The quadratic is not decoration: the far boundary is V-shaped (412 px at u=650, 371 at
u=1950, 433 at u=3750) because the panorama is spherical, and a straight line fits it
**2.8x worse** (residual 20.3 px vs **7.39**).

**The boundaries are not the touchlines, and this was measured rather than assumed.**
Scored against the line-evidence map exactly as the pitch region was, both fitted curves
land on a detected line *no more often than a random horizontal curve*:

| curve | on a detected line |
| :-- | --: |
| fitted far boundary | 0.028 |
| fitted near boundary | 0.010 |
| **random horizontal curve (chance)** | **0.040** |

So it is a monotone re-parameterisation that correlates with pitch position, and that is
all it is claimed to be. The near edge is visibly the worse of the two — its own fit
residual is **50.1 px** against the far edge's 7.4, because substitutes, staff and the
far crowd are in the cloud. Every threshold built on this frame is therefore **fitted on
period 1**, never read off as geometry.

What does support it is external and measured: `corr(veo_z, v) = -0.727` against
`corr(veo_z, u) = -0.331`, and `corr(veo_x, u) = +0.832` against `corr(veo_x, v) =
+0.113` — the two axes separate. And all **8 kickoffs land inside xi [0.39,0.50],
eta [0.52,0.60]**, a box no other restart type enters.

## D-B step 10 — the dead-ball restart family

Step 8 noted that every OutOfPlay is followed by a restart, and proposed the OutOfPlay
detector as their candidate generator. Measuring first showed that is the wrong way
round: **the restart has a stronger and more direct signature than the stoppage**, and
needs nothing from the OutOfPlay detector.

Medians over each type against 800 random in-play times, in panorama px/s:

| type | n | speed [-4,-0.5]s | speed [0,+1.5]s | post/pre ratio |
| :-- | --: | --: | --: | --: |
| ThrowIn | 38 | 13.0 | 202.2 | 5.0 |
| GoalKick | 16 | 1.8 | 101.7 | 105.8 |
| CornerKick | 9 | 1.3 | 52.8 | 38.6 |
| FreeKick | 15 | 2.1 | 285.4 | 23.9 |
| KickOff | 8 | 1.5 | 240.5 | 52.8 |
| interception | 89 | **149.5** | 111.5 | 0.8 |
| tackle | 84 | **124.8** | 92.5 | 0.8 |
| dribble | 41 | **144.6** | 112.2 | 1.0 |
| *random* | 800 | 30.9 | 23.5 | 0.9 |

The five dead-ball types sit at 1-13 px/s beforehand; every in-play type sits at
125-150. That is not a tuned margin, it is the difference between a stationary ball and
a moving one — so **one detector covers all five**, 86 events against OutOfPlay's 64.

### Detection — the family as one class, timing only

Config chosen by period-1 F1 over a 36-cell sweep (pre window x post window x
coverage-feature x min-sep); threshold fitted on period 1 and applied unchanged.

| | n_pred | n_ref | tp | precision | recall | chance | F1 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| period 1 (dev) | 40 | 40 | 19 | 0.475 | 0.475 | 0.049 | 0.475 |
| **period 2 (held out)** | 43 | 46 | 17 | **0.395** | **0.370** | **0.053** | **0.382** |
| both periods | 83 | 86 | 36 | 0.434 | 0.419 | 0.099 | 0.426 |

Dev-to-held-out gap **+0.093**, so unlike step 8 this one *is* mildly optimistic on dev —
36 configs were tried on period 1. Held-out precision 0.395 is still markedly better
than step 8's 0.359 on a larger type set.

### Type, from position

`xi` and `eta` at the top-confidence ball candidate in [-2, +0.5] s. Given **true** event
times the classifier is right **61 %** of the time (84 of 86 events have a position at
all), which is the ceiling everything below is multiplied down from by detection recall:

| true \ predicted | KickOff | GoalKick | ThrowIn | Corner |
| :-- | --: | --: | --: | --: |
| **KickOff** (8) | **8** | | | |
| **GoalKick** (16) | | **14** | 2 | |
| **ThrowIn** (37) | | 4 | **26** | 7 |
| **CornerKick** (8) | | 2 | 3 | **3** |
| *FreeKick* (15) | 1 | 1 | 13 | |

ThrowIn is the catch-all, and that is a measured choice, not laziness: four positive-cue
rules were tried and every one lost on period-1 F1 (`eta>0.25` → 0.207, `eta>0.25 or
|xi-.5|<0.28` → 0.238, `eta>0.35` → 0.160, `|xi-.5|<0.30` → 0.158, catch-all → **0.261**).

**FreeKick is not attempted**, declared in the manifest before scoring: its `eta` cloud
(median 0.64) sits inside ThrowIn's bimodal one (0.05 / 0.67) with no cue between them.
Its 15 events therefore arrive as ThrowIn false positives, which is most of why ThrowIn's
precision is 0.21.

### End-to-end, per type (team-agnostic; `score-benchmark.py` reproduces every row)

| type | n_ref | n_pred | tp | precision | recall | chance | F1 | held-out F1 |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: |
| **KickOff** | 8 | 4 | 4 | **1.000** | 0.500 | 0.004 | **0.667** | **0.800** |
| GoalKick | 16 | 13 | 4 | 0.308 | 0.250 | 0.013 | 0.276 | 0.267 |
| ThrowIn | 38 | 52 | 11 | 0.212 | 0.289 | 0.049 | 0.244 | 0.235 |
| CornerKick | 9 | 11 | 1 | 0.091 | 0.111 | 0.011 | 0.100 | 0.000 |

**KickOff is the first detector in this project with perfect precision** — 4 predictions,
4 correct, against a chance recall of 0.004. It is also the easiest: the centre spot is
one place, and the frame locates it tightly.

### The negative control, which is what makes those numbers mean anything

20 trials per type, same `n_pred`, times drawn uniformly in play:

| type | real F1 | random mean | random max | a result? |
| :-- | --: | --: | --: | :-- |
| KickOff | 0.667 | 0.000 | 0.000 | yes |
| GoalKick | 0.276 | 0.010 | 0.069 | yes |
| ThrowIn | 0.244 | 0.044 | 0.111 | yes |
| **CornerKick** | **0.100** | 0.020 | **0.100** | **no** |
| macro | **0.322** | 0.019 | | |

**CornerKick exactly ties the control's best trial, so it is not a result** — consistent
with its held-out F1 of 0.000 and with 7 of its 9 events being in period 1. It is
reported because it was attempted and declared, not because it worked.

A rounding bug nearly hid that: the verdict compared a 4-dp real F1 against an unrounded
control maximum, and `0.1 > 0.09999999999999999` read True. Both sides are now compared
unrounded, with a margin, because a tie is not a win.

### Two things worth keeping

1. **The consequence relation ran backwards.** Step 8's plan was OutOfPlay → restart.
   Measuring the restart first showed it is the stronger, cheaper signal and needs no
   OutOfPlay detector at all. The stoppage is inferred from the restart, not the reverse.
2. **Fitting a rule on 7 examples buys dev macro-F1 and nothing else.** Adding the
   CornerKick rule raised period-1 macro-F1 from 0.280 to 0.314 and moved held-out macro
   by -0.005. The protocol selected it; the held-out half said it was noise.

## D-B step 11 — team, and the repo's primary metric off zero

Every detector up to here scored **0 on the team-aware metric by construction**, because
none predicted a side. For two of the restart types the laws of the game decide it: a
**goal kick is taken by the side defending that end**, a **corner by the side attacking
it**. So "which side defends which end" settles both — and that is a *single bit*,
because the sides swap at half time.

The bit is fitted on period-1 goal-kick team labels (`in period 1 the xi<0.5 end is
defended by Own`) and period 2 follows from the swap, which makes period 2 a real test:
if the swap were wrong, or if Veo's Own/Opponent were camera-relative rather than
team-relative, period-2 accuracy would collapse to ~0.

**On true event times the rule is right 24 of 24:**

| | correct / of |
| :-- | --: |
| GoalKick, period 1 (where the bit was fitted) | 8 / 8 |
| **GoalKick, period 2 (held out — this tests the swap)** | **8 / 8** |
| CornerKick, period 1 | 7 / 7 |
| CornerKick, period 2 | 1 / 1 |

Two checks that this is the frame working and not a coincidence: our `xi` side agrees
with Veo's own pitch-length coordinate on **14 of 14** goal kicks that carry one, and
goal-kick team is separable by (our `xi` side, period) on **16 of 16** — with the sign
flipping at half time exactly as the swap predicts.

**What is not attempted, and why it was not guessed at.** ThrowIn team is ~50/50 in
every (end, period) cell — it needs possession, which is G4. KickOff team is whoever
conceded; the one positional cue available, which way the ball drifts over [+4,+12] s,
does not separate (Own kickoffs drifted -0.171, -0.150, **+0.383**). Both are declared
unpredicted in the manifest rather than filled in.

**This is one bit of label supervision and is named as such.** Without a roster or a
shirt-colour-to-label mapping it cannot be had for free — even colour clustering would
still need one bit to say which cluster is "Own".

## D-B step 12 — FootballGoal, inferred backwards from its kickoff

The same trick a third time. Step 10 found the restart easier to see than the stoppage
it ends; this finds the **goal easier to see through its kickoff** than directly. A goal
has no ball signature of its own — the ball is struck, which is what a shot looks like —
but it is always followed by a kickoff, and the kickoff detector is the most precise
thing in this repo.

Goal → kickoff gaps: **37.2, 38.1, 38.2, 53.1** (period 1) and **28.0, 38.5** (period 2).
Four of six sit within 0.4 s of 38.2, which at a 3 s tolerance is the whole game. The
offset is the median of the *period-1* gaps (**38.13 s**); the two outliers are simply
unreachable, and nothing here can fix that — a restart is taken when the players are
ready.

| | n_pred | n_ref | tp | precision | recall | chance | F1 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| period 1 (dev) | 1 | 4 | 1 | 1.000 | 0.250 | 0.001 | 0.400 |
| **period 2 (held out)** | 2 | 2 | 1 | 0.500 | 0.500 | 0.002 | **0.500** |
| both periods | 3 | 6 | 2 | 0.667 | 0.333 | 0.003 | **0.444** |

**Team costs nothing here either** — the team-aware block is identical to the
team-agnostic one, because both true positives carry the right scorer. A goal is scored
at the end the *conceding* side defends, so the step-11 map names the conceder and the
scorer is the other side; the same lookback that finds the goal also teams it. Random
control: real 0.444 against 0.000 mean and 0.000 max over 20 trials.

**Read it as low-n.** 6 reference events, 3 predictions. Recall is capped by the kickoff
detector's recall — a goal whose kickoff is missed is invisible — and the two
period-opening kickoffs have no goal behind them and are excluded rather than made to
invent one.

## A prediction budget, and what it fixed

Restating step 8 exposed a second problem: its F1-optimal threshold sat at **187
predictions for 64 events**, a chance recall of 0.209 at which the headline recall stops
meaning much and nothing downstream can use the list. That is F1 being gameable at low
precision — emitting more candidates lifts recall faster than it costs precision.

The fix is a declared **prediction budget**: cap `n_pred` at K × `n_ref` on period 1, and
take the **smallest K whose period-1 F1 is within 5 % of the unconstrained optimum**.
Parsimony unless it actually costs you. K is chosen on period-1 data alone.

| K | OutOfPlay period-1 F1 | n_pred |
| :-- | --: | --: |
| 1.0 | 0.143 | 12 |
| 1.5 | 0.189 | 44 |
| 2.0 | 0.189 | 44 |
| **3.0 (selected)** | **0.257** | **71** |
| unconstrained | 0.265 | 106 |

Held out, OutOfPlay improves on every axis that matters:

| | before | after |
| :-- | --: | --: |
| held-out F1 | 0.383 | **0.467** |
| held-out precision | 0.272 | **0.375** |
| held-out recall / chance | 6.7x | **9.1x** |
| both-periods n_pred | 187 | **127** |

**On the restart detector the same rule is a no-op** — its optimum already sits at 1.0x,
40 predictions for 40 period-1 events, identical F1 at every cap. That is the evidence
the budget is not quietly doing the detector's work: it bites only on the detector that
was buying recall by shotgunning.

### Where the benchmark now stands

**6 of 14 types attempted, 141 of 447 events — 32 % of event mass.**

| type | n_ref | n_pred | F1 team-agnostic | F1 team-aware |
| :-- | --: | --: | --: | --: |
| OutOfPlay | 64 | 127 | 0.356 | 0.052 |
| ThrowIn | 38 | 52 | 0.244 | 0.000 |
| GoalKick | 16 | 13 | 0.276 | **0.276** |
| CornerKick | 9 | 11 | 0.100 | 0.100 |
| **KickOff** | 8 | 4 | **0.667** | **0.500** |
| **Goal** | 6 | 3 | **0.444** | **0.444** |
| **macro** | | | **0.348** | **0.229** |

| | start of the day | now |
| :-- | --: | --: |
| types attempted | 1 | **6** |
| event mass | 14 % | **32 %** |
| macro-F1, team-agnostic | 0.338 | **0.348** |
| **macro-F1, team-aware (primary)** | **0.000** | **0.229** |
| **parity count (F1 ≥ 0.5)** | **0/14** | **1/14** |

Period-2 macro (0.261) again exceeds period-1 (0.186). **KickOff is the first type to
reach parity.** Every type that predicts team scores the same team-aware as
team-agnostic — when these detectors find an event, they get the side right.

### Reproducing steps 8-16 from the stored artifacts

Seconds, CPU only, no gpu-box — everything they read is already in
`backend/.local/artifacts/mosaic/`:

```sh
A=backend/.local/artifacts/mosaic
V=backend/.venv/bin/python
M=backend/src/services/pipeline/gpu_job/mosaic

$V $M/derive_pitch_frame.py --occupancy $A/occupancy_points.json \
    --line-map $A/line_map.png --out $A/pitch_frame.json

# restarts FIRST: OutOfPlay takes its team by inverting theirs (step 13), and Goal
# takes both its time and its team from the kickoffs among them (step 12)
$V $M/detect_restarts.py --track $A/ball_track.json --candidates $A/ball5_pano.json \
    --frame $A/pitch_frame.json --pred $A/pred_restarts.json \
    --manifest $A/manifest_restarts.json --out $A/score_restarts.json

# throw-in team from the thrower's shirt (step 14). The player artifacts are already
# pulled, so this needs no gpu-box; regenerating them does (detect_players_colour.py).
$V $M/team_from_shirt.py --players $A/pd_035060.json $A/players_predti.json \
    --ball-frame $A/ball5_frame.json --restart-pred $A/pred_restarts.json \
    --out-pred $A/pred_restarts_teamed.json --out $A/score_shirt.json --emit-team

$V $M/detect_out_of_play.py --track $A/ball_track.json \
    --restart-pred $A/pred_restarts_teamed.json \
    --pred $A/pred_oop.json --manifest $A/manifest_oop.json --out $A/score_oop.json

$V $M/detect_goals.py --restart-pred $A/pred_restarts_teamed.json --frame $A/pitch_frame.json \
    --pred $A/pred_goals.json --manifest $A/manifest_goals.json --out $A/score_goals.json

$V $M/merge_predictions.py \
    --pred $A/pred_oop.json $A/pred_restarts_teamed.json $A/pred_goals.json \
    --manifest $A/manifest_oop.json $A/manifest_restarts.json $A/manifest_goals.json \
    --out-pred $A/pred_all.json --out-manifest $A/manifest_all.json

# independent confirmation, and the repo's current headline over all 6 types
$V scripts/local/score-benchmark.py --pred $A/pred_all.json --manifest $A/manifest_all.json

# the control every team claim must clear -- replaces the team, keeps the predictions
$V $M/control_team_shuffle.py --artifacts $A \
    --restart-pred $A/pred_restarts_teamed.json --out $A/control_team.json   # ~5 min
```

Every script writes the **exact command that produced it** into its own output
(`command`). That exists because step 8's original figures could not be reproduced
afterwards: the invocation was never written down. Do not remove it, and do not report a
figure whose `command` field does not match how you ran it.

## D-B step 13 — OutOfPlay team by chaining, and two measured dead ends

### The chain: OutOfPlay team is the restart's, inverted

Veo labels an OutOfPlay with the side that put the ball out, and the restart goes to the
other side. In this match that relation is **exact — 64 of 64**:

| restart type | n | restart team vs the OutOfPlay before it |
| :-- | --: | :-- |
| ThrowIn | 39 | opposite, 39/39 |
| GoalKick | 16 | opposite, 16/16 |
| CornerKick | 9 | opposite, 9/9 |

So any OutOfPlay followed by a restart we can team, we can team by inversion. Note the
dependency runs **backwards through the step numbers** — step 8 now reads step 10's
output. That is the same inversion steps 10 and 12 found: what happens *after* an event
is repeatedly easier to see than the event itself.

It is a thin channel, and the thinness is the honest part. Only GoalKick and Corner
predictions carry a team, so only 41 of 127 OutOfPlay predictions get teamed; of those,
8 are also true positives, and the team is right on **6 of 8**. A relation that is
perfect in the ground truth degrades to what our own restart type-and-team predictions
are worth. OutOfPlay team-aware F1 goes **0.000 → 0.052**.

There is no downside to emitting it: an untimed prediction scores 0 team-aware anyway,
so a wrong team costs nothing that was not already lost.

### Dead end 1 — throw-in direction does not carry the taker

The obvious cue: a throw-in is taken by one side, who then have the ball, so the ball
should drift toward the end that side attacks. Measured over 35 throw-ins with both a
ball position and a post-throw track:

| | value |
| :-- | --: |
| direction rule correct | **17 / 35 = 0.486** |
| drift median, taker attacking the `hi` end | **-0.000** |
| drift median, taker attacking the `lo` end | -0.152 |

**A coin flip.** The two distributions are not even ordered the right way round. A
throw-in is as often played backwards to a defender as forward, so possession direction
in the first seconds says nothing about who threw it. Together with the earlier finding
that throw-in team is ~50/50 in every (end, period) cell, **position and direction are
both exhausted: throw-in team needs possession, i.e. who touched the ball last.**

### Dead end 2 — no local compute for the possession build

Possession needs players assigned to teams, which needs shirt colour. **Colour
separability is not the problem** — the kits were viewed rather than assumed, and they
are white against dark navy, about as separable as a kit pair gets, on uniform green
turf.

The problem is compute. There is no `torch`, `ultralytics` or `sklearn` in the local
venv (Python 3.14), and **gpu-box is unreachable again**: it pings at 17 ms with port 22
open, but `sshd` answers with

```
# Tailscale SSH requires an additional check.
# To authenticate, visit: https://login.tailscale.com/a/...
```

which is an interactive re-auth no agent can complete. Same blocker as 2026-09-20, same
fix. Until it clears, the possession work cannot start — it is not a design question any
more, just access.

## D-B step 14 — throw-in team from the thrower's shirt, and the control that nearly killed it

gpu-box came back, so the possession question could finally be asked. Throw-in team is
the one thing the defend-end map cannot reach, and both cheap cues were already dead
(position ~50/50 in every cell, direction 17/35). What it needs is *who is holding the
ball*, which for a throw-in is a much smaller question than possession in general.

### Finding the thrower

| rule | attributed |
| :-- | --: |
| nearest player **at the throw-in instant** | useless — ball inside a box in **2 of 36** |
| ball inside **exactly one** box, any 5 fps step in [-2.6,-0.4] s | **25 of 38 = 0.66** |

At the instant Veo timestamps, the ball is already in flight, and the second-nearest
player is a median **24 px** further than the nearest (which is 60 px away) — so
"nearest" is a toss-up in over half of cases. Before the throw the ball is *in the
taker's hands*, which makes containment a clean test rather than a distance threshold.
The ball is detectable there: a candidate exists in [-2.5,-0.5] s at **37 of 38**
throw-ins, though at lower confidence (0.44 against 0.74 after the throw).

### A bug found by looking, not by reasoning

The first shirt band, 0.15–0.45 of box height, **sits on head and shoulders.** Cropping
the boxes and viewing them showed the sampled swatches were grass and hair. Sweeping the
band separates the class medians far better —

| band | Own L median | Opponent L median |
| :-- | --: | --: |
| 0.15–0.45 (original) | 97 | 143 |
| 0.35–0.60 (used) | **84** | **177** |

— and changes held-out accuracy **not at all**. So the band was never the binding
constraint. Attribution rate and sample size are. Worth keeping: the visual check was
right that the descriptor was wrong, and wrong that it was what mattered.

### The number that does not flatter it

Threshold and polarity fitted on period 1:

| | n | correct | accuracy | majority baseline | balanced |
| :-- | --: | --: | --: | --: | --: |
| period 1 (fitted) | 10 | 7 | 0.70 | 0.60 | 0.75 |
| **period 2 (held out)** | 15 | 12 | **0.80** | **0.80** | **0.88** |

Held out it **ties its majority-class baseline** — because the attributable subsample is
12 Own to 3 Opponent while all 38 throw-ins are roughly even. Balanced accuracy 0.88
against 0.50 says the colour is informative (every one of the 3 Opponents correct); n=15
says it cannot be demonstrated that way.

### The control that decides it — and the perverse incentive it exposes

**The team-aware metric rewards guessing over abstaining.** A prediction with no team
scores 0 team-aware; a prediction with a *coin-flip* team is right about half the time.
Assigning random teams to the throw-ins lifts macro from 0.229 to 0.260 while containing
no information at all. So "the primary metric went up" is worthless on its own as
evidence, and `control_team_shuffle.py` now exists to replace the team and keep
everything else:

| team on ThrowIn | ThrowIn F1 | OutOfPlay F1 | macro |
| :-- | --: | --: | --: |
| **shirt colour (shipped)** | **0.178** | 0.147 | **0.274** |
| always Own | 0.133 | 0.147 | 0.267 |
| always Opponent | 0.067 | 0.105 | 0.249 |
| coin flip, 40 trials — mean | 0.105 | 0.132 | 0.260 |
| coin flip — **max** | **0.156** | **0.168** | **0.274** |
| no team at all | 0.000 | 0.052 | 0.229 |

Two verdicts, and one of them is a retraction:

* **ThrowIn team is a result.** 0.178 against a random maximum of 0.156, with **0 of 40**
  trials reaching it.
* **OutOfPlay team by chaining (step 13) is NOT a result.** 0.147 against a random
  maximum of 0.168, with **12 of 40** trials at or above it. The underlying relation is
  still exact (64/64), but our own restart type-and-team predictions are wrong often
  enough that inverting them adds nothing over a coin flip. It is kept and emitted, and
  labelled not a result — the same treatment CornerKick gets.

The macro row is the weakest of the three (0.274 against a random max of 0.274) and that
is not a contradiction: most of the macro movement is the OutOfPlay knock-on, which
benefits from *any* team on the throw-ins it chains off.

**Every future team claim must clear this control, not zero.**

### Where the benchmark stands

| type | n_ref | n_pred | F1 team-agnostic | F1 team-aware | team channel |
| :-- | --: | --: | --: | --: | :-- |
| OutOfPlay | 64 | 127 | 0.356 | 0.147 | chained — **not a result** |
| ThrowIn | 38 | 52 | 0.244 | **0.178** | shirt colour — a result |
| GoalKick | 16 | 13 | 0.276 | **0.276** | defend-end map |
| CornerKick | 9 | 11 | 0.100 | 0.100 | defend-end map; type **not a result** |
| KickOff | 8 | 4 | 0.667 | **0.500** | goal-end lookback |
| Goal | 6 | 3 | 0.444 | **0.444** | goal-end lookback |
| **macro** | | | **0.348** | **0.274** | |

micro-F1 **0.182**, parity 1/14, period-2 macro (0.313) again above period-1 (0.243).
GoalKick and Goal score *identically* team-aware and team-agnostic — every true positive
carries the right side, which no coin flip can do, so those need no control to survive
one.

## D-B step 15 — attribution, which was the actual constraint

Step 14 left throw-in attribution at 25 of 38 and named it, not the colour, as the cap.
Diagnosing the 13 failures settled what kind of problem it was:

| why attribution failed | n |
| :-- | --: |
| **ball outside every player box** | **12** |
| no ball candidate in the window at all | 1 |
| ball inside 2+ boxes (ambiguous) | **0** |

**Not one failure was ambiguity.** And of the 12, seven missed the nearest box edge by
only **1.6–32 px**. Which is exactly what a throw-in looks like: the ball is held *above
the head*, so it lands just outside a person box rather than inside it.

### The fix, and why it is a fraction rather than a number of pixels

Pad each box by a fraction of **its own height**. Players here run 13–298 px tall, so a
fixed pixel tolerance is nothing up close and enormous at the far touchline. Swept by
attribution and **period-1** accuracy, never by period 2:

| pad | attributed | period-1 acc | period-2 (read once) | majority | balanced |
| :-- | --: | --: | --: | --: | --: |
| 0 (strict) | 25/38 = 0.66 | 0.70 | 0.80 | **0.80 (tie)** | 0.88 |
| **0.10 × h (chosen)** | **30/38 = 0.79** | **0.83** | **0.83** | 0.78 | **0.89** |
| 0.15–0.20 × h | 32/38 = 0.84 | 0.77 | 0.68 | 0.74 | 0.72 |
| 0.30 × h | 31/38 = 0.82 | 0.67 | 0.79 | 0.74 | 0.73 |

0.10 h has the best period-1 accuracy in the sweep, so it is selectable without touching
period 2. Larger pads buy attribution and start catching the wrong player — 0.15 h adds
two more throw-ins and loses 15 points of held-out accuracy.

Held out, the channel now **clears** the majority-class baseline (0.83 against 0.78)
where under strict containment it tied it. Teamed predictions rise 38 → 46.

### And the control caught a flaw in the control

With the better attribution, ThrowIn F1 went 0.178 → **0.200** — and the first control
run marked it **not a result**, because the random maximum over 40 trials happened to
reach 0.222. Only 1 trial in 40 did.

"Must beat the best of N random trials" is a bad criterion: it tightens as N grows and it
turns on the tail of a single seed. Replaced with the standard permutation estimate,
`p = (1 + #{random >= real}) / (1 + trials)`, over 200 trials:

| | real | random mean | random p99 | trials ≥ real | p | result |
| :-- | --: | --: | --: | --: | --: | :-- |
| **ThrowIn** | **0.200** | 0.112 | 0.200 | 3/200 | **0.020** | **yes** |
| OutOfPlay (chained) | 0.147 | 0.126 | 0.178 | 51/200 | **0.259** | **no** |
| macro | 0.278 | 0.260 | 0.281 | 4/200 | **0.025** | yes |

So the improved attribution turns ThrowIn team into a result at p = 0.02, and the
step-13 retraction is confirmed far more firmly than before — p = 0.26 is not close.

### Where the benchmark stands

| type | n_ref | n_pred | F1 team-agnostic | F1 team-aware | team channel |
| :-- | --: | --: | --: | --: | :-- |
| OutOfPlay | 64 | 127 | 0.356 | 0.147 | chained — **not a result** (p = 0.26) |
| ThrowIn | 38 | 52 | 0.244 | **0.200** | shirt colour — **a result** (p = 0.02) |
| GoalKick | 16 | 13 | 0.276 | **0.276** | defend-end map |
| CornerKick | 9 | 11 | 0.100 | 0.100 | defend-end map; type **not a result** |
| KickOff | 8 | 4 | 0.667 | **0.500** | goal-end lookback |
| Goal | 6 | 3 | 0.444 | **0.444** | goal-end lookback |
| **macro** | | | **0.348** | **0.278** | p = 0.025 |

micro-F1 **0.188**, parity 1/14, period-2 macro **0.320** against period-1 0.243.

## D-B step 16 — OutOfPlay team: three routes, all measured dead

OutOfPlay is the largest attempted type (64 events) and the last one holding a team-aware
score that is statistically nothing. The physical rule is simple — *whoever last touched
the ball put it out* — and the thrower-shirt machinery from step 15 looked like it should
transfer directly. It does not. Three routes were tried and all three fail on held-out
data.

Player detections for this: 960 frames at 5 fps across [-3.2,-0.2] s before every true
OutOfPlay, 24,519 persons, 35 s of GPU.

### Route 1 — chain off our own restart predictions

The relation is **exact in the ground truth**: an OutOfPlay's side is always the opposite
of the restart's, 64/64. Our own predictions destroy it. Sweeping the pairing window,
scored only on OutOfPlay predictions that are true positives:

| window | teamed | TPs teamed | period 1 | period 2 |
| --: | --: | --: | --: | --: |
| 10 s | 23 | 6 | 1/4 = 0.25 | 1/2 = 0.50 |
| 15 s | 39 | 10 | 4/7 = 0.57 | 2/3 = 0.67 |
| 30 s | 67 | 18 | 5/9 = 0.56 | 6/9 = 0.67 |
| 60 s | 97 | 24 | 7/13 = 0.54 | 7/11 = 0.64 |
| **ceiling, true restarts and true teams** | | | | **64/64 = 1.00** |

A coin flip at every window. The ceiling is 1.00, so the entire loss is that *the first
teamed restart prediction within the window is usually not the restart that followed this
OutOfPlay* — restart precision is 0.21–0.31, so the pairing is mostly noise. Tightening
the window to the median 17 s gap does not help; it just teams fewer.

### Route 2 — the last player contact before the ball crosses

Scan backwards for the latest frame where the ball sits inside exactly one padded box:

| rule | attributed | period 1 | period 2 | majority |
| :-- | --: | --: | --: | --: |
| last contact, pad 0.20 h | 60/64 = 0.94 | **0.70** | 0.64 | **0.64 (tie)** |
| confidence-weighted vote, pad 0.10 h | 57/64 = 0.89 | 0.69 | 0.65 | 0.65 (tie) |

Attribution is *high* — 0.94, far better than the throw-in's 0.79 — and the team is a
coin flip anyway. That combination is the tell: the ball is being associated to plenty of
players, just not the right one.

### Route 3 — the player at the strike frame

The physically correct cue: find the frame of largest ball acceleration in the window —
the kick that sent it out — and take the nearest player. Selected on period-1 accuracy,
as the protocol requires:

| pad, max distance | attributed | period 1 | period 2 | majority |
| :-- | --: | --: | --: | --: |
| **0.00 h, 1.0 h (best period-1)** | 0.58 | **0.71** | **0.45** | 0.60 |
| **0.10 h, 0.6 h (best period-1)** | 0.59 | **0.71** | **0.48** | 0.67 |
| 0.00 h, 0.3 h | 0.36 | 0.64 | 0.75 | 0.67 |
| 0.10 h, 1.0 h | 0.62 | 0.67 | 0.73 | 0.64 |

The two cells the protocol selects score **below their majority baseline** on held-out
data. Two other cells look good on period 2 — and they are only identifiable as good in
hindsight, which is exactly what the period split exists to stop.

### Why the throw-in worked and this cannot

**The throw-in has a stationary ball held in a player's hands for one to two seconds** —
a temporally extended, unambiguous association, which is why containment works there and
why padding the box by 0.10 h was enough to lift attribution to 0.79.

An out-of-play's last touch is **instantaneous**. At 5 fps a struck ball moves ~50 px
between frames, so the contact frame may not be sampled at all; on its way out the ball
passes near many players, which is why route 2 attributes 94 % of events to *somebody*;
and the last touch is often a deflection, ambiguous even to a human annotator.

**The lesson generalises past this type: this machinery works where the ball is held, not
where it is struck.** Anything needing the toucher of a moving ball needs either a much
higher frame rate or real multi-object tracking with possession — not this.

### What this means for the headline

The chained OutOfPlay team channel stays in the output, declared and labelled, exactly as
CornerKick does. But it fails its control at **p = 0.26**, so the conservative reading of
the primary metric zeroes it:

| macro-F1, team-aware | value |
| :-- | --: |
| as reported | **0.278** |
| **with every channel that fails its control zeroed** | **0.253** |

**0.024 of the headline rests on a channel indistinguishable from guessing.** Quote the
conservative number where one number is wanted.
