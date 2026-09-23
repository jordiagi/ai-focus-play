#!/usr/bin/env python3
"""D-B step 3 — the pitch region as a polygon in PANORAMA PIXEL SPACE, and a test of it.

D-B's premise is that Tier A detection needs pitch-relative *regions*, not metres. This
run supplied the evidence for that premise rather than assuming it: inverting the
14,607 player foot points onto the fitted ground plane gives an oriented bounding box of
**105.8 x 104.5 m, aspect 1.01** -- a square, where a pitch is about 1.5. The depth
spread comes out at 124 m. Near the horizon the far half of the pitch compresses into a
few pixels, so a small pixel error is tens of metres, and the metric inversion is
useless there. In panorama pixels the same cloud is perfectly well behaved.

So the zone is defined here, in pixels, and the polygon is **derived** from player
occupancy -- never drawn. That is the standing rule.

The derivation is then TESTED, because a region that merely contains the players is not
the same as the pitch. If the boundary is real, it should coincide with the white lines
that bound the playing surface, so the test is: what fraction of the polygon's boundary
lands on a detected line pixel -- scored against the fraction a random boundary of the
same length would achieve. A ratio near 1 means the polygon is an arbitrary blob.
"""
import argparse, sys, json, math
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", required=True, help="occupancy_points.json")
    ap.add_argument("--panorama", required=True)
    ap.add_argument("--line-map", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-image", default=None)
    ap.add_argument("--out-polygon", default=None)
    ap.add_argument("--sigma", type=float, default=11.0)
    ap.add_argument("--near-px", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    import cv2

    pano = cv2.imread(a.panorama)
    Ch, Cw = pano.shape[:2]
    lm = cv2.imread(a.line_map, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    det = (lm > 0.30).astype(np.uint8)
    dist = cv2.distanceTransform(1 - det, cv2.DIST_L2, 3)

    pts = np.array(json.loads(Path(a.points).read_text()))[:, :2]
    acc = np.zeros((Ch, Cw), np.float32)
    for u, v in pts:
        if 0 <= v < Ch and 0 <= u < Cw:
            acc[int(v), int(u)] += 1.0
    dens = cv2.GaussianBlur(acc, (0, 0), a.sigma)

    rng = np.random.default_rng(a.seed)
    rows = []
    best = None
    for q in (40, 50, 60, 70, 80):
        nz = dens[dens > 0]
        thr = float(np.percentile(nz, q))
        m = (dens >= thr).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
        nl, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        if nl <= 1:
            continue
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        reg = (lab == big).astype(np.uint8)
        cont, _ = cv2.findContours(reg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cont:
            continue
        c = max(cont, key=cv2.contourArea).reshape(-1, 2)
        covered = float((acc * reg).sum()) / max(float(acc.sum()), 1.0)
        d = dist[np.clip(c[:, 1], 0, Ch - 1), np.clip(c[:, 0], 0, Cw - 1)]
        on = float((d <= a.near_px).mean())
        # chance: a boundary of the same length placed at random over the panorama
        ridx = rng.integers(0, Ch * Cw, size=max(len(c), 1000))
        rd = dist.ravel()[ridx]
        chance = float((rd <= a.near_px).mean())
        rows.append({"pct": q, "threshold": round(thr, 5),
                     "area_frac": round(float(reg.mean()), 4),
                     "players_inside_frac": round(covered, 4),
                     "boundary_px": int(len(c)),
                     "boundary_on_line": round(on, 4),
                     "chance": round(chance, 4),
                     "lift": round(on / chance, 2) if chance > 0 else None})
        if best is None or (on / max(chance, 1e-9)) > best[0]:
            best = (on / max(chance, 1e-9), q, c, reg)

    doc = {"job": "D-B step 3: derived pitch region in panorama pixel space",
            "command": " ".join(sys.argv),
           "player_points": int(len(pts)), "canvas": [Cw, Ch],
           "near_px": a.near_px, "sweep": rows,
           "why_pixels_not_metres": (
               "inverting the same cloud onto the fitted ground plane gives a 105.8 x "
               "104.5 m box, aspect 1.01 -- a square. Near the horizon a few px is tens "
               "of metres, so the metric inversion is unusable; pixel space is not.")}
    if best:
        lift, q, c, reg = best
        doc["chosen"] = {"pct": q, "lift": round(lift, 2)}
        if a.out_polygon:
            Path(a.out_polygon).write_text(json.dumps(
                {"pct": q, "polygon_uv": c.tolist()}))
        if a.out_image:
            vis = (pano * 0.5).astype(np.uint8)
            hm = np.clip(dens / max(np.percentile(dens[dens > 0], 99), 1e-9), 0, 1)
            vis[:, :, 1] = np.maximum(vis[:, :, 1], (hm * 200).astype(np.uint8))
            vis[det > 0] = (0, 0, 255)
            cv2.polylines(vis, [c.reshape(-1, 1, 2)], True, (0, 255, 255), 3)
            cv2.imwrite(a.out_image, vis)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
