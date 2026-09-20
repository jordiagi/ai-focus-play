#!/usr/bin/env python3
"""D-B step 7 — score the ball track against a position we know from PHYSICS.

The obvious validation is contaminated and must not be used: correlating the track's
panorama azimuth with Veo's pitch coordinate, against the camera's aim as baseline,
compares two outputs of Veo's OWN ball tracker. It asks an independent detector to beat
Veo at reproducing Veo, and every selector duly lost in a suspiciously tight 0.82-0.88
band.

A kickoff is uncontaminated ground truth: the ball is **on the centre spot**, whose
panorama position comes from the fitted centre circle. Nothing from Veo's tracker
enters.

Two refinements over the first pass:

* Score the window BEFORE the whistle, where the ball is placed and stationary. At
  5 fps a +/-0.1 s timing error moves a just-kicked ball a metre or two, so the earlier
  number confounded detection error with sampling.
* Report the distance for the track's own choice, never the nearest of several
  candidates -- nearest-of-five is oracle selection and flatters the result.

The control is the same track sampled at arbitrary times: if being near the centre spot
at kickoff is not much better than being near it in general, the track knows nothing.
"""
import argparse, csv, json, math
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--centre-uv", type=float, nargs=2, default=[2135.7, 519.6],
                    help="centre spot in panorama px (from the fitted centre circle)")
    ap.add_argument("--px-per-m", type=float, default=284.0 / 9.15,
                    help="the circle's semi-major axis is ~284 px for its 9.15 m radius")
    ap.add_argument("--pre", type=float, default=1.5, help="window start, s BEFORE the event")
    ap.add_argument("--post", type=float, default=0.2, help="window end, s before the event")
    a = ap.parse_args()

    CX, CY = a.centre_uv
    tr = json.loads(Path(a.track).read_text())
    T = np.array([p["t"] for p in tr])
    U = np.array([p["u"] for p in tr])
    V = np.array([p["v"] for p in tr])
    Cf = np.array([p["conf"] for p in tr])

    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    ko = sorted(int(r["video_time_ms"]) / 1000.0
                for r in csv.DictReader(open(bench))
                if r["event_type"] == "FootballKickOff")

    rows, d_all = [], []
    for t in ko:
        m = (T >= t - a.pre) & (T <= t - a.post)
        if not m.any():
            rows.append({"t": round(t, 1), "points": 0})
            continue
        d = np.hypot(U[m] - CX, V[m] - CY)
        rows.append({"t": round(t, 1), "points": int(m.sum()),
                     "median_px": round(float(np.median(d)), 1),
                     "median_m": round(float(np.median(d)) / a.px_per_m, 2),
                     "median_conf": round(float(np.median(Cf[m])), 3)})
        d_all.append(float(np.median(d)))

    ctrl = np.hypot(U - CX, V - CY)
    doc = {
        "job": "D-B step 7: ball track vs the centre spot at kickoff",
        "why_not_the_obvious_test": (
            "correlating track azimuth with Veo's x against the camera's aim compares "
            "two outputs of Veo's own tracker -- contaminated, and every selector lost "
            "in a tight 0.82-0.88 band"),
        "window": {"from_s_before": a.pre, "to_s_before": a.post,
                   "reason": "ball is placed and stationary; removes the timing confound"},
        "track_points": len(tr),
        "kickoffs": len(ko), "kickoffs_covered": len(d_all),
        "per_kickoff": rows,
        "median_of_kickoff_medians_px": round(float(np.median(d_all)), 1) if d_all else None,
        "median_of_kickoff_medians_m": (round(float(np.median(d_all)) / a.px_per_m, 2)
                                        if d_all else None),
        "control_any_time_px": round(float(np.median(ctrl)), 1),
        "control_any_time_m": round(float(np.median(ctrl)) / a.px_per_m, 1),
        "caveat": ("n is the number of kickoffs in the match. Small. The centre spot "
                   "itself comes from an ellipse fit and carries its own error."),
    }
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps({k: v for k, v in doc.items() if k != "per_kickoff"}, indent=1))
    print("\nper kickoff:")
    for r in rows:
        print("  " + json.dumps(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
