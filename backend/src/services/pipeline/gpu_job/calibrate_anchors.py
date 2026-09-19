#!/usr/bin/env python3
"""G2 — calibrate anchor frames to pitch metres using Veo's restart events.

No manual clicking. Veo's own events ARE the calibration rig: at a restart the ball
sits at a pitch location we know exactly, and we know the video time. So:

  1. grab the frame at each restart event
  2. detect the ball (tiled inference; measured at ~0.83 on this footage)
  3. register that frame to its best-matching anchor  -> ball pixel in ANCHOR space
  4. per anchor, fit a homography anchor_pixel -> pitch metres from the accumulated
     (pixel, known xz) pairs
  5. validate leave-one-out, and report the error distribution

Restart types used, with the geometry that makes them usable:
  FootballKickOff    ball on the centre spot
  FootballCornerKick ball at a corner
  FootballThrowIn    ball on a touchline
  FootballGoalKick   ball inside a goal area

The honest failure modes, stated up front:
  * at a throw-in the ball is often in the thrower's HANDS, a metre or two infield
  * Veo's own coordinates carry a ~2 m bias (its centre spot lands at 54.5, 34.4 on a
    105x68 model rather than 52.5, 34.0)
  * a ball detection may be a false positive
So the fitted homography inherits several metres of slop. RANSAC absorbs some; the
leave-one-out error reports the rest. This measures whether that is good enough for
the L2 gate (90th-percentile error < 2 m), it does not assume it.
"""
import argparse, csv, json, subprocess, sys, time
from pathlib import Path

RESTART_GEOM = {
    "FootballKickOff": "centre",
    "FootballCornerKick": "corner",
    "FootballThrowIn": "touchline",
    "FootballGoalKick": "goal_area",
}


def grab(video, t, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", "-q:v", "2", str(out)], check=True)
    return out


def tiles_for(w, h, top_frac, nx, ny, overlap):
    top = int(h * top_frac); ph = h - top
    tw, th = w // nx, ph // ny
    ox, oy = int(tw * overlap), int(th * overlap)
    out = []
    for iy in range(ny):
        for ix in range(nx):
            out.append((max(0, ix*tw-ox), max(top, top+iy*th-oy),
                        min(w, (ix+1)*tw+ox), min(h, top+(iy+1)*th+oy)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--events", required=True, help="veo_events_447.csv")
    ap.add_argument("--anchors", required=True, help="comma-separated anchor times in seconds")
    ap.add_argument("--pitch", default="105,68")
    ap.add_argument("--model", default="yolo11x.pt")
    ap.add_argument("--conf", type=float, default=0.05)
    ap.add_argument("--frames-dir", default="/workspace/aifp/frames/calib")
    ap.add_argument("--out", default="/workspace/aifp/out/calibration.json")
    ap.add_argument("--device", default="0")
    ap.add_argument("--min-inliers", type=int, default=100,
                    help="MEASURED: registrations near 30 inliers round-trip at 36-52 px "
                         "(garbage); >=70 round-trips under 2 px. 30 was far too permissive "
                         "and poisoned the first calibration attempt.")
    ap.add_argument("--all-events", action="store_true",
                    help="use every coordinate-bearing event, not just restarts. Restarts "
                         "have precise ball positions but individually degenerate geometry "
                         "(goal kicks singular-value ratio 0.101, kickoffs 0.148); the full "
                         "set is 6x larger and well spread (0.668).")
    a = ap.parse_args()

    import cv2, numpy as np, torch
    from ultralytics import YOLO

    PL, PW = [float(x) for x in a.pitch.split(",")]
    anchors_t = [float(x) for x in a.anchors.split(",")]
    dev = f"cuda:{a.device}" if torch.cuda.is_available() else "cpu"
    if dev.startswith("cuda"):
        torch.cuda.set_per_process_memory_fraction(0.30, int(a.device))

    rows = [r for r in csv.DictReader(open(a.events))
            if r["x"] and r["z"] and (a.all_events or r["event_type"] in RESTART_GEOM)]
    print(f"restart events with coordinates: {len(rows)}", file=sys.stderr)

    fdir = Path(a.frames_dir)
    model = YOLO(a.model)
    BALL = 32
    sift = cv2.SIFT_create(nfeatures=4000)
    bf = cv2.BFMatcher()

    # anchor features
    anchor_feat = {}
    for t in anchors_t:
        p = grab(Path(a.video), t, fdir / f"anchor_{int(t):06d}.jpg")
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        anchor_feat[t] = sift.detectAndCompute(img, None)

    def detect_ball(img):
        """Best ball candidate in full-frame pixel coords, via tiled inference."""
        h, w = img.shape[:2]
        best, bestc = None, 0.0
        for (x0, y0, x1, y1) in tiles_for(w, h, 0.22, 3, 2, 0.15):
            crop = img[y0:y1, x0:x1]
            r = model.predict(crop, imgsz=640, conf=a.conf, classes=[BALL],
                              device=dev, half=True, verbose=False)[0]
            if r.boxes is None or len(r.boxes) == 0:
                continue
            cf = r.boxes.conf.cpu().numpy()
            xy = r.boxes.xywh.cpu().numpy()
            k = int(cf.argmax())
            if float(cf[k]) > bestc:
                bestc = float(cf[k]); best = (x0 + float(xy[k][0]), y0 + float(xy[k][1]))
        return best, bestc

    def register(img_gray, anchor_t):
        ka, da = anchor_feat[anchor_t]
        kb, db = sift.detectAndCompute(img_gray, None)
        if db is None or da is None or len(kb) < 8:
            return None, 0
        knn = bf.knnMatch(db, da, k=2)
        good = [m for m, n in (p for p in knn if len(p) == 2) if m.distance < 0.75*n.distance]
        if len(good) < 8:
            return None, 0
        src = np.float32([kb[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([ka[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
        if H is None or mask is None:
            return None, 0
        return H, int(mask.sum())

    per_anchor = {t: [] for t in anchors_t}
    diag = {"events": len(rows), "ball_found": 0, "registered": 0, "assigned": 0}
    t_start = time.time()
    for r in rows:
        vt = int(r["video_time_ms"]) / 1000.0
        p = grab(Path(a.video), vt, fdir / f"ev_{int(vt*1000):08d}.jpg")
        img = cv2.imread(str(p))
        if img is None:
            continue
        ball, bc = detect_ball(img)
        if ball is None:
            continue
        diag["ball_found"] += 1
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        best_t, best_n, best_H = None, 0, None
        for t in anchors_t:
            H, n = register(gray, t)
            if n > best_n:
                best_t, best_n, best_H = t, n, H
        if best_H is None or best_n < a.min_inliers:
            continue
        diag["registered"] += 1
        pt = np.array([[[ball[0], ball[1]]]], dtype=np.float32)
        ax, ay = cv2.perspectiveTransform(pt, best_H)[0][0]
        per_anchor[best_t].append({
            "video_s": vt, "type": r["event_type"], "team": r["team"],
            "anchor_px": [float(ax), float(ay)],
            "pitch_m": [float(r["x"]) * PL, float(r["z"]) * PW],
            "ball_conf": bc, "inliers": best_n,
        })
        diag["assigned"] += 1
    diag["seconds"] = round(time.time() - t_start, 1)

    # fit + leave-one-out validate per anchor
    fits = {}
    for t, pts in per_anchor.items():
        if len(pts) < 6:
            fits[str(int(t))] = {"n_points": len(pts),
                                 "status": "insufficient", "note": "need >=6 correspondences"}
            continue
        src = np.float32([p["anchor_px"] for p in pts]).reshape(-1, 1, 2)
        dst = np.float32([p["pitch_m"] for p in pts]).reshape(-1, 1, 2)
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
        errs = []
        for i in range(len(pts)):
            keep = [j for j in range(len(pts)) if j != i]
            if len(keep) < 5:
                continue
            Hi, _ = cv2.findHomography(src[keep], dst[keep], cv2.RANSAC, 3.0)
            if Hi is None:
                continue
            pred = cv2.perspectiveTransform(src[i:i+1], Hi)[0][0]
            errs.append(float(np.hypot(pred[0]-dst[i][0][0], pred[1]-dst[i][0][1])))
        errs_sorted = sorted(errs)
        fits[str(int(t))] = {
            "n_points": len(pts),
            "ransac_inliers": int(mask.sum()) if mask is not None else 0,
            "H": H.tolist() if H is not None else None,
            "loo_median_err_m": round(errs_sorted[len(errs_sorted)//2], 2) if errs_sorted else None,
            "loo_p90_err_m": round(errs_sorted[int(0.9*len(errs_sorted))-1], 2) if len(errs_sorted) >= 10 else None,
            "loo_max_err_m": round(errs_sorted[-1], 2) if errs_sorted else None,
            "status": "fitted",
        }

    doc = {"job": "G2 anchor calibration from Veo restart events",
           "anchors_s": anchors_t, "pitch_m": [PL, PW],
           "diagnostics": diag, "fits": fits,
           "gate": {"requires": "90th-percentile error < 2 m",
                    "note": "leave-one-out; inherits Veo's own ~2 m coordinate bias and "
                            "the throw-in-in-hands offset, so this is a PESSIMISTIC estimate "
                            "of our homography's own error"}}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps({"diagnostics": diag,
                      "fits": {k: {kk: vv for kk, vv in v.items() if kk != "H"}
                               for k, v in fits.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
