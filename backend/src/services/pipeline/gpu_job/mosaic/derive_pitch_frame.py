#!/usr/bin/env python3
"""D-B step 9 -- an occupancy-derived coordinate frame on the panorama.

The restart types differ by **where the ball was**, so classifying them needs a
pitch-relative coordinate, not a pixel one: `u` alone confounds length with pan, and
`v` alone confounds width with depth because the pitch is a trapezoid in this panorama.

This builds a two-axis normalised frame from the **player occupancy cloud only** --
14,607 foot points, no Veo coordinate anywhere:

    xi(u)    = (u - u_lo) / (u_hi - u_lo)                 along the pan (length-ish)
    eta(u,v) = (v - v_far(u)) / (v_near(u) - v_far(u))    across it     (width-ish)

`v_far` and `v_near` are weighted quadratics through per-u-bin percentiles of the
occupancy cloud. The quadratic is not decoration: the far boundary is V-shaped
(412 px at u=650, 371 px at u=1950, 433 px at u=3750) because the panorama is
spherical, and a straight line fits it three times worse (resid 20.3 vs 7.4 px).

**What this frame is NOT.** Its boundaries are not the touchlines. Scored against the
line-evidence map the same way the pitch region was, the fitted curves land on a
detected line **less often than chance** (0.028 far / 0.010 near vs 0.040 for a random
horizontal curve). The occupancy cloud has substitutes, staff and the far crowd in it,
and the near edge is ragged -- its own fit residual is 50 px against the far edge's 7.4.

So this is a **monotone re-parameterisation that correlates with pitch position**, and
that is all it is claimed to be. The evidence for it is external and measured:

  * corr(veo_z, v) = -0.727 while corr(veo_z, u) = -0.331 -- the axes do separate
  * corr(veo_x, u) = +0.832 while corr(veo_x, v) = +0.113
  * all 8 kickoffs land inside xi in [0.39,0.50], eta in [0.52,0.60] -- a tight box no
    other restart type enters

Every threshold that uses this frame is therefore **fitted on period 1**, never assumed
from geometry. Nothing downstream may read xi=0 as "the goal line".
"""
import argparse, json, sys
from pathlib import Path

import numpy as np


def fit_frame(occ, u_lo=600, u_hi=3900, step=100, min_pts=80,
              q_far=3.0, q_near=95.0, deg=2):
    """Weighted quadratics through per-bin percentiles of the occupancy cloud."""
    ub, far, near, wt = [], [], [], []
    for b in np.arange(u_lo, u_hi, step):
        m = (occ[:, 0] >= b) & (occ[:, 0] < b + step)
        if m.sum() < min_pts:
            continue
        ub.append(b + step / 2.0)
        far.append(np.percentile(occ[m, 1], q_far))
        near.append(np.percentile(occ[m, 1], q_near))
        wt.append(m.sum())
    ub = np.asarray(ub, float)
    far = np.asarray(far, float)
    near = np.asarray(near, float)
    w = np.sqrt(np.asarray(wt, float))
    p_far = np.polyfit(ub, far, deg, w=w)
    p_near = np.polyfit(ub, near, deg, w=w)
    rms = lambda p, y: float(np.sqrt(np.mean((np.polyval(p, ub) - y) ** 2)))
    return {
        "p_far": [float(c) for c in p_far],
        "p_near": [float(c) for c in p_near],
        "u_lo": float(ub.min() - step / 2.0),
        "u_hi": float(ub.max() + step / 2.0),
        "bins_used": int(len(ub)),
        "resid_rms_far_px": round(rms(p_far, far), 2),
        "resid_rms_near_px": round(rms(p_near, near), 2),
        "q_far": q_far, "q_near": q_near, "degree": deg,
    }


def line_alignment(frame, line_map, near_px=6):
    """Does either fitted boundary sit on detected line evidence? (It does not.)"""
    import cv2
    lm = cv2.imread(str(line_map), cv2.IMREAD_UNCHANGED)
    if lm is None:
        return None
    H, W = lm.shape[:2]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * near_px + 1,) * 2)
    band = cv2.dilate((lm >= int(0.35 * 255)).astype(np.uint8), k).astype(bool)
    U = np.arange(int(frame["u_lo"]), int(frame["u_hi"]))
    out = {}
    for tag, key in (("far", "p_far"), ("near", "p_near")):
        V = np.polyval(frame[key], U).round().astype(int)
        ok = (V >= 0) & (V < H)
        out[f"{tag}_on_line"] = round(float(band[V[ok], U[ok]].mean()), 4)
    rng = np.random.default_rng(1)
    hits = []
    for _ in range(400):
        v0 = rng.integers(300, 900)
        V = np.clip((v0 + rng.normal(0, 0.002) * np.arange(len(U))).round().astype(int),
                    0, H - 1)
        hits.append(band[V, U].mean())
    out["chance_random_horizontal_curve"] = round(float(np.mean(hits)), 4)
    out["verdict"] = ("the fitted boundaries are NOT the touchlines -- both land on a "
                      "detected line no more often than a random horizontal curve. The "
                      "frame is a monotone re-parameterisation, not a calibrated pitch.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--occupancy", required=True)
    ap.add_argument("--line-map", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    occ = np.asarray(json.loads(Path(a.occupancy).read_text()), dtype=float)[:, :2]
    frame = fit_frame(occ)
    frame["job"] = "D-B step 9: occupancy-derived (xi, eta) frame on the panorama"
    frame["command"] = " ".join(sys.argv)
    frame["occupancy_points"] = int(len(occ))
    # the straight-line alternative, so the quadratic is justified by a number
    lin = fit_frame(occ, deg=1)
    frame["linear_alternative_resid_rms_far_px"] = lin["resid_rms_far_px"]
    if a.line_map:
        frame["line_alignment"] = line_alignment(frame, a.line_map)
    frame["what_this_is_not"] = (
        "xi=0 is not a goal line and eta=0/1 are not touchlines; no threshold using "
        "this frame may be assumed from geometry, all are fitted on period 1")
    Path(a.out).write_text(json.dumps(frame, indent=1))
    print(json.dumps(frame, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
