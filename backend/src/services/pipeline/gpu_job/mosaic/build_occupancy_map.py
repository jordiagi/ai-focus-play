#!/usr/bin/env python3
"""D-B step 2 — derive the pitch from where the PLAYERS are, in panorama space.

The zones D-B needs (pitch region, goal mouths, the boundary a ball crosses to go out)
have to be **derived, not drawn** -- that is the standing rule, no manual annotation --
and they cannot come from metres, because calibration has now failed five separate
ways. Players are the remaining source: they are confined to the playing surface, they
cover it over 103 minutes, and using them needs no labels of ours.

Each detection is mapped into the panorama the same way `locate_play_region.py` maps
event frames, and for the same reason it is exact: an event frame and a panorama frame
are views from the same centre, so

    frame --(SIFT homography)--> a panorama frame --(its K, R)--> panorama

composes without approximation. Only registrations at or above the measured gate
(>=100 RANSAC inliers) are used.

A player's **foot point** is taken as the bottom-centre of the box, because that is the
point actually on the ground plane; the box centre floats above it by half a body and
would bias the map upward by a distance that varies with how close the player is.

The occupancy map is reported, not thresholded into a polygon here. Turning it into
zones is the next step and deserves its own measurement -- the repo has been burned
before by treating coverage as if it were accuracy.
"""
import argparse, sys, json, math, subprocess
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detections", required=True, help="players.json from gpu-box")
    ap.add_argument("--video", required=True, help="local 720p proxy")
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--frames-dir", required=True, help="the panorama's source frames")
    ap.add_argument("--panorama", required=True)
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-image", default=None)
    ap.add_argument("--out-points", default=None)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--neighbours", type=int, default=4)
    ap.add_argument("--min-inliers", type=int, default=100)
    ap.add_argument("--min-box-h", type=float, default=12.0,
                    help="reject specks; below this a 'person' is noise or a spectator")
    ap.add_argument("--max-box-h-frac", type=float, default=0.55,
                    help="reject people very close to the camera (not on our pitch)")
    ap.add_argument("--sigma", type=float, default=9.0)
    a = ap.parse_args()

    import cv2

    C = json.loads(Path(a.cameras).read_text())
    scale, (x0, y0) = float(C["scale"]), C["origin"]
    pano = cv2.imread(a.panorama)
    Ch, Cw = pano.shape[:2]
    warper = cv2.PyRotationWarper(C.get("warp", "spherical"), scale)
    cams = C["cameras"]
    ctimes = np.array([c["t"] for c in cams])

    det = json.loads(Path(a.detections).read_text())
    frames = det["detections"]

    ref = {}
    for i, c in enumerate(cams):
        p = Path(a.frames_dir) / f"{int(round(c['t'] * 1000)):08d}.jpg"
        if p.exists():
            ref[i] = str(p)

    sift = cv2.SIFT_create(nfeatures=3000)
    bf = cv2.BFMatcher()
    feats = {}

    def fof(i):
        if i not in feats:
            img = cv2.imread(ref[i], cv2.IMREAD_GRAYSCALE)
            feats[i] = (*sift.detectAndCompute(img, None), img.shape)
        return feats[i]

    tmp = Path(a.tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    acc = np.zeros((Ch, Cw), np.float32)
    pts = []
    reg_ok = reg_try = 0
    kept = dropped_small = dropped_big = outside = 0

    for fr in frames:
        t = fr["t"]
        if not fr["boxes"]:
            continue
        fp = tmp / f"p{int(round(t*1000)):08d}.jpg"
        if not fp.exists():
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t),
                            "-i", a.video, "-frames:v", "1",
                            "-vf", f"scale={a.width}:-1", "-q:v", "2", str(fp)],
                           check=True)
        img = cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        reg_try += 1
        kp, des = sift.detectAndCompute(img, None)
        if des is None:
            continue
        h, w = img.shape
        best = None
        for j in np.argsort(np.abs(ctimes - t))[:a.neighbours]:
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
            if best is None or int(mask.sum()) > best[0]:
                best = (int(mask.sum()), H, j)
        if best is None or best[0] < a.min_inliers:
            continue
        reg_ok += 1
        _, H, j = best
        cam = cams[j]
        K = np.array([[cam["focal"], 0, cam["ppx"]],
                      [0, cam["focal"] * cam["aspect"], cam["ppy"]],
                      [0, 0, 1]], np.float32)
        R = np.ascontiguousarray(np.array(cam["R"], np.float32))
        sx = w / float(fr["w"])          # detections are on the FULL-res source
        sy = h / float(fr["h"])
        foot = []
        for x1, y1, x2, y2, cf in fr["boxes"]:
            bh = (y2 - y1) * sy
            if bh < a.min_box_h:
                dropped_small += 1
                continue
            if bh > a.max_box_h_frac * h:
                dropped_big += 1
                continue
            foot.append([(x1 + x2) / 2 * sx, y2 * sy])
        if not foot:
            continue
        P = cv2.perspectiveTransform(np.float32(foot).reshape(-1, 1, 2), H).reshape(-1, 2)
        for q in P:
            u, v = warper.warpPoint((float(q[0]), float(q[1])), K, R)
            u, v = u - x0, v - y0
            if not (0 <= u < Cw and 0 <= v < Ch):
                outside += 1
                continue
            acc[int(v), int(u)] += 1.0
            kept += 1
            if a.out_points:
                pts.append([round(float(u), 1), round(float(v), 1), round(t, 2)])

    dens = cv2.GaussianBlur(acc, (0, 0), a.sigma)
    doc = {
        "job": "D-B step 2: player occupancy in panorama space",
        "command": " ".join(sys.argv),
        "frames_with_detections": len(frames),
        "frames_registered": reg_ok, "frames_tried": reg_try,
        "registered_frac": round(reg_ok / max(reg_try, 1), 3),
        "player_points_mapped": kept,
        "dropped_small_box": dropped_small, "dropped_large_box": dropped_big,
        "mapped_outside_panorama": outside,
        "canvas": [Cw, Ch],
    }
    if kept:
        nz = dens[dens > 0]
        thr = float(np.percentile(nz, 60))
        m = (dens >= thr).astype(np.uint8)
        nl, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        if nl > 1:
            big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            reg = (lab == big)
            ys, xs = np.nonzero(reg)
            doc["occupancy"] = {
                "density_p60": round(thr, 4),
                "main_blob_area_frac": round(float(reg.mean()), 4),
                "u_range": [int(xs.min()), int(xs.max())],
                "v_range": [int(ys.min()), int(ys.max())],
                "points_in_main_blob": int(acc[reg].sum()),
                "points_total": int(acc.sum()),
            }
        if a.out_image:
            vis = (pano * 0.45).astype(np.uint8)
            hm = np.clip(dens / max(np.percentile(dens[dens > 0], 99), 1e-6), 0, 1)
            vis[:, :, 1] = np.maximum(vis[:, :, 1], (hm * 255).astype(np.uint8))
            cv2.imwrite(a.out_image, vis)
    if a.out_points:
        Path(a.out_points).write_text(json.dumps(pts))
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
