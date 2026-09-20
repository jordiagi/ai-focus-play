#!/usr/bin/env python3
"""D-A step 3a — composite the LINE RESPONSE, not the pixels.

Calibrating the RGB panorama failed for a diagnosed reason: only three or four
distinct pitch lines could be recovered from it, which is not enough to constrain an
8-parameter fit (the orthogonality criterion scored 0.84 at vertical versus 0.89 at its
optimum -- i.e. it barely discriminates).

The cause is the median composite itself. Median over ~14 frames is what removes the
players, but it also averages slight residual misalignment, and a 1-2 px pitch line is
exactly the structure that destroys first. The line survives in every SOURCE frame,
where it is sharp and high-contrast; it is the compositing that loses it.

So detect lines FIRST, per frame, then warp the response into the panorama and
accumulate. Each frame contributes a crisp line map, players occlude different parts in
different frames, and the accumulation over 80 frames fills in what any one frame
misses. The geometry is unchanged -- same cameras, same warper, same canvas -- so the
result is registered pixel-for-pixel with the RGB panorama.
"""
import argparse, json, math
from pathlib import Path

import numpy as np


def frame_response(bgr, cv2):
    """Line evidence on one sharp source frame."""
    i16 = bgr.astype(np.int16)
    B, G, R = i16[:, :, 0], i16[:, :, 1], i16[:, :, 2]
    grn = G - (R + B) // 2
    gray0 = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mu = cv2.boxFilter(gray0, -1, (17, 17))
    sd = np.sqrt(np.maximum(cv2.boxFilter(gray0 * gray0, -1, (17, 17)) - mu * mu, 0))
    grass = ((grn > 20) & (sd < 16) & (bgr.max(axis=2) > 40)).astype(np.uint8)
    grass = cv2.morphologyEx(grass, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    resp = np.zeros_like(gray0)
    for k in (5, 9, 15, 25):
        t = cv2.morphologyEx(gray0, cv2.MORPH_TOPHAT,
                             cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        resp = np.maximum(resp, t)
    resp = resp / (cv2.GaussianBlur(resp, (0, 0), 21) + 6.0)
    sat = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1].astype(np.float32)
    resp *= np.clip((110.0 - sat) / 60.0, 0, 1)      # blue lines are saturated
    resp *= grass
    return np.clip(resp, 0, 4.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--panorama", required=True, help="only for canvas size")
    ap.add_argument("--out-image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-cover", type=int, default=3,
                    help="a pixel needs this many contributing frames to be trusted")
    a = ap.parse_args()

    import cv2

    C = json.loads(Path(a.cameras).read_text())
    scale = float(C["scale"])
    x0, y0 = C["origin"]
    pano = cv2.imread(a.panorama)
    Ch, Cw = pano.shape[:2]
    warper = cv2.PyRotationWarper(C.get("warp", "spherical"), float(scale))

    acc = np.zeros((Ch, Cw), np.float32)
    cov = np.zeros((Ch, Cw), np.float32)
    used = 0
    for cam in C["cameras"]:
        p = Path(a.frames_dir) / f"{int(round(cam['t'] * 1000)):08d}.jpg"
        if not p.exists():
            continue
        img = cv2.imread(str(p))
        if img is None:
            continue
        f, asp = cam["focal"], cam["aspect"]
        K = np.array([[f, 0, cam["ppx"]], [0, f * asp, cam["ppy"]], [0, 0, 1]], np.float32)
        Rm = np.ascontiguousarray(np.array(cam["R"], np.float32))
        r = frame_response(img, cv2)
        cor, wr = warper.warp(r, K, Rm, cv2.INTER_LINEAR, cv2.BORDER_CONSTANT)
        _, wm = warper.warp(np.ones(img.shape[:2], np.float32), K, Rm,
                            cv2.INTER_NEAREST, cv2.BORDER_CONSTANT)
        oy, ox = cor[1] - y0, cor[0] - x0
        hh, ww = wr.shape[:2]
        ry0, rx0 = max(0, oy), max(0, ox)
        ry1, rx1 = min(Ch, oy + hh), min(Cw, ox + ww)
        if ry1 <= ry0 or rx1 <= rx0:
            continue
        sr = wr[ry0 - oy:ry1 - oy, rx0 - ox:rx1 - ox]
        sm = wm[ry0 - oy:ry1 - oy, rx0 - ox:rx1 - ox] > 0.5
        acc[ry0:ry1, rx0:rx1] += np.where(sm, sr, 0)
        cov[ry0:ry1, rx0:rx1] += sm
        used += 1

    mean = np.where(cov >= a.min_cover, acc / np.maximum(cov, 1), 0.0)
    if mean.max() > 0:
        mean = mean / np.percentile(mean[mean > 0], 99.5)
    mean = np.clip(mean, 0, 1)
    cv2.imwrite(a.out_image, (mean * 255).astype(np.uint8))
    doc = {"job": "D-A step 3a: warped line-response map",
           "frames_used": used, "canvas": [Cw, Ch],
           "covered_frac": round(float((cov >= a.min_cover).mean()), 3),
           "median_cover": int(np.median(cov[cov > 0])) if (cov > 0).any() else 0,
           "frac_above_0.35": round(float((mean > 0.35).mean()), 5)}
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
