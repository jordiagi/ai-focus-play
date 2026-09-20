#!/usr/bin/env python3
"""D-0 falsification test — does the camera's own motion encode the match state?

D-0 claims this footage's virtual camera followed the ball for 103 minutes, so its
pan/zoom trajectory should already encode where play is and when play stops. Before
building anything on that, `specs/deferred.md` demands one falsification:

    the recovered trajectory MUST show the 795 s halftime gap
    (H1 ends 2879.3, H2 starts 3674.4). If it does not, the idea is wrong.

THE CRITERION IS PRE-REGISTERED (written before the first run, see README):

  C1  discrimination  ROC AUC of per-frame camera speed as a halftime classifier
                      >= 0.80 over the sampled window
  C2  effect size     median in-play speed >= 2x median halftime speed
  C3  localisation    a changepoint found FROM THE SIGNAL ALONE lands within
                      +/-30 s of BOTH 2879.3 and 3674.4

C1+C2 say the two regimes differ. C3 is the one that matters for event detection:
it says the boundary can be RECOVERED, not merely distinguished once you are told
where it is. Reporting all three separately so a partial result stays legible.

No pitch calibration is involved anywhere in this file.
"""
import argparse, csv, json, math, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def extract(video, t0, dur, fps, width, out_dir):
    """One ffmpeg pass. Frame i is at t0 + i/fps."""
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("*.jpg"))
    if existing:
        return existing
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t0), "-i", str(video),
         "-t", str(dur), "-vf", f"fps={fps},scale={width}:-1", "-q:v", "3",
         str(out_dir / "%06d.jpg")], check=True)
    return sorted(out_dir.glob("*.jpg"))


def chunk_pairs(args):
    """Consecutive-pair registration over one contiguous block of frames.

    Blocks overlap by one frame so no pair is dropped at a seam. Features are
    computed inside the worker, so only small result dicts cross the process
    boundary -- passing SIFT descriptors between processes costs more than
    recomputing them.
    """
    paths, idx0, nfeatures = args
    import cv2, numpy as np

    sift = cv2.SIFT_create(nfeatures=nfeatures)
    bf = cv2.BFMatcher()
    out = []
    prev = None
    for k, p in enumerate(paths):
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        kp, des = sift.detectAndCompute(img, None)
        cur = (kp, des, img.shape)
        if prev is not None:
            out.append(register(prev, cur, bf, idx0 + k, cv2, np))
        prev = cur
    return out


def register(a, b, bf, index, cv2, np):
    """Homography A->B, reduced to the two numbers a virtual camera actually has:
    how far the view translated, and how much it zoomed."""
    (ka, da, shape), (kb, db, _) = a, b
    h, w = shape
    rec = {"index": index, "inliers": 0, "matches": 0,
           "dx": None, "dy": None, "zoom": None}
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return rec
    knn = bf.knnMatch(da, db, k=2)
    good = [m for m, n in (p for p in knn if len(p) == 2)
            if m.distance < 0.75 * n.distance]
    rec["matches"] = len(good)
    if len(good) < 8:
        return rec
    src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if H is None or mask is None:
        return rec
    rec["inliers"] = int(mask.sum())

    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    centre = np.float32([[w / 2, h / 2]]).reshape(-1, 1, 2)
    pc = cv2.perspectiveTransform(corners, H).reshape(-1, 2)
    pcen = cv2.perspectiveTransform(centre, H).reshape(2)
    rec["dx"] = float(pcen[0] - w / 2)
    rec["dy"] = float(pcen[1] - h / 2)
    # shoelace area of the projected frame -> linear zoom factor
    area = 0.5 * abs(sum(pc[i][0] * pc[(i + 1) % 4][1] - pc[(i + 1) % 4][0] * pc[i][1]
                         for i in range(4)))
    rec["zoom"] = float(math.sqrt(area / (w * h))) if area > 0 else None
    return rec


def roc_auc(pos, neg):
    """AUC via rank-sum (ties get average rank). pos = halftime (expect LOW speed),
    scored on negated speed so 'higher score = halftime'."""
    if not pos or not neg:
        return None
    data = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks, i = {}, 0
    vals = [d[0] for d in data]
    r = [0.0] * len(data)
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[k] = avg
        i = j + 1
    rsum = sum(r[k] for k in range(len(data)) if data[k][1] == 1)
    n1, n0 = len(pos), len(neg)
    return round((rsum - n1 * (n1 + 1) / 2) / (n1 * n0), 4)


def median(v):
    s = sorted(v)
    if not s:
        return None
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def best_step(times, sig):
    """Cheapest honest changepoint: the single split minimising within-segment
    absolute deviation. Applied to the two halves independently so it can find
    a start AND an end without assuming how many there are."""
    if len(sig) < 4:
        return None
    best, best_cost = None, float("inf")
    for i in range(2, len(sig) - 2):
        l, r = sig[:i], sig[i:]
        ml, mr = median(l), median(r)
        cost = sum(abs(x - ml) for x in l) + sum(abs(x - mr) for x in r)
        if cost < best_cost:
            best_cost, best = cost, times[i]
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--t0", type=float, default=2400.0)
    ap.add_argument("--t1", type=float, default=4200.0)
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--nfeatures", type=int, default=2000)
    ap.add_argument("--min-inliers", type=int, default=100,
                    help="measured reliability gate from G2; below ~40 is garbage")
    ap.add_argument("--h1-end", type=float, default=2879.3)
    ap.add_argument("--h2-start", type=float, default=3674.4)
    ap.add_argument("--tol", type=float, default=30.0, help="C3 localisation tolerance")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()

    t_start = time.time()
    paths = extract(Path(a.video), a.t0, a.t1 - a.t0, a.fps, a.width, Path(a.frames_dir))
    t_extract = time.time() - t_start
    if len(paths) < 10:
        print(f"FATAL: only {len(paths)} frames extracted", file=sys.stderr)
        return 2

    n = len(paths)
    size = max(2, math.ceil(n / a.workers))
    blocks = []
    s = 0
    while s < n - 1:
        e = min(n, s + size + 1)          # +1 so blocks overlap by one frame
        blocks.append((paths[s:e], s, a.nfeatures))
        s = e - 1
    t_start = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        recs = [r for block in ex.map(chunk_pairs, blocks) for r in block]
    t_match = time.time() - t_start
    recs.sort(key=lambda r: r["index"])

    # pair i covers frames i -> i+1; timestamp it at the midpoint
    rows = []
    for r in recs:
        t = a.t0 + (r["index"] + 0.5) / a.fps
        ok = r["inliers"] >= a.min_inliers and r["dx"] is not None
        speed = math.hypot(r["dx"], r["dy"]) * a.fps if ok else None
        zrate = abs(math.log(r["zoom"])) * a.fps if ok and r["zoom"] else None
        rows.append({"t": round(t, 3), "inliers": r["inliers"], "matches": r["matches"],
                     "reliable": ok, "speed_px_s": speed, "zoom_rate": zrate,
                     "dx": r["dx"], "dy": r["dy"], "zoom": r["zoom"]})

    if a.csv:
        Path(a.csv).parent.mkdir(parents=True, exist_ok=True)
        with open(a.csv, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)

    use = [r for r in rows if r["reliable"]]
    ht = [r["speed_px_s"] for r in use if a.h1_end < r["t"] < a.h2_start]
    pl = [r["speed_px_s"] for r in use if r["t"] < a.h1_end or r["t"] > a.h2_start]

    auc = roc_auc([-v for v in ht], [-v for v in pl])
    m_ht, m_pl = median(ht), median(pl)
    ratio = round(m_pl / m_ht, 3) if m_ht else None

    # C3: find the two boundaries from the signal alone. Split the window at its
    # own midpoint and look for one changepoint in each half -- that assumes two
    # boundaries exist but NOT where they are.
    mid = (a.t0 + a.t1) / 2
    left = [r for r in use if r["t"] < mid]
    right = [r for r in use if r["t"] >= mid]
    cp1 = best_step([r["t"] for r in left], [r["speed_px_s"] for r in left])
    cp2 = best_step([r["t"] for r in right], [r["speed_px_s"] for r in right])
    e1 = round(abs(cp1 - a.h1_end), 1) if cp1 else None
    e2 = round(abs(cp2 - a.h2_start), 1) if cp2 else None

    c1 = auc is not None and auc >= 0.80
    c2 = ratio is not None and ratio >= 2.0
    c3 = e1 is not None and e2 is not None and e1 <= a.tol and e2 <= a.tol

    doc = {
        "job": "D-0 falsification: camera motion vs halftime",
        "window_s": [a.t0, a.t1], "sample_fps": a.fps, "frame_width": a.width,
        "frames": n, "pairs": len(rows),
        "min_inliers_gate": a.min_inliers,
        "reliable_pairs": len(use),
        "reliable_frac": round(len(use) / len(rows), 3) if rows else None,
        "inliers_median": median([r["inliers"] for r in rows]),
        "truth": {"h1_end": a.h1_end, "h2_start": a.h2_start,
                  "halftime_s": round(a.h2_start - a.h1_end, 1)},
        "speed_px_s": {
            "halftime": {"n": len(ht), "median": round(m_ht, 2) if m_ht else None},
            "in_play": {"n": len(pl), "median": round(m_pl, 2) if m_pl else None},
        },
        "criteria": {
            "C1_auc": {"value": auc, "threshold": 0.80, "pass": c1},
            "C2_median_ratio": {"value": ratio, "threshold": 2.0, "pass": c2},
            "C3_localisation": {"changepoint_1": cp1, "error_1_s": e1,
                                "changepoint_2": cp2, "error_2_s": e2,
                                "tolerance_s": a.tol, "pass": c3},
        },
        "verdict": ("SURVIVES" if (c1 and c2 and c3)
                    else "PARTIAL" if (c1 and c2) else "FALSIFIED"),
        "seconds": {"extract": round(t_extract, 1), "register": round(t_match, 1)},
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
