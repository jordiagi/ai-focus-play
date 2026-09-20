#!/usr/bin/env python3
"""D-B step 5 — put the ball candidates into panorama space.

Once a candidate is in panorama coordinates it is in ONE frame of reference for the
whole match, so a trajectory can be assembled across pans and zooms and compared with
fixed landmarks (the centre circle, the derived pitch region). That is what makes
pixel-space Tier A detection possible without metres.

Same exact composition used for the event frames and the players:

    frame --(SIFT homography)--> a panorama anchor --(its K, R)--> panorama

Both are views from one centre, so it is not an approximation. Only registrations at or
above the measured gate (>=100 RANSAC inliers) are kept; below ~40 the homography is
garbage (36-52 px round-trip), so an ungated frame contributes nothing rather than
noise.

Registration dominates the cost (~0.5 s/frame), so frames are decoded in one ffmpeg
pass per period and registered in parallel, with each worker building the anchor
features once.

Every candidate is carried through with its confidence and apparent size. Nothing here
decides which candidate is the ball.
"""
import argparse, json, math, subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

_G = {}


def _init(anchor_paths, cam_list, scale, origin, warp, nfeat):
    import cv2
    _G["sift"] = cv2.SIFT_create(nfeatures=nfeat)
    _G["bf"] = cv2.BFMatcher()
    _G["cams"] = cam_list
    _G["ctimes"] = np.array([c["t"] for c in cam_list])
    _G["scale"] = scale
    _G["origin"] = origin
    _G["warper"] = cv2.PyRotationWarper(warp, float(scale))
    _G["apaths"] = {int(k): v for k, v in anchor_paths.items()}
    _G["af"] = {}


def _anchor(i):
    """Load anchor features on demand, keeping only a few.

    Caching all 80 anchors in every worker exhausted 15 GB of RAM: each worker held
    80 x 2500 SIFT descriptors plus their KeyPoint objects. Jobs are time-ordered, so
    a worker only ever needs a handful of anchors at a time.
    """
    import cv2
    if i in _G["af"]:
        return _G["af"][i]
    path = _G["apaths"].get(i)
    if path is None:
        return None
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        _G["af"][i] = None
        return None
    if len(_G["af"]) > 10:
        _G["af"].pop(next(iter(_G["af"])))
    _G["af"][i] = _G["sift"].detectAndCompute(img, None)
    return _G["af"][i]


def _work(job):
    import cv2
    out = []
    x0, y0 = _G["origin"]
    for t, path, cands, sx, sy in job:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        kp, des = _G["sift"].detectAndCompute(img, None)
        if des is None:
            continue
        best = None
        for j in np.argsort(np.abs(_G["ctimes"] - t))[:4]:
            j = int(j)
            got = _anchor(j)
            if got is None:
                continue
            kb, db = got
            if db is None:
                continue
            knn = _G["bf"].knnMatch(des, db, k=2)
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
        if best is None or best[0] < _G["gate"]:
            out.append({"t": t, "reg": 0, "c": []})
            continue
        n_in, H, j = best
        cam = _G["cams"][j]
        K = np.array([[cam["focal"], 0, cam["ppx"]],
                      [0, cam["focal"] * cam["aspect"], cam["ppy"]],
                      [0, 0, 1]], np.float32)
        R = np.ascontiguousarray(np.array(cam["R"], np.float32))
        pts = np.float32([[c[0] * sx, c[1] * sy] for c in cands]).reshape(-1, 1, 2)
        P = cv2.perspectiveTransform(pts, H).reshape(-1, 2)
        mapped = []
        for (cx, cy, cw, cf), q in zip(cands, P):
            u, v = _G["warper"].warpPoint((float(q[0]), float(q[1])), K, R)
            mapped.append([round(float(u - x0), 1), round(float(v - y0), 1),
                           round(float(cw * sx), 2), cf])
        out.append({"t": t, "reg": n_in, "c": mapped})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ball", required=True)
    ap.add_argument("--video", required=True, help="local 720p proxy")
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--frames-dir", required=True, help="panorama anchor frames")
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--min-inliers", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--nfeatures", type=int, default=2500)
    ap.add_argument("--p1", type=float, nargs=2, default=[562.3, 2879.3])
    ap.add_argument("--p2", type=float, nargs=2, default=[3674.4, 6132.1])
    a = ap.parse_args()

    import cv2

    B = json.loads(Path(a.ball).read_text())
    fps = B["config"]["fps"]
    fw, fh = B["config"]["frame_wh"]
    det = {round(d["t"], 3): d["c"] for d in B["detections"]}

    C = json.loads(Path(a.cameras).read_text())
    cams = C["cameras"]

    tmp = Path(a.tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    index = []
    for tag, (t0, t1) in (("p1", a.p1), ("p2", a.p2)):
        sub = tmp / tag
        sub.mkdir(exist_ok=True)
        if not any(sub.glob("*.jpg")):
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t0),
                            "-i", a.video, "-t", str(t1 - t0),
                            "-vf", f"fps={fps},scale={a.width}:-1", "-q:v", "3",
                            str(sub / "%06d.jpg")], check=True)
        for p in sorted(sub.glob("*.jpg")):
            i = int(p.stem) - 1
            index.append((round(t0 + i / fps, 3), str(p)))
    index.sort()

    sx = a.width / float(fw)
    probe = cv2.imread(index[0][1])
    sy = probe.shape[0] / float(fh)

    jobs = [(t, p, det.get(t, []), sx, sy) for t, p in index if det.get(t)]
    anchors = {}
    for i, c in enumerate(cams):
        p = Path(a.frames_dir) / f"{int(round(c['t'] * 1000)):08d}.jpg"
        if p.exists():
            anchors[i] = str(p)

    chunks = [jobs[i:i + 40] for i in range(0, len(jobs), 40)]
    _G["gate"] = a.min_inliers
    results = []
    with ProcessPoolExecutor(max_workers=a.workers, initializer=_init,
                             initargs=(anchors, cams, float(C["scale"]),
                                       C["origin"], C.get("warp", "spherical"),
                                       a.nfeatures)) as ex:
        for r in ex.map(_setgate_and_work, [(c, a.min_inliers) for c in chunks]):
            results.extend(r)
    results.sort(key=lambda r: r["t"])

    reg = sum(1 for r in results if r["reg"] >= a.min_inliers)
    ncand = sum(len(r["c"]) for r in results)
    doc = {"job": "D-B step 5: ball candidates in panorama space",
           "fps": fps, "frames_with_candidates": len(jobs),
           "frames_registered": reg,
           "registered_frac": round(reg / max(len(jobs), 1), 4),
           "candidates_mapped": ncand,
           "min_inliers_gate": a.min_inliers,
           "note": "no candidate is asserted to be the ball; association is next",
           "tracks": results}
    Path(a.out).write_text(json.dumps(doc))
    print(json.dumps({k: v for k, v in doc.items() if k != "tracks"}, indent=1))
    return 0


def _setgate_and_work(arg):
    chunk, gate = arg
    _G["gate"] = gate
    return _work(chunk)


if __name__ == "__main__":
    raise SystemExit(main())
