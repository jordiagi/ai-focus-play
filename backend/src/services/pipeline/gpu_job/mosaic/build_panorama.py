#!/usr/bin/env python3
"""D-A step 2 — reconstruct the panorama with a ROTATING-CAMERA model.

`build_mosaic.py` warped every frame onto one frame's image plane and produced a
bowtie: the pan exceeds 90 degrees, so distant views project towards infinity and
stretch without bound. The planar model is right *locally* -- loop closure is 0.97 px
median -- but an image plane is the wrong surface to composite a wide pan onto.

The correct model is the one that matches what Veo actually does: a camera rotating
about a fixed centre with a varying focal length, i.e. a pan-zoom crop of a fixed
panorama. Each frame then has a rotation R and a focal f, and frames composite onto a
SPHERE, which has no singularity at 90 degrees.

Pipeline (OpenCV's stitching detail API, the standard one):

  features -> pairwise matches -> HomographyBasedEstimator (initial R, f)
  -> BundleAdjusterRay (global refinement over all pairs) -> waveCorrect
  -> spherical warp -> per-pixel MEDIAN composite

The median is the point, not an incidental choice: pitch is stationary across the match
while players move through it, so compositing many frames dissolves the players and
leaves the line markings. That is the input a pitch-calibration model wants, and no
single frame of this footage provides it.

Exit codes: 0 built, 4 too few frames survived matching.
"""
import argparse, sys, json, math, subprocess
from pathlib import Path


def relative_focals(G):
    """Per-frame relative focal, solved globally and linearly.

    OpenCV's HomographyBasedEstimator assigns ONE focal to every camera and
    BundleAdjusterRay then holds focals fixed, so a zooming camera is forced into a
    constant-focal model and the error lands in the rotations -- which is what blurs
    the line markings. BundleAdjusterReproj does refine focal but goes degenerate here
    (it returned a negative focal).

    So estimate focal separately and hand it to Ray, which then only has to solve
    rotations. For an edge i->j between similar viewing directions the homography's
    local scale at the image centre is f_j/f_i, giving one linear equation per edge in
    log space. Solving all 2798 at once is drift-free for the same reason the mosaic
    is: it uses every loop, not a chain.

    Measured on this match: focal varies by 2.41x, and only 25% of frames sit within
    +/-10% of the median. The constant-focal assumption is not close.
    """
    import numpy as np
    W, H = G["width"], G["height"]
    n = len(G["times"])
    rows, rhs, wts = [], [], []
    for e in G["edges"]:
        M = np.array(e["H"]).reshape(3, 3)
        x, y = W / 2, H / 2
        d = M[2, 0] * x + M[2, 1] * y + M[2, 2]
        if abs(d) < 1e-9:
            continue
        u = M[0, 0] * x + M[0, 1] * y + M[0, 2]
        v = M[1, 0] * x + M[1, 1] * y + M[1, 2]
        J = np.array([[(M[0, 0] * d - u * M[2, 0]) / d ** 2,
                       (M[0, 1] * d - u * M[2, 1]) / d ** 2],
                      [(M[1, 0] * d - v * M[2, 0]) / d ** 2,
                       (M[1, 1] * d - v * M[2, 1]) / d ** 2]])
        sc = math.sqrt(abs(np.linalg.det(J)))
        if not (0.05 < sc < 20):
            continue
        rows.append((e["i"], e["j"]))
        rhs.append(math.log(sc))
        wts.append(min(e["inliers"], 800) ** 0.5)
    A = np.zeros((len(rows) + 1, n))
    b = np.zeros(len(rows) + 1)
    for k, (i, j) in enumerate(rows):
        A[k, j] = wts[k]
        A[k, i] = -wts[k]
        b[k] = rhs[k] * wts[k]
    A[-1, :] = 1.0                      # gauge: mean log-focal = 0
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    return np.exp(sol)


def grab(video, t, out, width):
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t), "-i", str(video),
                        "-frames:v", "1", "-vf", f"scale={width}:-1", "-q:v", "2",
                        str(out)], check=True)
    return str(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True,
                    help="graph JSON from measure_loop_closure.py (for the frame list)")
    ap.add_argument("--frames", type=int, default=90,
                    help="how many frames to stitch, evenly spaced over the match")
    ap.add_argument("--warp", default="spherical",
                    choices=["spherical", "cylindrical", "mercator", "plane"])
    ap.add_argument("--match-conf", type=float, default=0.3)
    ap.add_argument("--conf-thresh", type=float, default=1.0)
    ap.add_argument("--max-side", type=int, default=4000)
    ap.add_argument("--out-image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-cameras", default=None)
    ap.add_argument("--video", default=None,
                    help="re-extract frames at --width instead of reusing the graph's")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--frames-dir", default=None)
    ap.add_argument("--no-seed-focals", action="store_true",
                    help="keep OpenCV's one-focal-for-everything (worse; for comparison)")
    a = ap.parse_args()

    import cv2, numpy as np

    G = json.loads(Path(a.graph).read_text())
    times = G["times"]
    allf = {int(k): v for k, v in G["frames"].items()}
    idxs = sorted(allf)
    if len(idxs) > a.frames:
        step = len(idxs) / a.frames
        idxs = [idxs[int(k * step)] for k in range(a.frames)]

    if a.video:
        if not a.frames_dir:
            raise SystemExit("--video requires --frames-dir")
        src = {i: grab(Path(a.video), times[i],
                       Path(a.frames_dir) / f"{int(times[i]*1000):08d}.jpg", a.width)
               for i in idxs}
    else:
        src = {i: allf[i] for i in idxs}

    rel = None if a.no_seed_focals else relative_focals(G)

    imgs, keep_t, keep_g = [], [], []
    for i in idxs:
        im = cv2.imread(src[i])
        if im is not None:
            imgs.append(im)
            keep_t.append(times[i])
            keep_g.append(i)

    finder = cv2.SIFT_create(nfeatures=3000)
    feats = [cv2.detail.computeImageFeatures2(finder, im) for im in imgs]

    matcher = cv2.detail.BestOf2NearestMatcher_create(False, a.match_conf)
    pw = matcher.apply2(feats, None)
    matcher.collectGarbage()

    keep = cv2.detail.leaveBiggestComponent(feats, pw, a.conf_thresh)
    keep = [int(x) for x in np.array(keep).ravel()]
    if len(keep) < 8:
        print(json.dumps({"error": "too few frames in the matched component",
                          "kept": len(keep), "of": len(imgs)}, indent=1))
        return 4
    imgs = [imgs[i] for i in keep]
    feats = [feats[i] for i in keep]
    keep_t = [keep_t[i] for i in keep]
    keep_g = [keep_g[i] for i in keep]
    pw = matcher.apply2(feats, None)
    matcher.collectGarbage()

    est = cv2.detail.HomographyBasedEstimator()
    ok, cams = est.apply(feats, pw, None)
    if not ok:
        print(json.dumps({"error": "HomographyBasedEstimator failed"}, indent=1))
        return 4
    for c in cams:
        c.R = c.R.astype(np.float32)

    # Seed the real per-frame focal. Ray keeps focals fixed, so this is the only
    # place the camera's zoom can enter the model at all.
    seeded = False
    if rel is not None:
        r = np.array([rel[g] for g in keep_g], float)
        r = r / np.median(r)
        base = float(np.median([c.focal for c in cams]))
        for c, ri in zip(cams, r):
            c.focal = base * float(ri)
        seeded = True

    adj = cv2.detail.BundleAdjusterRay()
    adj.setConfThresh(a.conf_thresh)
    adj.setRefinementMask(np.ones((3, 3), np.uint8))
    ok, cams = adj.apply(feats, pw, cams)
    if not ok:
        print(json.dumps({"error": "BundleAdjusterRay failed"}, indent=1))
        return 4

    focals = sorted(c.focal for c in cams)
    scale = (focals[len(focals) // 2] if len(focals) % 2 else
             (focals[len(focals) // 2 - 1] + focals[len(focals) // 2]) / 2)

    Rs = [np.ascontiguousarray(c.R) for c in cams]
    if a.warp in ("spherical", "cylindrical", "mercator"):
        cv2.detail.waveCorrect(Rs, cv2.detail.WAVE_CORRECT_HORIZ)
        for c, R in zip(cams, Rs):
            c.R = R

    # cap the canvas by shrinking the projection scale, not by cropping
    warper = cv2.PyRotationWarper(a.warp, float(scale))
    rois = []
    for im, c in zip(imgs, cams):
        K = c.K().astype(np.float32)
        rois.append(warper.warpRoi((im.shape[1], im.shape[0]), K, c.R))
    xs = [r[0] for r in rois]; ys = [r[1] for r in rois]
    xe = [r[0] + r[2] for r in rois]; ye = [r[1] + r[3] for r in rois]
    span = max(max(xe) - min(xs), max(ye) - min(ys))
    if span > a.max_side:
        scale *= a.max_side / span
        warper = cv2.PyRotationWarper(a.warp, float(scale))

    warped, masks, corners = [], [], []
    for im, c in zip(imgs, cams):
        K = c.K().astype(np.float32)
        cor, wi = warper.warp(im, K, c.R, cv2.INTER_LINEAR, cv2.BORDER_CONSTANT)
        _, wm = warper.warp(np.full(im.shape[:2], 255, np.uint8), K, c.R,
                            cv2.INTER_NEAREST, cv2.BORDER_CONSTANT)
        warped.append(wi); masks.append(wm); corners.append(cor)

    x0 = min(c[0] for c in corners); y0 = min(c[1] for c in corners)
    x1 = max(c[0] + w.shape[1] for c, w in zip(corners, warped))
    y1 = max(c[1] + w.shape[0] for c, w in zip(corners, warped))
    Cw, Ch = int(x1 - x0), int(y1 - y0)

    acc = np.zeros((Ch, Cw, 3), np.uint8)
    cov = np.zeros((Ch, Cw), np.uint16)
    # median in strips so peak RAM stays ~O(strip * n), not O(canvas * n)
    STRIP = max(32, min(192, (1 << 28) // max(1, Cw * 3 * len(warped))))
    for y in range(0, Ch, STRIP):
        y2 = min(Ch, y + STRIP)
        buf = np.full((len(warped), y2 - y, Cw, 3), np.nan, np.float32)
        for k, (im, mk, cor) in enumerate(zip(warped, masks, corners)):
            oy, ox = cor[1] - y0, cor[0] - x0
            ry0, ry1 = max(y, oy), min(y2, oy + im.shape[0])
            if ry1 <= ry0:
                continue
            sy0, sy1 = ry0 - oy, ry1 - oy
            sub = im[sy0:sy1].astype(np.float32)
            sm = mk[sy0:sy1] > 0
            sub[~sm] = np.nan
            buf[k, ry0 - y:ry1 - y, ox:ox + im.shape[1]] = sub
            cov[ry0:ry1, ox:ox + im.shape[1]] += sm
        with np.errstate(all="ignore"):
            med = np.nanmedian(buf, axis=0)
        acc[y:y2] = np.nan_to_num(med).astype(np.uint8)

    Path(a.out_image).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(a.out_image, acc)

    doc = {
        "job": "D-A step 2: rotating-camera panorama",
        "command": " ".join(sys.argv),
        "warp": a.warp,
        "frames_offered": len(idxs), "frames_matched": len(imgs),
        "focal_seeded_per_frame": seeded, "source_width": a.width if a.video else G["width"],
        "conf_thresh": a.conf_thresh, "match_conf": a.match_conf,
        "focal_px": {"median": round(float(scale), 1),
                     "min": round(float(min(focals)), 1),
                     "max": round(float(max(focals)), 1),
                     "zoom_ratio": round(float(max(focals) / min(focals)), 2)},
        "panorama": {"path": a.out_image, "width": Cw, "height": Ch,
                     "coverage_frac": round(float((cov > 0).mean()), 3),
                     "median_stack_depth": int(np.median(cov[cov > 0])) if (cov > 0).any() else 0,
                     "max_stack_depth": int(cov.max())},
        "horizontal_fov_deg": round(float(2 * math.degrees(math.atan(Cw / (2 * scale)))), 1),
        "frame_times_s": keep_t,
    }
    if a.out_cameras:
        Path(a.out_cameras).write_text(json.dumps({
            "warp": a.warp, "scale": float(scale), "origin": [int(x0), int(y0)],
            "cameras": [{"t": t, "focal": float(c.focal), "ppx": float(c.ppx),
                         "ppy": float(c.ppy), "aspect": float(c.aspect),
                         "R": np.asarray(c.R).tolist()}
                        for t, c in zip(keep_t, cams)]}))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps({k: v for k, v in doc.items() if k != "frame_times_s"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
