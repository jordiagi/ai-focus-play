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
    ap.add_argument("--ball-frame", default=None,
                    help="ball.json in FRAME coords; enables the frame-centre prior")
    ap.add_argument("--w-centre", type=float, default=0.0,
                    help="weight on distance from frame centre. The export is a "
                         "ball-following crop, so the camera's aim is evidence about "
                         "where the ball is -- ignoring it threw away the strongest "
                         "signal available, and the first run lost to it 0.833 vs 0.908")
    ap.add_argument("--max-skip", type=int, default=10,
                    help="frames the tracker may decline in a row (the miss state)")
    ap.add_argument("--miss-cost", type=float, default=1.2,
                    help="cost per declined frame; too low and it tracks nothing, too "
                         "high and it is forced onto false positives again")
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

    # frame-centre prior: candidate order is preserved by the mapping step, so the
    # i-th panorama candidate is the i-th frame-space candidate
    prior = {}
    if a.ball_frame and a.w_centre > 0:
        B = json.loads(Path(a.ball_frame).read_text())
        fw, fh = B["config"]["frame_wh"]
        for d in B["detections"]:
            if not d["c"]:
                continue
            prior[round(d["t"], 3)] = [
                math.hypot(c[0] - fw / 2.0, c[1] - fh / 2.0) / (fw / 2.0)
                for c in d["c"]]

    # split into runs with no long gap
    runs, cur = [], []
    for f in fr:
        if cur and f["t"] - cur[-1]["t"] > a.max_gap_s:
            runs.append(cur)
            cur = []
        cur.append(f)
    if cur:
        runs.append(cur)

    def emis_of(f):
        e = np.array([-math.log(max(c[3], 1e-6)) for c in f["c"]]) * a.w_conf
        pv = prior.get(round(f["t"], 3))
        if pv is not None and len(pv) == len(e):
            e = e + a.w_centre * np.asarray(pv) ** 2
        return e

    # Viterbi WITH an explicit miss state, expressed as skip-transitions.
    #
    # The first version had to pick a candidate in every frame. At conf>=0.45 only 47%
    # of frames hold a plausible candidate, so in most frames it was forced to take a
    # false positive -- which is exactly what produced a jump. 13.6% of steps above
    # plausible ball speed was in fact LOW for a tracker that cannot decline.
    #
    # Here a state is (frame, candidate) and a transition may skip up to `max-skip`
    # frames at a per-frame cost. Skipped frames are misses: the tracker declines them
    # rather than inventing a position, and the motion term is scored over the true
    # elapsed time rather than a single frame step.
    # Viterbi WITH an explicit miss state.
    #
    # The first version had to pick a candidate in EVERY frame. At conf>=0.45 only 47%
    # of frames hold a plausible candidate, so in most frames it was forced onto a
    # false positive -- which is what produced the jumps. 13.6% of steps above
    # plausible ball speed was in fact LOW for a tracker that cannot decline.
    #
    # A state is (frame, candidate); a transition may skip frames at `miss_cost` each.
    # Virtual START and END nodes make the path span the whole run, so the result is a
    # full labelling -- assign or decline -- rather than one chain. Without them the
    # cheapest path is a single frame, which is exactly what the first attempt returned
    # (37 points from 18,752 frames).
    #
    # miss_cost is the decision threshold in disguise: a candidate is worth taking when
    # -log(conf) is below it, so 1.2 means "assign above conf ~0.30".
    track = []
    for run in runs:
        n = len(run)
        pos = [np.array([[c[0], c[1]] for c in f["c"]], float) for f in run]
        emis = [emis_of(f) for f in run]
        best = [emis[k] + a.miss_cost * k for k in range(n)]   # from START
        bptr = [[(-1, -1)] * len(e) for e in emis]
        for k in range(1, n):
            tk = run[k]["t"]
            for j0 in range(max(0, k - a.max_skip), k):
                dt = tk - run[j0]["t"]
                if dt <= 0 or dt > a.max_gap_s:
                    continue
                d = np.linalg.norm(pos[k][:, None, :] - pos[j0][None, :, :], axis=2)
                z = d / max(a.vmax_px_s * dt, 1e-6)
                trans = np.where(z <= 1.0, z ** 2, 2 * z - 1.0)
                trans = trans + a.miss_cost * (k - j0 - 1)
                tot = trans + best[j0][None, :]
                am = np.argmin(tot, axis=1)
                val = tot[np.arange(len(pos[k])), am] + emis[k]
                for ci in np.nonzero(val < best[k])[0]:
                    best[k][ci] = val[ci]
                    bptr[k][ci] = (j0, int(am[ci]))
        # to END: pay for the frames skipped after k
        fin = [best[k] + a.miss_cost * (n - 1 - k) for k in range(n)]
        endk = int(np.argmin([f.min() for f in fin]))
        endc = int(np.argmin(fin[endk]))
        k, ci = endk, endc
        chain = []
        while k >= 0:
            chain.append((k, ci))
            k, ci = bptr[k][ci]
        for k, ci in reversed(chain):
            c = run[k]["c"][ci]
            track.append({"t": run[k]["t"], "u": c[0], "v": c[1],
                          "size": c[2], "conf": c[3]})

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
        "w_centre": a.w_centre, "w_conf": a.w_conf,
        "max_skip": a.max_skip, "miss_cost": a.miss_cost,
        "frames_with_candidates": len(fr), "runs": len(runs),
        "frames_declined": len(fr) - len(track),
        "coverage": round(len(track) / max(len(fr), 1), 4),
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
