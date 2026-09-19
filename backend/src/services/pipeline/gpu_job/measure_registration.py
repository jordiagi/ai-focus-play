#!/usr/bin/env python3
"""G2 feasibility — can frames be registered to each other on this footage?

The design rests on one claim: the physical camera is FIXED and the exported video
is a virtual pan-and-zoom crop of it. If that is true, every frame relates to every
other by a homography, and we can register frames to a small set of anchors, then
calibrate the anchors to the pitch once.

That claim is untested on THIS footage, which has three properties that could break
feature matching:
  * grass is texture-poor
  * two overlapping line systems (white match lines + a blue layout for another field)
  * heavy zoom variation as the virtual camera follows the ball

So measure before building. This reports, as a function of time separation, how many
RANSAC inliers a SIFT homography finds between frame pairs. The answer decides whether
one anchor suffices, how many anchors are needed, or whether the approach fails.

Reports the number whatever it is. A low inlier count here is a real finding, not a
failure to work around.
"""
import argparse, itertools, json, subprocess, sys, time
from pathlib import Path


def grab(video, t, out, scale=1.0):
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out
    vf = f"scale=iw*{scale}:ih*{scale}" if scale != 1.0 else "null"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t), "-i", str(video),
                    "-frames:v", "1", "-vf", vf, "-q:v", "2", str(out)], check=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--t0", type=float, default=600)
    ap.add_argument("--t1", type=float, default=6100)
    ap.add_argument("--step", type=float, default=120, help="sample spacing in seconds")
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--frames-dir", default="/workspace/aifp/frames/reg")
    ap.add_argument("--out", default="/workspace/aifp/out/registration.json")
    ap.add_argument("--min-inliers", type=int, default=30,
                    help="what we'll call a usable registration")
    a = ap.parse_args()

    import cv2, numpy as np

    times = [a.t0 + i * a.step for i in range(int((a.t1 - a.t0) / a.step) + 1)]
    fdir = Path(a.frames_dir)
    paths = [grab(Path(a.video), t, fdir / f"{int(t):06d}.jpg", a.scale) for t in times]

    sift = cv2.SIFT_create(nfeatures=4000)
    feats = {}
    t_start = time.time()
    for t, p in zip(times, paths):
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        kp, des = sift.detectAndCompute(img, None)
        feats[t] = (kp, des)
    t_feat = time.time() - t_start

    bf = cv2.BFMatcher()

    def pair(ta, tb):
        ka, da = feats[ta]; kb, db = feats[tb]
        if da is None or db is None or len(ka) < 8 or len(kb) < 8:
            return 0, None
        knn = bf.knnMatch(da, db, k=2)
        good = [m for m, n in (p for p in knn if len(p) == 2) if m.distance < 0.75 * n.distance]
        if len(good) < 8:
            return 0, None
        src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
        if H is None or mask is None:
            return 0, None
        return int(mask.sum()), H

    # inliers as a function of time separation
    by_sep = {}
    t_start = time.time()
    for i, ta in enumerate(times):
        for j in range(i + 1, min(i + 1 + 8, len(times))):   # up to 8 steps apart
            tb = times[j]
            sep = round(tb - ta)
            n, _ = pair(ta, tb)
            by_sep.setdefault(sep, []).append(n)
    t_match = time.time() - t_start

    sep_stats = {}
    for sep, vals in sorted(by_sep.items()):
        v = sorted(vals)
        sep_stats[sep] = {
            "pairs": len(v),
            "median_inliers": v[len(v) // 2],
            "min": v[0], "max": v[-1],
            "usable_frac": round(sum(1 for x in v if x >= a.min_inliers) / len(v), 3),
        }

    # FULL pairwise matrix -> how many anchors are needed for good coverage?
    # Inliers do not decay with time separation, so the constraint is view OVERLAP,
    # not drift. That makes anchor selection a set-cover problem over the pan range.
    t_start = time.time()
    M = {}
    for ta, tb in itertools.combinations(times, 2):
        n, _ = pair(ta, tb)
        M[(ta, tb)] = n; M[(tb, ta)] = n
    t_full = time.time() - t_start

    def covers(anchor):
        return {t for t in times if t != anchor and M.get((anchor, t), 0) >= a.min_inliers}

    remaining = set(times)
    chosen, curve = [], []
    while remaining and len(chosen) < 12:
        best = max(times, key=lambda t: len(covers(t) & remaining))
        gain = covers(best) & remaining
        if not gain:
            break
        chosen.append(best)
        remaining -= gain
        remaining.discard(best)
        curve.append({"anchors": len(chosen), "anchor_t": best,
                      "covered": len(times) - len(remaining),
                      "coverage_frac": round((len(times) - len(remaining)) / len(times), 3)})
    greedy = {"curve": curve, "uncovered_after": sorted(remaining),
              "seconds": round(t_full, 1)}

    # how well does ONE anchor cover the match?
    mid = times[len(times) // 2]
    anchor = {str(int(t)): pair(mid, t)[0] for t in times if t != mid}
    covered = sum(1 for v in anchor.values() if v >= a.min_inliers)

    kp_counts = [len(feats[t][0]) for t in times]
    doc = {
        "job": "G2 registration feasibility",
        "frames_sampled": len(times), "span_s": [a.t0, a.t1], "step_s": a.step,
        "scale": a.scale, "min_inliers_usable": a.min_inliers,
        "keypoints": {"median": sorted(kp_counts)[len(kp_counts)//2],
                      "min": min(kp_counts), "max": max(kp_counts)},
        "by_time_separation": sep_stats,
        "greedy_anchors": greedy,
        "single_anchor": {
            "anchor_t": mid,
            "covered_frames": covered, "of": len(anchor),
            "coverage_frac": round(covered / len(anchor), 3),
        },
        "seconds": {"features": round(t_feat, 1), "matching": round(t_match, 1)},
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
