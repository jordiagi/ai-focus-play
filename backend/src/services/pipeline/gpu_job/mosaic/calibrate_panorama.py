#!/usr/bin/env python3
"""D-A step 3 — fit the pitch to the panorama in RAY space.

Why not a homography. The reconstructed panorama spans 125 degrees, so no pinhole
image can contain this pitch and **no single homography maps the panorama to the pitch
plane**. That is exactly why Veo ships a panorama and calibrates with known intrinsics
instead of fitting one. Every earlier attempt in this repo assumed a homography, and
that assumption was wrong before any of the tuning started.

The right object is the ray. `build_panorama.py` left us a spherical panorama whose
every pixel IS a direction:

    theta = (u + x0)/scale, psi = pi - (v + y0)/scale
    d     = (sin psi sin theta, cos psi, sin psi cos theta)      # +y is DOWN

(verified against OpenCV's own PyRotationWarper.warpPoint to the pixel.) The camera sits
at the origin, the pitch is the plane those rays strike, and the whole calibration is
then 8 numbers:

    alpha, beta   ground-plane normal (tilt, roll) -- 2
    h             camera height above the pitch, metres -- 1
    gamma         pitch rotation within the plane -- 1
    tx, ty        pitch centre relative to the camera's foot point -- 2
    L, W          pitch length and width (a U16 field is NOT 105x68) -- 2

Fitting is done against a soft evidence image, not a thresholded mask: line width
varies from many pixels near the camera to under one pixel at the far touchline, so a
single threshold either loses the far lines or floods on the near ones. The response is
a multi-scale top-hat, locally contrast-normalised, suppressed where the pixel is
saturated (the adjacent field's lines are BLUE, so they are excluded by construction)
and zeroed outside the automatically-derived grass region. No hand annotation anywhere
-- the standing instruction is that zones must be derived, not drawn.

Search is coarse-to-fine random restarts then Nelder-Mead, because the objective is not
convex and a single local solve from a guess is how the earlier attempts fooled
themselves.

Honest scoring: the headline number is the fraction of projected model line that lands
on a real detected line pixel. That is the same metric `../pitch/score_alignment.py`
used, so the result is directly comparable with PnLCalib's 0.29 median / 26% well-aligned.
"""
import argparse, json, math
from pathlib import Path

import numpy as np


def pitch_model(L, W, n_per_line=24, circle_pts=48):
    """Markings at their true metric sizes for a pitch of L x W.

    The first version scaled a 105x68 template, which silently stretched the penalty
    areas too. Their sizes are fixed by the Laws (16.5 deep, 40.32 wide, 5.5/18.32 for
    the goal area, 9.15 radius) while L and W are not -- and that difference is the
    ONLY thing that breaks the scale degeneracy, because a pure similarity of the whole
    pitch reprojects identically. Getting this wrong removes the information the fit
    needs to pin absolute size.
    """
    segs = []
    hl, hw = L / 2, W / 2
    for y in (-hw, hw):
        segs.append(((-hl, y), (hl, y)))
    for x in (-hl, hl):
        segs.append(((x, -hw), (x, hw)))
    segs.append(((0, -hw), (0, hw)))
    for sgn in (-1, 1):
        gx = sgn * hl
        segs.append(((gx - sgn * 16.5, -20.16), (gx - sgn * 16.5, 20.16)))
        segs.append(((gx, -20.16), (gx - sgn * 16.5, -20.16)))
        segs.append(((gx, 20.16), (gx - sgn * 16.5, 20.16)))
        segs.append(((gx - sgn * 5.5, -9.16), (gx - sgn * 5.5, 9.16)))
        segs.append(((gx, -9.16), (gx - sgn * 5.5, -9.16)))
        segs.append(((gx, 9.16), (gx - sgn * 5.5, 9.16)))
    pts = []
    for (ax, ay), (bx, by) in segs:
        t = np.linspace(0, 1, n_per_line)
        pts.append(np.stack([ax + (bx - ax) * t, ay + (by - ay) * t], 1))
    aa = np.linspace(0, 2 * math.pi, circle_pts, endpoint=False)
    pts.append(np.stack([9.15 * np.cos(aa), 9.15 * np.sin(aa)], 1))
    for sgn in (-1, 1):
        cx = sgn * (hl - 11.0)
        bb = np.linspace(0, 2 * math.pi, 60)
        q = np.stack([cx + 9.15 * np.cos(bb), 9.15 * np.sin(bb)], 1)
        pts.append(q[np.abs(q[:, 0]) > hl - 16.5])
    return np.concatenate(pts, 0)


def normals(alpha, beta):
    """Ground normal, pointing UP (from pitch toward camera). Nominal is (0,-1,0)
    because +y is down in the spherical panorama frame."""
    ca, sa = np.cos(alpha), np.sin(alpha)
    cb, sb = np.cos(beta), np.sin(beta)
    n = np.stack([sb * ca, -ca * cb, sa], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def basis(n):
    ref = np.zeros_like(n)
    ref[..., 2] = 1.0
    bad = np.abs(n[..., 2]) > 0.9
    ref[bad] = 0.0
    ref[bad, 0] = 1.0
    e1 = np.cross(n, ref)
    e1 /= np.linalg.norm(e1, axis=-1, keepdims=True)
    e2 = np.cross(n, e1)
    return e1, e2


def project(params, model, scale, x0, y0, Cw, Ch):
    """params (S,8) x model (P,2) -> pixel coords (S,P,2) and validity (S,P)."""
    al, be, h, ga, tx, ty = [params[:, i] for i in range(6)]
    n = normals(al, be)
    e1, e2 = basis(n)
    cg, sg = np.cos(ga)[:, None], np.sin(ga)[:, None]
    X = model[None, :, 0] + np.zeros((len(params), 1))
    Y = model[None, :, 1] + np.zeros((len(params), 1))
    Xr, Yr = X * cg - Y * sg, X * sg + Y * cg
    P = (-h[:, None, None] * n[:, None, :]
         + (Xr + tx[:, None])[:, :, None] * e1[:, None, :]
         + (Yr + ty[:, None])[:, :, None] * e2[:, None, :])
    nrm = np.linalg.norm(P, axis=-1)
    nrm = np.where(nrm < 1e-9, 1e-9, nrm)
    psi = np.arccos(np.clip(P[..., 1] / nrm, -1, 1))
    th = np.arctan2(P[..., 0], P[..., 2])
    u = scale * th - x0
    v = scale * (math.pi - psi) - y0
    ok = (u >= 0) & (u < Cw - 1) & (v >= 0) & (v < Ch - 1)
    return u, v, ok


def score_batch(params, model, resp, scale, x0, y0, min_span=0.55, min_vspan=0.22):
    """Mean line evidence under the projected model, gated on the model actually
    spanning the panorama.

    The gate is not a tuning knob, it is what makes the objective non-degenerate. The
    first run without it returned 0.88 "alignment" by collapsing the whole pitch into a
    sliver lying along the tree line, with every parameter pinned at a bound. The
    panorama was built from frames that follow the ball over the entire pitch, so a
    pitch occupying less than half its width contradicts how the image was made.
    """
    Ch, Cw = resp.shape
    u, v, ok = project(params, model, scale, x0, y0, Cw, Ch)
    ui = np.clip(u, 0, Cw - 1).astype(np.int32)
    vi = np.clip(v, 0, Ch - 1).astype(np.int32)
    val = (resp[vi, ui] * ok).mean(axis=1)
    gate = (((u.max(1) - u.min(1)) >= min_span * Cw) &
            ((v.max(1) - v.min(1)) >= min_vspan * Ch))
    return val * gate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panorama", required=True)
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-overlay", default=None)
    ap.add_argument("--out-response", default=None)
    ap.add_argument("--response-image", default=None,
                    help="precomputed line map from build_line_map.py (strongly "
                         "preferred: the RGB median composite loses thin lines)")
    ap.add_argument("--n-circles", type=int, default=8)
    ap.add_argument("--circle-tol", type=float, default=0.0025)
    ap.add_argument("--det-thresh", type=float, default=0.35)
    ap.add_argument("--refine", type=int, default=25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hit-px", type=float, default=3.0,
                    help="a projected point counts as ON a line within this distance")
    a = ap.parse_args()

    import cv2
    from scipy.optimize import minimize

    C = json.loads(Path(a.cameras).read_text())
    scale = float(C["scale"])
    x0, y0 = C["origin"]
    bgr = cv2.imread(a.panorama)
    Ch, Cw = bgr.shape[:2]

    # ---- evidence image ----
    if a.response_image:
        resp = cv2.imread(a.response_image, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        if resp.shape != (Ch, Cw):
            raise SystemExit(f"response {resp.shape} does not match panorama {(Ch, Cw)}")
    else:
        i16 = bgr.astype(np.int16)
        B, G, R = i16[:, :, 0], i16[:, :, 1], i16[:, :, 2]
        grn = G - (R + B) // 2
        gray0 = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        mu = cv2.boxFilter(gray0, -1, (17, 17))
        sd = np.sqrt(np.maximum(cv2.boxFilter(gray0 * gray0, -1, (17, 17)) - mu * mu, 0))
        grass = ((grn > 25) & (sd < 12) & (bgr.max(axis=2) > 40)).astype(np.uint8)
        grass = cv2.morphologyEx(grass, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
        grass = cv2.morphologyEx(grass, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
        nl, lab, st, _ = cv2.connectedComponentsWithStats(grass, 8)
        region = (lab == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
        region = cv2.morphologyEx(region, cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
        col = region.cumsum(axis=0)
        first = np.argmax((col >= 30), axis=0)
        rows = np.arange(Ch)[:, None]
        region = ((region > 0) & (rows >= first[None, :])).astype(np.uint8)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        resp = np.zeros_like(gray)
        for k in (7, 13, 21, 31):
            t = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT,
                                 cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
            resp = np.maximum(resp, t)
        resp = resp / (cv2.GaussianBlur(resp, (0, 0), 25) + 6.0)
        sat = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1].astype(np.float32)
        resp *= np.clip((110.0 - sat) / 60.0, 0, 1)
        resp *= region
        resp = np.clip(resp, 0, np.percentile(resp[region > 0], 99.9))
        resp /= max(resp.max(), 1e-9)
    if a.out_response:
        cv2.imwrite(a.out_response, (np.clip(resp * 3, 0, 1) * 255).astype(np.uint8))

    # ---- great circles: a straight ground line is a great circle in ray space ----
    # Blind search over 8 parameters does not work -- it returned 0.88 "alignment" by
    # collapsing the pitch onto the tree line. But the geometry is nearly closed-form.
    # Two PARALLEL ground lines (the touchlines) intersect at their vanishing direction
    # t; a perpendicular line (halfway) then gives s = m_half x t; and the ground normal
    # is n = t x s. Only the overall scale is left, and the pitch width fixes that.
    ys, xs = np.nonzero(resp > a.det_thresh)
    th = (xs + x0) / scale
    psi = math.pi - (ys + y0) / scale
    D = np.stack([np.sin(psi) * np.sin(th), np.cos(psi), np.sin(psi) * np.cos(th)], 1)
    D /= np.linalg.norm(D, axis=1, keepdims=True)

    rng = np.random.default_rng(a.seed)
    remaining = np.ones(len(D), bool)
    circles = []
    for _ in range(a.n_circles):
        idx = np.nonzero(remaining)[0]
        if len(idx) < 400:
            break
        Dr = D[idx]
        bestc, bestm = 0, None
        for _ in range(3000):
            i1, i2 = rng.integers(0, len(Dr), 2)
            m = np.cross(Dr[i1], Dr[i2])
            nm = np.linalg.norm(m)
            if nm < 1e-6:
                continue
            m = m / nm
            c = int((np.abs(Dr @ m) < a.circle_tol).sum())
            if c > bestc:
                bestc, bestm = c, m
        if bestm is None or bestc < 300:
            break
        inl = np.abs(Dr @ bestm) < a.circle_tol
        _, _, vt = np.linalg.svd(Dr[inl])
        m = vt[-1] / np.linalg.norm(vt[-1])
        inl = np.abs(Dr @ m) < a.circle_tol
        sel = idx[inl]
        circles.append({"m": m, "n": int(inl.sum()),
                        "xspan": int(xs[sel].max() - xs[sel].min()),
                        "yspan": int(ys[sel].max() - ys[sel].min())})
        remaining[sel] = False

    UP = np.array([0.0, -1.0, 0.0])

    def params_from(m_near, m_far, m_half, W, L):
        """Closed-form calibration from three great circles plus an assumed width."""
        t = np.cross(m_near, m_far)
        if np.linalg.norm(t) < 1e-6:
            return None
        t = t / np.linalg.norm(t)
        sv = np.cross(m_half, t)
        if np.linalg.norm(sv) < 1e-6:
            return None
        sv = sv / np.linalg.norm(sv)
        n = np.cross(t, sv)
        nn = np.linalg.norm(n)
        if nn < 1e-6:
            return None
        n = n / nn
        if n @ UP < 0:                       # canonicalise: normal points up
            n, sv = -n, -sv
        if n @ UP < math.cos(math.radians(40)):
            return None                      # wave-corrected panorama: near-vertical
        dn, df = m_near @ sv, m_far @ sv
        if abs(dn) < 1e-6 or abs(df) < 1e-6:
            return None
        rn, rf = (m_near @ n) / dn, (m_far @ n) / df
        if abs(rf - rn) < 1e-6:
            return None
        h = W / abs(rf - rn)                 # the only place absolute scale enters
        if not (1.0 < h < 40.0):
            return None
        b_mid = h * (rn + rf) / 2.0
        dh = m_half @ t
        a_half = h * (m_half @ n) / dh if abs(dh) > 1e-6 else 0.0
        al = math.asin(np.clip(n[2], -1, 1))
        ca = math.cos(al)
        if abs(ca) < 1e-6:
            return None
        be = math.atan2(n[0] / ca, -n[1] / ca)
        e1, e2 = basis(n[None, :])
        e1, e2 = e1[0], e2[0]
        ga = math.atan2(t @ e2, t @ e1)
        tx = a_half * math.cos(ga) - b_mid * math.sin(ga)
        ty = a_half * math.sin(ga) + b_mid * math.cos(ga)
        return np.array([al, be, h, ga % (2 * math.pi), tx, ty, L, W])

    lo = np.array([-0.45, -0.45, 1.0, 0.0, -120.0, -120.0, 85.0, 50.0])
    hi = np.array([0.45, 0.45, 40.0, 2 * math.pi, 120.0, 120.0, 115.0, 78.0])
    # Recall matters as much as precision: a model can sit ON detected lines while
    # explaining almost none of them.
    F = 8
    gh, gw = Ch // F + 1, Cw // F + 1
    det = (resp > a.det_thresh)
    dg = np.zeros((gh, gw), bool)
    dys, dxs = np.nonzero(det)
    dg[dys // F, dxs // F] = True
    n_det_cells = int(dg.sum())
    _cache = {}

    def model_for(L, W, fine=False):
        key = (round(L, 1), round(W, 1), fine)
        if key not in _cache:
            _cache[key] = (pitch_model(L, W, 40, 80) if fine
                           else pitch_model(L, W, 16, 36))
        return _cache[key]

    def bilinear(img, u, v):
        """Smooth sampling. Nearest-neighbour lookup makes the objective piecewise
        constant, and Nelder-Mead on a staircase does nothing -- that, not the
        geometry, is why the first refinements stalled."""
        u0 = np.clip(np.floor(u), 0, Cw - 2).astype(np.int32)
        v0 = np.clip(np.floor(v), 0, Ch - 2).astype(np.int32)
        du, dv = np.clip(u - u0, 0, 1), np.clip(v - v0, 0, 1)
        a00 = img[v0, u0]; a10 = img[v0, u0 + 1]
        a01 = img[v0 + 1, u0]; a11 = img[v0 + 1, u0 + 1]
        return ((a00 * (1 - du) + a10 * du) * (1 - dv) +
                (a01 * (1 - du) + a11 * du) * dv)

    def f1_of(p, fine=False):
        p = np.clip(np.asarray(p, float), lo, hi)
        mdl = model_for(p[6], p[7], fine)
        u, v, ok = project(p[None, :], mdl, scale, x0, y0, Cw, Ch)
        u, v, ok = u[0], v[0], ok[0]
        if ok.sum() < 0.25 * len(mdl):
            return 0.0
        if (u.max() - u.min()) < 0.5 * Cw or (v.max() - v.min()) < 0.18 * Ch:
            return 0.0
        prec = float((bilinear(resp, u, v) * ok).mean())
        ui = np.clip(u, 0, Cw - 1).astype(np.int32)
        vi = np.clip(v, 0, Ch - 1).astype(np.int32)
        hit = np.zeros((gh, gw), bool)
        hit[vi[ok] // F, ui[ok] // F] = True
        rec = float((hit & dg).sum()) / max(n_det_cells, 1)
        # smooth term drives the local solve, recall keeps it from collapsing
        return prec * (0.25 + rec)

    # Enumerate which detected circles play which role. The closed form is exact (it is
    # unit-tested against synthetic ground truth), so the only real unknown is the
    # assignment -- and the adjacent field contributes circles of its own.
    cand = []
    for i in range(len(circles)):
        for j in range(len(circles)):
            if i == j:
                continue
            for k in range(len(circles)):
                if k in (i, j):
                    continue
                for W in np.arange(50.0, 76.1, 2.0):
                    pp = params_from(circles[i]["m"], circles[j]["m"],
                                     circles[k]["m"], W, 0.0)
                    if pp is None:
                        continue
                    for ratio in (1.45, 1.55, 1.65, 1.75):
                        q = pp.copy()
                        q[6] = np.clip(W * ratio, lo[6], hi[6])
                        q = np.clip(q, lo, hi)
                        cand.append((f1_of(q), q, (i, j, k)))
    cand.sort(key=lambda z: -z[0])

    best = (None, -1.0)
    for sc0, pp, trip in cand[:a.refine]:
        r = minimize(lambda q: -f1_of(q, fine=False), pp, method="Nelder-Mead",
                     options={"maxiter": 2500, "xatol": 1e-4, "fatol": 1e-8})
        v2 = f1_of(r.x, fine=True)
        if v2 > best[1]:
            best = (np.clip(r.x, lo, hi), float(v2))
    if best[0] is None:
        print(json.dumps({"error": "no viable great-circle hypothesis",
                          "circles_found": len(circles)}, indent=1))
        return 5
    p, sc = best
    fine = model_for(p[6], p[7], True)

    # ---- honest scoring: fraction of projected line ON a detected line pixel ----
    dist = cv2.distanceTransform(1 - det.astype(np.uint8), cv2.DIST_L2, 3)
    u, v, ok = project(p[None, :], fine, scale, x0, y0, Cw, Ch)
    ui = np.clip(u, 0, Cw - 1).astype(np.int32)
    vi = np.clip(v, 0, Ch - 1).astype(np.int32)
    d = dist[vi, ui][0]
    okf = ok[0]
    on = float(((d <= a.hit_px) & okf).sum())
    inside = float(okf.sum())
    total = float(len(fine))

    al, be, h, ga, tx, ty, L, W = p
    doc = {
        "job": "D-A step 3: ray-space pitch calibration of the panorama",
        "params": {"alpha_rad": round(float(al), 5), "beta_rad": round(float(be), 5),
                   "camera_height_m": round(float(h), 3),
                   "gamma_rad": round(float(ga), 5),
                   "tx_m": round(float(tx), 3), "ty_m": round(float(ty), 3),
                   "pitch_L_m": round(float(L), 2), "pitch_W_m": round(float(W), 2)},
        "search_f1": round(sc, 5),
        "great_circles_found": len(circles),
        "hypotheses_scored": len(cand),
        "alignment": {
            "model_points": int(total),
            "inside_panorama": int(inside),
            "on_line_within_%.0fpx" % a.hit_px: int(on),
            "fraction_of_visible_on_line": round(on / inside, 4) if inside else None,
            "fraction_of_all_on_line": round(on / total, 4),
            "median_dist_px": round(float(np.median(d[okf])), 2) if inside else None,
            "recall_of_detected_line_cells": None,   # filled in below
        },
        "comparable_to": ("pitch/score_alignment.py -- PnLCalib scored 0.29 median "
                          "line-alignment with 26% of frames >=0.50"),
    }
    hit = np.zeros((gh, gw), bool)
    hit[vi[0][okf] // F, ui[0][okf] // F] = True
    doc["alignment"]["recall_of_detected_line_cells"] = round(
        float((hit & dg).sum()) / max(n_det_cells, 1), 4)
    doc["alignment"]["detected_line_cells"] = n_det_cells

    if a.out_overlay:
        vis = (bgr * 0.45).astype(np.uint8)
        vis[:, :, 2] = np.maximum(vis[:, :, 2],
                                  (np.clip(resp * 3, 0, 1) * 200).astype(np.uint8))
        for k in range(len(fine)):
            if okf[k]:
                cv2.circle(vis, (int(ui[0, k]), int(vi[0, k])), 2, (0, 255, 255), -1)
        cv2.imwrite(a.out_overlay, vis)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
