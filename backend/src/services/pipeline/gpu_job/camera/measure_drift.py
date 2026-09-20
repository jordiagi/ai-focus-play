#!/usr/bin/env python3
"""D-0 / D-A — how much does CHAINED frame-to-frame registration drift?

This is the measurement that decided D-0, and it constrains D-A.

D-0 predicted "kickoff = the camera returns to the same central view". Kickoffs are
all taken from the centre circle, so the camera view at each one must be nearly
identical. That makes the 8 benchmark kickoffs a **free physical ground truth for a
repeated view** -- no pitch calibration, no annotation, no labels beyond the kickoff
timestamps Veo already gave us.

So the same quantity can be obtained two ways, and the gap between them is drift:

  DIRECT    register kickoff frame A against kickoff frame B -> the true view offset
  CHAINED   integrate per-pair dx along the trajectory between them -> the estimate

Only pairs at or above the measured reliability gate (>=100 RANSAC inliers; below ~40
is garbage) are counted. An ungated pair's offset is not evidence of anything.

Run `falsify_halftime.py` first to produce the trajectory CSV.
"""
import argparse, csv, itertools, json, subprocess, statistics as st
from pathlib import Path


def grab(video, t, out, width):
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(t), "-i", str(video),
                        "-frames:v", "1", "-vf", f"scale={width}:-1", "-q:v", "2",
                        str(out)], check=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--csv", required=True, help="trajectory CSV from falsify_halftime.py")
    ap.add_argument("--bench", default=None, help="veo_events_447.csv; default = repo copy")
    ap.add_argument("--event-type", default="FootballKickOff")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--nfeatures", type=int, default=4000)
    ap.add_argument("--min-inliers", type=int, default=100)
    ap.add_argument("--frames-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import cv2, numpy as np

    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    times = sorted(int(r["video_time_ms"]) / 1000.0
                   for r in csv.DictReader(open(bench))
                   if r["event_type"] == a.event_type)
    if len(times) < 2:
        raise SystemExit(f"need >=2 {a.event_type} events, found {len(times)}")

    # CHAINED: cumulative pan from the per-pair trajectory
    rows = list(csv.DictReader(open(a.csv)))
    tt, cx, pan = [], 0.0, []
    for r in rows:
        tt.append(float(r["t"]))
        if r["reliable"] == "True":
            cx += float(r["dx"])
        pan.append(cx)

    def chained_at(x):
        return pan[min(range(len(tt)), key=lambda k: abs(tt[k] - x))]

    # DIRECT: register the event frames against each other
    sift = cv2.SIFT_create(nfeatures=a.nfeatures)
    bf = cv2.BFMatcher()
    feats = {}
    for t in times:
        p = grab(Path(a.video), t, Path(a.frames_dir) / f"e{t}.jpg", a.width)
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        kp, des = sift.detectAndCompute(img, None)
        feats[t] = (kp, des, img.shape)

    pairs, gated = [], []
    for x, y in itertools.combinations(times, 2):
        ka, da, (h, w) = feats[x]
        kb, db, _ = feats[y]
        rec = {"a": x, "b": y, "inliers": 0, "direct_px": None,
               "chained_px": round(abs(chained_at(y) - chained_at(x)), 1)}
        knn = bf.knnMatch(da, db, k=2)
        good = [m for m, n in (p for p in knn if len(p) == 2)
                if m.distance < 0.75 * n.distance]
        if len(good) >= 8:
            src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
            if H is not None and mask is not None:
                rec["inliers"] = int(mask.sum())
                c = cv2.perspectiveTransform(
                    np.float32([[w / 2, h / 2]]).reshape(-1, 1, 2), H).reshape(2)
                rec["direct_px"] = round(float(np.hypot(c[0] - w / 2, c[1] - h / 2)), 1)
        pairs.append(rec)
        if rec["inliers"] >= a.min_inliers and rec["direct_px"] is not None:
            gated.append(rec)

    d = [g["direct_px"] for g in gated]
    c = [g["chained_px"] for g in gated]
    doc = {
        "job": "D-0/D-A chained-registration drift vs direct registration",
        "event_type": a.event_type, "n_events": len(times), "event_times": times,
        "min_inliers_gate": a.min_inliers,
        "pairs_total": len(pairs), "pairs_gated": len(gated),
        "direct_offset_px": {"median": round(st.median(d), 1), "min": min(d),
                             "max": max(d)} if d else None,
        "chained_offset_px": {"median": round(st.median(c), 1), "min": min(c),
                              "max": max(c)} if c else None,
        "drift_factor_median": round(st.median(c) / st.median(d), 1) if d and st.median(d) else None,
        "pan_range_px": round(max(pan) - min(pan), 1),
        "interpretation": (
            "All these events are restarts from the centre circle, so the DIRECT "
            "offsets are the true view spread. Any excess in the CHAINED column is "
            "accumulated integration drift."),
        "pairs": pairs,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps({k: v for k, v in doc.items() if k != "pairs"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
