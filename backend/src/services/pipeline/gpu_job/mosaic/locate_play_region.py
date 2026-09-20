#!/usr/bin/env python3
"""D-A step 3c — find which lines are OURS, using Veo's own events.

Calibration keeps failing on a multi-pitch complex: only one touchline-parallel line
sits at a pitch-like distance from the fitted centre circle, where a real pitch centre
would have two. The detected lines span more than one field, and no rigid pitch model
can satisfy a mixture.

Veo already tells us which field is ours, for free. Every one of the 447 events carries
a video timestamp, and the export is a BALL-FOLLOWING crop -- the virtual camera centres
on the action by construction. So the centre of the frame at each event time is a point
on our pitch. Project those into the panorama and the cloud outlines our field.

This is deliberately a WEAK use of the data. An earlier attempt tried to calibrate from
ball-position correspondences directly and failed at 10-15 m with only ~40 % RANSAC
inliers, because Veo's coordinate marks where the action was rather than where a
detected ball is. Outlining a region is robust to exactly that error: camera lag of a
few metres moves a point within the pitch, it does not move it onto another field.

    event frame --(SIFT homography)--> a panorama frame --(its K,R)--> panorama

Both are views from the same centre, so the composition is exact. Only registrations at
or above the measured gate (>=100 RANSAC inliers) are kept.

Veo's own (x, z) pitch coordinate is recorded alongside each point, so a later step can
try direct correspondences if the region mask is not enough.
"""
import argparse, csv, json, math, subprocess
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--frames-dir", required=True, help="the panorama's source frames")
    ap.add_argument("--panorama", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--events", type=int, default=220)
    ap.add_argument("--neighbours", type=int, default=4)
    ap.add_argument("--min-inliers", type=int, default=100)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-mask", default=None)
    ap.add_argument("--out-points", default=None)
    ap.add_argument("--dilate", type=int, default=120,
                    help="grow the region: the ball cloud is inside the pitch, the "
                         "lines we need are at its edge")
    a = ap.parse_args()

    import cv2

    C = json.loads(Path(a.cameras).read_text())
    scale = float(C["scale"])
    x0, y0 = C["origin"]
    pano = cv2.imread(a.panorama)
    Ch, Cw = pano.shape[:2]
    warper = cv2.PyRotationWarper(C.get("warp", "spherical"), scale)

    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    rows = list(csv.DictReader(open(bench)))
    ev = [(int(r["video_time_ms"]) / 1000.0, r["event_type"],
           float(r["x"]) if r["x"] else None, float(r["z"]) if r["z"] else None)
          for r in rows]
    ev.sort()
    if len(ev) > a.events:
        step = len(ev) / a.events
        ev = [ev[int(k * step)] for k in range(a.events)]

    cams = C["cameras"]
    ctimes = np.array([c["t"] for c in cams])
    sift = cv2.SIFT_create(nfeatures=3000)
    bf = cv2.BFMatcher()

    ref = {}
    for i, c in enumerate(cams):
        p = Path(a.frames_dir) / f"{int(round(c['t'] * 1000)):08d}.jpg"
        if p.exists():
            ref[i] = str(p)

    tmp = Path(a.tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    feats = {}

    def fof(i):
        if i not in feats:
            img = cv2.imread(ref[i], cv2.IMREAD_GRAYSCALE)
            feats[i] = (*sift.detectAndCompute(img, None), img.shape)
        return feats[i]

    pts, kept, tried = [], 0, 0
    for t, etype, ex, ez in ev:
        fp = tmp / f"e{int(round(t*1000)):08d}.jpg"
        if not fp.exists():
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t),
                            "-i", a.video, "-frames:v", "1",
                            "-vf", f"scale={a.width}:-1", "-q:v", "2", str(fp)],
                           check=True)
        img = cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        tried += 1
        kp, des = sift.detectAndCompute(img, None)
        if des is None:
            continue
        h, w = img.shape
        order = np.argsort(np.abs(ctimes - t))[:a.neighbours]
        best = None
        for j in order:
            j = int(j)
            if j not in ref:
                continue
            kb, db, _ = fof(j)
            if db is None:
                continue
            knn = bf.knnMatch(des, db, k=2)
            good = [m for m, n in (q for q in knn if len(q) == 2)
                    if m.distance < 0.75 * n.distance]
            if len(good) < 8:
                continue
            src = np.float32([kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
            if H is None or mask is None:
                continue
            n_in = int(mask.sum())
            if best is None or n_in > best[0]:
                best = (n_in, H, j)
        if best is None or best[0] < a.min_inliers:
            continue
        n_in, H, j = best
        c = cv2.perspectiveTransform(np.float32([[w / 2, h / 2]]).reshape(-1, 1, 2),
                                     H).reshape(2)
        cam = cams[j]
        K = np.array([[cam["focal"], 0, cam["ppx"]],
                      [0, cam["focal"] * cam["aspect"], cam["ppy"]],
                      [0, 0, 1]], np.float32)
        R = np.ascontiguousarray(np.array(cam["R"], np.float32))
        u, v = warper.warpPoint((float(c[0]), float(c[1])), K, R)
        u, v = u - x0, v - y0
        if not (0 <= u < Cw and 0 <= v < Ch):
            continue
        kept += 1
        pts.append({"t": t, "event": etype, "u": float(u), "v": float(v),
                    "inliers": n_in, "veo_x": ex, "veo_z": ez})

    doc = {"job": "D-A step 3c: play region from Veo events",
           "events_tried": tried, "events_located": kept,
           "located_frac": round(kept / max(tried, 1), 3),
           "canvas": [Cw, Ch]}
    if pts:
        U = np.array([p["u"] for p in pts])
        V = np.array([p["v"] for p in pts])
        doc["u_range"] = [float(U.min()), float(U.max())]
        doc["v_range"] = [float(V.min()), float(V.max())]
        if a.out_mask:
            m = np.zeros((Ch, Cw), np.uint8)
            for p in pts:
                cv2.circle(m, (int(p["u"]), int(p["v"])), 3, 255, -1)
            hull = cv2.convexHull(np.stack([U, V], 1).astype(np.int32))
            filled = np.zeros((Ch, Cw), np.uint8)
            cv2.fillConvexPoly(filled, hull, 255)
            grown = cv2.dilate(filled, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (2 * a.dilate + 1, 2 * a.dilate + 1)))
            cv2.imwrite(a.out_mask, grown)
            doc["hull_area_frac"] = round(float((filled > 0).mean()), 4)
            doc["mask_area_frac"] = round(float((grown > 0).mean()), 4)
    if a.out_points:
        Path(a.out_points).write_text(json.dumps(pts))
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
