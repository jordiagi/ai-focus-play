#!/usr/bin/env python3
"""D-A step 3b — calibrate the panorama by anchoring on the CENTRE CIRCLE.

`calibrate_panorama.py` searches all 8 parameters and does not converge: the camera
height runs to its bound, several restarts land on different local optima, and the
plane normal is weakly determined because great-circle RANSAC recovers only three or
four distinct straight lines.

The centre circle fixes exactly what is weak. It is a circle of KNOWN radius (9.15 m,
fixed by the Laws at every pitch size), it is crisp and unambiguous in the line map,
and a circle of known radius seen by a calibrated camera determines the plane pose.
So it pins the ground normal, the camera height, and the pitch centre in one solve --
leaving only the in-plane rotation (from the halfway line) and the pitch dimensions.

    circle  -> alpha, beta (ground normal), h (camera height), tx, ty (pitch centre)
    halfway -> gamma
    search  -> L, W only

Two degeneracies had to be removed to make this work, both found by unit-testing
against synthetic ground truth rather than by staring at the output:

  * Letting h float gives a TRIVIAL global optimum at h=0, where every ray collapses
    to the camera centre and any centre at distance r fits with exactly zero residual.
    Both scipy optimisers drove straight to it. Here h is fixed at 1 and the radius
    floats instead; the true height is then 9.15/rho.
  * The parameters span 0.05 to 200 in magnitude, so the solve needs explicit x_scale.

Reports the same honest metric as `../pitch/score_alignment.py`: the fraction of
projected model line landing on a detected line pixel.
"""
import argparse, sys, json, math
from pathlib import Path

import numpy as np

R_CENTRE = 9.15


def rays(xs, ys, scale, x0, y0):
    th = (xs + x0) / scale
    psi = math.pi - (ys + y0) / scale
    D = np.stack([np.sin(psi) * np.sin(th), np.cos(psi), np.sin(psi) * np.cos(th)], 1)
    return D / np.linalg.norm(D, axis=1, keepdims=True)


def great_circles(D, rng, n_max, tol, min_inl):
    out, rem = [], np.ones(len(D), bool)
    for _ in range(n_max):
        idx = np.nonzero(rem)[0]
        if len(idx) < min_inl:
            break
        Dr = D[idx]
        bc, bm = 0, None
        for _ in range(2500):
            i1, i2 = rng.integers(0, len(Dr), 2)
            m = np.cross(Dr[i1], Dr[i2])
            nm = np.linalg.norm(m)
            if nm < 1e-6:
                continue
            m = m / nm
            c = int((np.abs(Dr @ m) < tol).sum())
            if c > bc:
                bc, bm = c, m
        if bm is None or bc < min_inl:
            break
        inl = np.abs(Dr @ bm) < tol
        _, _, vt = np.linalg.svd(Dr[inl])
        m = vt[-1] / np.linalg.norm(vt[-1])
        inl = np.abs(Dr @ m) < tol
        out.append({"m": m, "n": int(inl.sum()), "idx": idx[inl]})
        rem[idx[inl]] = False
    return out, rem


def fit_circle_pose(D, init, lo, hi):
    from scipy.optimize import least_squares
    from calibrate_panorama import normals, basis

    def resid(p):
        a, b, cx, cy, rho = p
        nn = normals(np.array([a]), np.array([b]))[0]
        E1, E2 = basis(nn[None, :])
        E1, E2 = E1[0], E2[0]
        den = D @ nn
        den = np.where(den > -1e-9, -1e-9, den)      # h fixed at 1
        Q = D * (-1.0 / den)[:, None]
        return np.sqrt((Q @ E1 - cx) ** 2 + (Q @ E2 - cy) ** 2) - rho

    return least_squares(resid, np.clip(init, lo, hi), bounds=(lo, hi),
                         x_scale=np.array([0.05, 0.05, 2.0, 2.0, 0.5]), max_nfev=8000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panorama", required=True)
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--line-map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-overlay", default=None)
    ap.add_argument("--out-circle", default=None)
    ap.add_argument("--thresh", type=float, default=0.30)
    ap.add_argument("--circle-tol", type=float, default=0.0022)
    ap.add_argument("--hit-px", type=float, default=3.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    import cv2, sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from scipy.optimize import minimize
    from calibrate_panorama import normals, basis, project, pitch_model

    C = json.loads(Path(a.cameras).read_text())
    scale, (x0, y0) = float(C["scale"]), C["origin"]
    bgr = cv2.imread(a.panorama)
    Ch, Cw = bgr.shape[:2]
    lm = cv2.imread(a.line_map, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0

    ys, xs = np.nonzero(lm > a.thresh)
    D = rays(xs.astype(float), ys.astype(float), scale, x0, y0)
    rng = np.random.default_rng(a.seed)
    lines, rem = great_circles(D, rng, 14, a.circle_tol, 250)

    # --- ellipse candidates from what is NOT a straight line ---
    res = np.zeros((Ch, Cw), np.uint8)
    res[ys[rem], xs[rem]] = 255
    res = cv2.morphologyEx(res, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    nl, lab, st, _ = cv2.connectedComponentsWithStats(res, 8)
    cands = []
    for i in range(1, nl):
        if st[i, cv2.CC_STAT_AREA] < 250:
            continue
        pts = np.column_stack(np.nonzero(lab == i)[::-1]).astype(np.float32)
        if len(pts) < 50:
            continue
        try:
            (ex, ey), (MA, ma), angd = cv2.fitEllipse(pts)
        except cv2.error:
            continue
        if MA < 10 or ma < 10:
            continue
        # Iterate fit -> re-collect -> refit. The straight-line removal eats the
        # flatter parts of the circle, so the first fit comes from a partial arc and
        # is biased; collecting against that biased ellipse then misses the rest.
        # Two or three rounds grow it to the full circle.
        sel = None
        for it, band in enumerate((0.06, 0.035, 0.022, 0.022)):
            cs, sn = math.cos(math.radians(angd)), math.sin(math.radians(angd))
            dx, dy = xs - ex, ys - ey
            xr, yr = cs * dx + sn * dy, -sn * dx + cs * dy
            rr = np.sqrt((xr / (MA / 2)) ** 2 + (yr / (ma / 2)) ** 2)
            sel = np.abs(rr - 1.0) < band
            if sel.sum() < 60:
                break
            pts2 = np.stack([xs[sel], ys[sel]], 1).astype(np.float32)
            try:
                (ex, ey), (MA, ma), angd = cv2.fitEllipse(pts2)
            except cv2.error:
                break
            if MA < 10 or ma < 10:
                break
        if sel is None or sel.sum() < 300:
            continue
        cs, sn = math.cos(math.radians(angd)), math.sin(math.radians(angd))
        dx, dy = xs - ex, ys - ey
        xr, yr = cs * dx + sn * dy, -sn * dx + cs * dy
        rr = np.sqrt((xr / (MA / 2)) ** 2 + (yr / (ma / 2)) ** 2)
        sel = np.abs(rr - 1.0) < 0.022
        if sel.sum() < 300:
            continue
        cov = len(np.unique((np.degrees(np.arctan2(yr[sel], xr[sel])) // 10
                             ).astype(int))) / 36.0
        cands.append({"ellipse": ((ex, ey), (MA, ma), angd), "sel": sel,
                      "n": int(sel.sum()), "cov": float(cov)})
    cands.sort(key=lambda z: -(z["cov"] * math.log(z["n"] + 1)))
    if not cands:
        print(json.dumps({"error": "no ellipse candidate found"}, indent=1))
        return 5

    lo5 = np.array([-0.5, -0.5, -60., -60., 0.05])
    hi5 = np.array([0.5, 0.5, 60., 60., 60.])
    F = 8
    gh, gw = Ch // F + 1, Cw // F + 1
    dg = np.zeros((gh, gw), bool)
    dg[ys // F, xs // F] = True
    n_det = int(dg.sum())

    def bilinear(img, u, v):
        u0 = np.clip(np.floor(u), 0, Cw - 2).astype(np.int32)
        v0 = np.clip(np.floor(v), 0, Ch - 2).astype(np.int32)
        du, dv = np.clip(u - u0, 0, 1), np.clip(v - v0, 0, 1)
        return ((img[v0, u0] * (1 - du) + img[v0, u0 + 1] * du) * (1 - dv) +
                (img[v0 + 1, u0] * (1 - du) + img[v0 + 1, u0 + 1] * du) * dv)

    _mc = {}

    def model_for(L, W, fine=False):
        k = (round(L, 1), round(W, 1), fine)
        if k not in _mc:
            _mc[k] = pitch_model(L, W, 40, 80) if fine else pitch_model(L, W, 16, 36)
        return _mc[k]

    LO = np.array([-0.5, -0.5, 1.0, 0.0, -150., -150., 80., 45.])
    HI = np.array([0.5, 0.5, 40.0, 2 * math.pi, 150., 150., 120., 80.])

    def score(p, fine=False):
        p = np.clip(np.asarray(p, float), LO, HI)
        mdl = model_for(p[6], p[7], fine)
        u, v, ok = project(p[None, :], mdl, scale, x0, y0, Cw, Ch)
        u, v, ok = u[0], v[0], ok[0]
        if ok.sum() < 0.25 * len(mdl):
            return 0.0
        prec = float((bilinear(lm, u, v) * ok).mean())
        ui = np.clip(u, 0, Cw - 1).astype(np.int32)
        vi = np.clip(v, 0, Ch - 1).astype(np.int32)
        hit = np.zeros((gh, gw), bool)
        hit[vi[ok] // F, ui[ok] // F] = True
        rec = float((hit & dg).sum()) / max(n_det, 1)
        return prec * (0.25 + rec)

    best = (None, -1.0, None)
    tried = []
    for ci, cand in enumerate(cands[:6]):
        Dc = D[cand["sel"]]
        sols = []
        for init in ([0, 0, 0, -4, 1.5], [0.2, 0.2, 3, -8, 3], [0, 0, 2, -2, 1],
                     [-0.15, 0.1, -3, -6, 2], [0.1, -0.1, 6, -10, 4]):
            try:
                s = fit_circle_pose(Dc, np.array(init, float), lo5, hi5)
            except Exception:
                continue
            sols.append(s)
        if not sols:
            continue
        s = min(sols, key=lambda z: z.cost)
        al, be, cx1, cy1, rho = s.x
        if rho <= 1e-3:
            continue
        h = R_CENTRE / rho
        tx, ty = cx1 * h, cy1 * h
        n = normals(np.array([al]), np.array([be]))[0]
        e1, e2 = basis(n[None, :])
        e1, e2 = e1[0], e2[0]
        dc = -h * n + tx * e1 + ty * e2
        dc = dc / np.linalg.norm(dc)
        tried.append({"cand": ci, "cov": cand["cov"], "n_px": cand["n"],
                      "circle_cost": float(s.cost), "h_m": round(float(h), 3),
                      "residual_m": round(float(np.sqrt(2 * s.cost / len(Dc))) * h, 4)})
        # the halfway line must pass through the pitch centre
        hl = sorted(lines, key=lambda L_: abs(L_["m"] @ dc))
        for m_half in [L_["m"] for L_ in hl[:3]]:
            dh = np.cross(m_half, n)
            if np.linalg.norm(dh) < 1e-6:
                continue
            dh /= np.linalg.norm(dh)
            for sgn in (1, -1):
                t = np.cross(n, sgn * dh)
                t /= np.linalg.norm(t)
                ga = math.atan2(t @ e2, t @ e1) % (2 * math.pi)
                sv = np.cross(n, t)
                sv /= np.linalg.norm(sv)
                # With the pose pinned by the circle, every other detected line has a
                # readable in-plane offset from the pitch centre. Read L and W off
                # those instead of grid-searching: a touchline sits at W/2, a goal
                # line at L/2, and the halfway line lands at 0 (which is the check
                # that the centre is right).
                c_t = tx * (t @ e1) + ty * (t @ e2)
                c_s = tx * (sv @ e1) + ty * (sv @ e2)
                Wc, Lc = [], []
                for L_ in lines:
                    m = L_["m"]
                    dd = np.cross(m, n)
                    nr = np.linalg.norm(dd)
                    if nr < 1e-9:
                        continue
                    dd /= nr
                    angd2 = math.degrees(math.atan2(dd @ sv, dd @ t)) % 180
                    par_t = min(angd2, 180 - angd2) < 25
                    perp = sv if par_t else t
                    den = m @ perp
                    if abs(den) < 1e-6:
                        continue
                    off = h * (m @ n) / den - (c_s if par_t else c_t)
                    if par_t and 25.0 < abs(off) < 45.0:
                        Wc.append((2 * abs(off), L_["n"]))
                    if (not par_t) and 35.0 < abs(off) < 60.0:
                        Lc.append((2 * abs(off), L_["n"]))
                Ws = sorted({round(w, 1) for w, _ in Wc}) or [64.0, 68.0, 70.0]
                Ls = sorted({round(l, 1) for l, _ in Lc}) or [100.0, 105.0]
                Ws = [w for w in Ws if LO[7] <= w <= HI[7]] or [68.0]
                Ls = [l for l in Ls if LO[6] <= l <= HI[6]] or [105.0]
                for L in Ls:
                    for W in Ws:
                        p_ = np.array([al, be, h, ga, tx, ty, L, W])
                        sc = score(p_)
                        if sc > best[1]:
                            best = (np.clip(p_, LO, HI), sc, ci)
    if best[0] is None:
        print(json.dumps({"error": "no viable circle hypothesis",
                          "candidates": len(cands), "tried": tried}, indent=1))
        return 5

    p = best[0].copy()
    for _ in range(3):
        r = minimize(lambda q: -score(q), p, method="Nelder-Mead",
                     options={"maxiter": 4000, "xatol": 1e-5, "fatol": 1e-9})
        p = np.clip(r.x, LO, HI)
    sc = score(p, fine=True)

    fine = model_for(p[6], p[7], True)
    det = (lm > a.thresh).astype(np.uint8)
    dist = cv2.distanceTransform(1 - det, cv2.DIST_L2, 3)
    u, v, ok = project(p[None, :], fine, scale, x0, y0, Cw, Ch)
    ui = np.clip(u, 0, Cw - 1).astype(np.int32)
    vi = np.clip(v, 0, Ch - 1).astype(np.int32)
    d = dist[vi, ui][0]
    okf = ok[0]
    on = int(((d <= a.hit_px) & okf).sum())
    hit = np.zeros((gh, gw), bool)
    hit[vi[0][okf] // F, ui[0][okf] // F] = True

    doc = {
        "job": "D-A step 3b: centre-circle-anchored pitch calibration",
        "command": " ".join(sys.argv),
        "params": {"alpha_rad": round(float(p[0]), 5), "beta_rad": round(float(p[1]), 5),
                   "camera_height_m": round(float(p[2]), 3),
                   "gamma_rad": round(float(p[3]), 5),
                   "tx_m": round(float(p[4]), 3), "ty_m": round(float(p[5]), 3),
                   "pitch_L_m": round(float(p[6]), 2), "pitch_W_m": round(float(p[7]), 2)},
        "on_bounds": [k for k, (lo_, hi_, val) in
                      zip(["alpha", "beta", "h", "gamma", "tx", "ty", "L", "W"],
                          zip(LO, HI, p)) if abs(val - lo_) < 1e-6 or abs(val - hi_) < 1e-6],
        "score": round(float(sc), 5),
        "circle_candidates": len(cands), "circle_fits": tried,
        "alignment": {
            "model_points": int(len(fine)), "inside_panorama": int(okf.sum()),
            "on_line_within_3px": on,
            "fraction_of_visible_on_line": round(on / max(int(okf.sum()), 1), 4),
            "median_dist_px": round(float(np.median(d[okf])), 2),
            "recall_of_detected_line_cells": round(float((hit & dg).sum()) / max(n_det, 1), 4),
        },
        "comparable_to": "PnLCalib scored 0.29 median line-alignment on single frames",
    }
    if a.out_overlay:
        vis = (bgr * 0.45).astype(np.uint8)
        vis[:, :, 2] = np.maximum(vis[:, :, 2], (np.clip(lm * 2.5, 0, 1) * 220).astype(np.uint8))
        for k in range(len(fine)):
            if okf[k]:
                cv2.circle(vis, (int(ui[0, k]), int(vi[0, k])), 2, (0, 255, 255), -1)
        cv2.imwrite(a.out_overlay, vis)
    if a.out_circle:
        vis2 = np.zeros((Ch, Cw), np.uint8)
        vis2[ys[cands[best[2]]["sel"]], xs[cands[best[2]]["sel"]]] = 255
        cv2.imwrite(a.out_circle, vis2)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
