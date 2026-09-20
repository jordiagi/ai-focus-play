#!/usr/bin/env python3
"""D-B step 8 — the first Tier A detector: FootballOutOfPlay, scored.

64 events, the largest Tier A type, and it needs **no metres**: what marks the ball
going out is a pattern in the ball's own motion, measured in panorama pixels.

The signature was measured before anything was built (medians over the 64 events
against 600 random in-play times):

| window | at OutOfPlay | at random |
| :-- | --: | --: |
| ball speed, [-1, +0.5] s | **196 px/s** | 77 |
| track coverage, [+0.5, +3.5] s | **0.20** | 0.53 |
| ball speed, [+2, +6] s | **35 px/s** | 93 |

Which is exactly the physical story: the ball is struck hard, leaves the field, stops
being detectable, and then sits still while someone fetches it. Every one of the 64 is
followed by a restart (38 throw-ins, 16 goal kicks, 9 corners), a median 17 s later.

Note the middle row is a *detector failure* used as a feature: coverage collapses
because the ball has left the region the tracker can follow. That is legitimate here --
the collapse is caused by the event -- but it means the feature is only as stable as
the tracker, and a better tracker would weaken it.

**Protocol.** The threshold is fitted on period 1 and applied unchanged to period 2,
which is reported separately; the manifest declares `tuned_on: period1`. Team is NOT
predicted, so the team-aware figure is 0 by construction and the honest headline is the
team-agnostic one.
"""
import argparse, csv, json, math
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--min-sep", type=float, default=8.0)
    ap.add_argument("--p1", type=float, nargs=2, default=[562.3, 2879.3])
    ap.add_argument("--p2", type=float, nargs=2, default=[3674.4, 6132.1])
    a = ap.parse_args()

    tr = json.loads(Path(a.track).read_text())
    T = np.array([p["t"] for p in tr])
    U = np.array([p["u"] for p in tr])
    V = np.array([p["v"] for p in tr])
    dt = np.diff(T)
    d = np.hypot(np.diff(U), np.diff(V))
    ok = (dt > 0) & (dt < 1.0)
    st, sv = T[1:][ok], d[ok] / dt[ok]

    grid = np.concatenate([np.arange(a.p1[0], a.p1[1], 1.0 / a.fps),
                           np.arange(a.p2[0], a.p2[1], 1.0 / a.fps)])

    def med_in(lo, hi):
        out = np.full(len(grid), np.nan)
        for i, t in enumerate(grid):
            m = (st >= t + lo) & (st <= t + hi)
            if m.any():
                out[i] = np.median(sv[m])
        return out

    def cov_in(lo, hi):
        exp = (hi - lo) * a.fps
        return np.array([((T >= t + lo) & (T <= t + hi)).sum() / exp for t in grid])

    s_pre = med_in(-1.0, 0.5)
    c_post = cov_in(0.5, 3.5)
    s_post = med_in(2.0, 6.0)

    def rank(x):
        r = np.full(len(x), np.nan)
        m = ~np.isnan(x)
        if m.sum() < 10:
            return np.zeros(len(x))
        order = np.argsort(np.argsort(x[m]))
        r[m] = order / max(m.sum() - 1, 1)
        return np.nan_to_num(r, nan=0.5)

    score = rank(s_pre) + (1 - rank(c_post)) + (1 - rank(s_post))

    # non-max suppression
    idx = np.argsort(-score)
    picked = []
    for i in idx:
        t = grid[i]
        if all(abs(t - grid[j]) >= a.min_sep for j in picked):
            picked.append(i)
        if len(picked) >= 400:
            break
    picked = np.array(sorted(picked, key=lambda j: grid[j]))
    cand_t, cand_s = grid[picked], score[picked]

    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    ref = sorted(int(r["video_time_ms"]) / 1000.0
                 for r in csv.DictReader(open(bench))
                 if r["event_type"] == "FootballOutOfPlay")
    ref = np.array(ref)
    TOL = 3.0
    dur = (a.p1[1] - a.p1[0]) + (a.p2[1] - a.p2[0])

    def prf(pred_t, ref_t):
        if len(pred_t) == 0 or len(ref_t) == 0:
            return 0.0, 0.0, 0.0, 0
        used, tp = set(), 0
        for r in ref_t:
            best, bj = None, None
            for j, p in enumerate(pred_t):
                if j in used:
                    continue
                dd = abs(p - r)
                if dd <= TOL and (best is None or dd < best):
                    best, bj = dd, j
            if bj is not None:
                used.add(bj)
                tp += 1
        prec = tp / len(pred_t)
        rec = tp / len(ref_t)
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return prec, rec, f1, tp

    in1 = lambda x: (x >= a.p1[0]) & (x <= a.p1[1])
    ref1, ref2 = ref[in1(ref)], ref[~in1(ref)]

    # fit the threshold on PERIOD 1 only
    best = None
    for thr in np.unique(np.round(cand_s, 3)):
        p1 = cand_t[(cand_s >= thr) & in1(cand_t)]
        pr, rc, f1, tp = prf(p1, ref1)
        if best is None or f1 > best[0]:
            best = (f1, thr, pr, rc, tp, len(p1))
    f1_1, thr, pr1, rc1, tp1, n1 = best

    sel = cand_s >= thr
    pred_t = cand_t[sel]
    p2 = pred_t[~in1(pred_t)]
    pr2, rc2, f1_2, tp2 = prf(p2, ref2)
    pra, rca, f1a, tpa = prf(pred_t, ref)

    def chance(n, k):
        p = 1 - (1 - 2 * TOL / dur) ** max(n, 0)
        return p

    doc = {
        "job": "D-B step 8: FootballOutOfPlay detector",
        "protocol": {"threshold_fitted_on": "period1", "applied_unchanged_to": "period2",
                     "tolerance_s": TOL, "min_sep_s": a.min_sep,
                     "team": "NOT predicted -- team-aware scoring is 0 by construction"},
        "threshold": round(float(thr), 4),
        "period1_dev": {"n_pred": int(n1), "n_ref": int(len(ref1)), "tp": int(tp1),
                        "precision": round(pr1, 4), "recall": round(rc1, 4),
                        "f1": round(f1_1, 4),
                        "recall_expected_by_chance": round(chance(n1, len(ref1)), 4)},
        "period2_heldout": {"n_pred": int(len(p2)), "n_ref": int(len(ref2)), "tp": int(tp2),
                            "precision": round(pr2, 4), "recall": round(rc2, 4),
                            "f1": round(f1_2, 4),
                            "recall_expected_by_chance": round(chance(len(p2), len(ref2)), 4)},
        "both_periods": {"n_pred": int(len(pred_t)), "n_ref": int(len(ref)), "tp": int(tpa),
                         "precision": round(pra, 4), "recall": round(rca, 4),
                         "f1": round(f1a, 4),
                         "recall_expected_by_chance": round(chance(len(pred_t), len(ref)), 4)},
        "dev_heldout_gap_f1": round(f1_1 - f1_2, 4),
    }
    Path(a.pred).write_text(json.dumps({"events": [
        {"video_s": round(float(t), 2), "event_type": "FootballOutOfPlay"}
        for t in pred_t]}, indent=1))
    Path(a.manifest).write_text(json.dumps({
        "attempted": ["FootballOutOfPlay"], "tuned_on": "period1",
        "note": ("team is not predicted for this type, so the team-aware score is 0 by "
                 "construction; read the team-agnostic figure")}, indent=1))
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
