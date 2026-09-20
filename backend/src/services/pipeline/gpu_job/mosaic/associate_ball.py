#!/usr/bin/env python3
"""D-B step 6 — pick the ball out of the candidates, and TEST whether it worked.

G1's caveat is the whole reason this step exists: a COCO `sports ball` detection at
conf>0.05 also fires on heads and line markings, so a per-frame top-1 is not the ball
and its 0.83 "detection rate" is candidate presence, not tracking accuracy. What
distinguishes the ball is not any single frame -- it is that the ball MOVES LIKE A
BALL. So the choice is made over the whole sequence at once, by Viterbi:

    emission   -log(confidence)           -- trust the detector a little
    transition displacement in panorama   -- trust continuity a lot

Panorama coordinates are what make the transition term meaningful: they are angular and
fixed for the whole match, so a displacement means the same thing whether the virtual
camera was panning, zoomed in, or still. In raw frame coordinates a stationary ball
moves whenever the camera does.

**The test.** A trajectory that looks smooth can still be smoothly wrong, so it is
scored against ground truth rather than admired. Veo gives a pitch-length coordinate
`x` for 355 events, and panorama azimuth is a monotone function of position along the
pitch. The frame centre alone already achieves corr(veo_x, azimuth) = **+0.904**
(measured in step 3c), so that is the number to beat: if associating the ball does not
beat the camera's own aim, the association has added nothing.

Reports the correlation, the baseline, and the step statistics. Draws no conclusion the
numbers do not support.
"""
import argparse, csv, json, math
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapped", required=True, help="from map_ball_to_panorama.py")
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-track", default=None)
    ap.add_argument("--vmax-px-s", type=float, default=900.0,
                    help="panorama px/s; ~30 m/s at 40 m is ~850 px/s at this scale")
    ap.add_argument("--w-conf", type=float, default=1.0)
    ap.add_argument("--max-gap-s", type=float, default=3.0,
                    help="beyond this the sequence is cut; continuity means nothing")
    ap.add_argument("--event-tol-s", type=float, default=1.0)
    ap.add_argument("--frame-centres", default=None,
                    help="play_points.json; lets the baseline be computed on the SAME "
                         "events rather than quoting 0.904 from a different subset")
    a = ap.parse_args()

    C = json.loads(Path(a.cameras).read_text())
    scale, (x0, y0) = float(C["scale"]), C["origin"]
    M = json.loads(Path(a.mapped).read_text())
    fr = [f for f in M["tracks"] if f["c"]]
    fr.sort(key=lambda f: f["t"])

    # split into runs with no long gap
    runs, cur = [], []
    for f in fr:
        if cur and f["t"] - cur[-1]["t"] > a.max_gap_s:
            runs.append(cur)
            cur = []
        cur.append(f)
    if cur:
        runs.append(cur)

    track = []
    for run in runs:
        n = len(run)
        cost = [None] * n
        back = [None] * n
        c0 = np.array([-math.log(max(c[3], 1e-6)) for c in run[0]["c"]]) * a.w_conf
        cost[0] = c0
        for k in range(1, n):
            dt = max(run[k]["t"] - run[k - 1]["t"], 1e-3)
            prev = np.array([[c[0], c[1]] for c in run[k - 1]["c"]])
            curp = np.array([[c[0], c[1]] for c in run[k]["c"]])
            d = np.linalg.norm(curp[:, None, :] - prev[None, :, :], axis=2)
            # Huber on displacement normalised by the plausible travel in dt
            z = d / max(a.vmax_px_s * dt, 1e-6)
            trans = np.where(z <= 1.0, z ** 2, 2 * z - 1.0)
            emis = np.array([-math.log(max(c[3], 1e-6)) for c in run[k]["c"]]) * a.w_conf
            tot = trans + cost[k - 1][None, :]
            back[k] = np.argmin(tot, axis=1)
            cost[k] = tot[np.arange(len(curp)), back[k]] + emis
        j = int(np.argmin(cost[n - 1]))
        idx = [0] * n
        idx[n - 1] = j
        for k in range(n - 1, 0, -1):
            idx[k - 1] = int(back[k][idx[k]])
        for k, f in enumerate(run):
            c = f["c"][idx[k]]
            track.append({"t": f["t"], "u": c[0], "v": c[1], "size": c[2], "conf": c[3]})

    track.sort(key=lambda p: p["t"])
    T = np.array([p["t"] for p in track])
    Uu = np.array([p["u"] for p in track])
    Vv = np.array([p["v"] for p in track])
    dT = np.diff(T)
    step = np.hypot(np.diff(Uu), np.diff(Vv))
    ok = dT <= a.max_gap_s
    speed = step[ok] / dT[ok]

    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    ev = [(int(r["video_time_ms"]) / 1000.0, float(r["x"]))
          for r in csv.DictReader(open(bench)) if r["x"]]

    fc = {}
    if a.frame_centres:
        for q in json.loads(Path(a.frame_centres).read_text()):
            if q.get("veo_x") is not None:
                fc[round(q["t"], 3)] = q["u"]

    xs, az, bx, baz = [], [], [], []
    for t, vx in ev:
        k = int(np.argmin(np.abs(T - t)))
        if abs(T[k] - t) > a.event_tol_s:
            continue
        xs.append(vx)
        az.append((Uu[k] + x0) / scale)
        # paired baseline: the camera's own aim at the very same event
        key = min(fc, key=lambda z: abs(z - t)) if fc else None
        if key is not None and abs(key - t) <= a.event_tol_s:
            bx.append(vx)
            baz.append((fc[key] + x0) / scale)
    corr = float(np.corrcoef(xs, az)[0, 1]) if len(xs) > 3 else None
    base_paired = float(np.corrcoef(bx, baz)[0, 1]) if len(bx) > 3 else None

    doc = {
        "job": "D-B step 6: ball association by Viterbi, and its test",
        "frames_with_candidates": len(fr), "runs": len(runs),
        "track_points": len(track),
        "step_px_per_s": {
            "median": round(float(np.median(speed)), 1) if speed.size else None,
            "p90": round(float(np.percentile(speed, 90)), 1) if speed.size else None,
            "frac_over_vmax": round(float((speed > a.vmax_px_s).mean()), 4)
            if speed.size else None,
        },
        "validation": {
            "events_matched": len(xs), "tolerance_s": a.event_tol_s,
            "corr_veo_x_vs_ball_azimuth": round(corr, 4) if corr is not None else None,
            "baseline_frame_centre_paired": (round(base_paired, 4)
                                             if base_paired is not None else None),
            "baseline_frame_centre_step3c": 0.904,
            "paired_events": len(bx),
            "beats_camera_aim": (corr is not None and base_paired is not None
                                 and corr > base_paired),
            "what_this_means": (
                "the frame centre is where the virtual camera pointed; beating it means "
                "the associated candidate carries information the camera's aim does not"),
        },
    }
    if a.out_track:
        Path(a.out_track).write_text(json.dumps(track))
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
