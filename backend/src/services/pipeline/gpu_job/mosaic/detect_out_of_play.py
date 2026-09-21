#!/usr/bin/env python3
"""D-B step 8 — the first Tier A detector: FootballOutOfPlay, scored.

64 events, the largest Tier A type, and it needs **no metres**: what marks the ball
going out is a pattern in the ball's own motion, measured in panorama pixels.

The signature, re-measured 2026-09-20 from `ball_track.json` (medians over the 64
events against 600 random in-play times). **An earlier run of this table recorded 196 /
0.20 / 35 against 77 / 0.53 / 93; those numbers do not reproduce** and the script that
produced them was not kept. Every contrast holds in the same direction and roughly the
same size, so the signature is real and the detector below stands, but quote these:

| window | at OutOfPlay | at random | ratio |
| :-- | --: | --: | --: |
| ball speed, [-1, +0.5] s | **267 px/s** | 93 | 2.9x |
| track coverage, [+0.5, +3.5] s | **0.13** | 0.47 | 0.28x |
| ball speed, [+2, +6] s | **42 px/s** | 98 | 0.43x |

Which is exactly the physical story: the ball is struck hard, leaves the field, stops
being detectable, and then sits still while someone fetches it. Every one of the 64 is
followed by a restart (38 throw-ins, 16 goal kicks, 9 corners), a median 17 s later.

Note the middle row is a *detector failure* used as a feature: coverage collapses
because the ball has left the region the tracker can follow. That is legitimate here --
the collapse is caused by the event -- but it means the feature is only as stable as
the tracker, and a better tracker would weaken it.

**Protocol.** `min_sep` is chosen by period-1 F1 over an 8-cell sweep (2,3,4,5,6,8,10,12
-> 5.0 wins at 0.265); the threshold is then fitted on period 1 and applied unchanged to
period 2, which is reported separately; the manifest declares `tuned_on: period1`. Team
is NOT predicted, so the team-aware figure is 0 by construction and the honest headline
is the team-agnostic one.

**The output records the exact command that produced it** (`command` in the score doc).
That is not decoration: the figures this detector reported on 2026-09-20 could not be
reproduced afterwards because the invocation was never written down, and the stored
outputs were overwritten before anyone noticed.
"""
import argparse, csv, json, math, sys
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--restart-pred", default=None,
                    help="pred_restarts.json -- enables team, see below")
    ap.add_argument("--pred", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--min-sep", type=float, default=5.0)  # selected on period 1
    ap.add_argument("--budgets", type=float, nargs="*", default=[1.0, 1.5, 2.0, 3.0],
                    help="candidate n_pred/n_ref caps, smallest first")
    ap.add_argument("--budget-tolerance", type=float, default=0.05,
                    help="period-1 F1 we are willing to give up for a smaller budget")
    ap.add_argument("--restart-window", type=float, default=60.0)
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

    # Fit the threshold on PERIOD 1 only, under a declared PREDICTION BUDGET.
    #
    # Why a budget at all. F1 at a fixed tolerance is gameable when precision is low:
    # emitting more candidates lifts recall faster than it costs precision, so the
    # unconstrained optimum sat at 187 predictions for 64 events -- a chance recall of
    # 0.209, at which the headline recall stops meaning much, and a list nothing
    # downstream can use. The budget caps n_pred at K x n_ref on period 1.
    #
    # K is chosen from PERIOD-1 INFORMATION ONLY, by a rule fixed before period 2 was
    # looked at: the smallest K whose period-1 F1 is within `--budget-tolerance` of the
    # unconstrained optimum. Parsimony unless it actually costs you. On this detector
    # that selects K=3 (period-1 F1 0.257 against an unconstrained 0.265, -3 %); on the
    # restart detector the same rule is a no-op, because its optimum already sits at
    # 1.0x -- which is the evidence that the rule is not doing the work of the detector.
    def fit_threshold(cap):
        best = None
        for thr in np.unique(np.round(cand_s, 3)):
            p1 = cand_t[(cand_s >= thr) & in1(cand_t)]
            if len(p1) > cap:
                continue
            pr, rc, f1, tp = prf(p1, ref1)
            if best is None or f1 > best[0]:
                best = (f1, thr, pr, rc, tp, len(p1))
        return best

    unconstrained = fit_threshold(np.inf)
    budget_sweep = []
    chosen = None
    for K in a.budgets:
        b = fit_threshold(K * len(ref1))
        if b is None:
            continue
        budget_sweep.append({"K": K, "period1_f1": round(b[0], 4), "period1_n_pred": b[5]})
        if chosen is None and b[0] >= (1 - a.budget_tolerance) * unconstrained[0]:
            chosen = (K, b)
    if chosen is None:
        chosen = (None, unconstrained)
    budget_K, best = chosen
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
        "command": " ".join(sys.argv),
        "protocol": {"threshold_fitted_on": "period1", "applied_unchanged_to": "period2",
                     "tolerance_s": TOL, "min_sep_s": a.min_sep,
                     "prediction_budget_K": budget_K,
                     "budget_rule": ("smallest K with period-1 F1 within "
                                     f"{a.budget_tolerance:.0%} of the unconstrained "
                                     "optimum; chosen on period-1 data alone"),
                     "budget_sweep_period1": budget_sweep,
                     "period1_f1_unconstrained": round(unconstrained[0], 4),
                     "period1_n_pred_unconstrained": unconstrained[5],
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
    # ---- team, by chaining off the restart that follows ------------------------------
    # Veo labels an OutOfPlay with the side that put the ball out, and the restart goes
    # to the other side. In this match that relation is **exact: 64 of 64 restarts are
    # the opposite team to the OutOfPlay before them** -- throw-ins 39/39, goal kicks
    # 16/16, corners 9/9. So any OutOfPlay followed by a restart we can team, we can
    # team too, by inversion.
    #
    # Note the dependency runs backwards through the step numbers: step 8 leans on step
    # 10's output. That is the same inversion step 10 and step 12 found -- the thing that
    # happens *after* an event is repeatedly easier to see than the event itself.
    #
    # It is a thin channel. Only GoalKick and Corner predictions carry a team, so only
    # OutOfPlays followed by one of those get teamed, and the perfect ground-truth
    # relation degrades to what our own restart type-and-team predictions are worth:
    # 6 correct of the 8 teamed predictions that are also true positives.
    events_out = [{"video_s": round(float(t), 2), "event_type": "FootballOutOfPlay",
                   "period": 1 if in1(t) else 2} for t in pred_t]
    team_stats = None
    if a.restart_pred:
        restarts = [q for q in json.loads(Path(a.restart_pred).read_text())["events"]
                    if q.get("team")]
        flip = {"Own": "Opponent", "Opponent": "Own"}
        n_teamed = 0
        for e in events_out:
            nxt = [q for q in restarts if 0 < q["video_s"] - e["video_s"] <= a.restart_window]
            if nxt:
                e["team"] = flip[nxt[0]["team"]]
                e["team_from_restart_s"] = nxt[0]["video_s"]
                n_teamed += 1
        team_stats = {"teamed": n_teamed, "of": len(events_out),
                      "window_s": a.restart_window,
                      "rule": "the OutOfPlay side is the opposite of the restart's; "
                              "exact on 64/64 in the ground truth",
                      "source": "GoalKick and CornerKick predictions, the only teamed ones"}
    # `period` is what lets the scoring harness split dev from held-out on its own side;
    # without it its per-period blocks silently see zero predictions and report 0.0
    doc["team"] = team_stats
    Path(a.pred).write_text(json.dumps({"events": events_out}, indent=1))
    Path(a.manifest).write_text(json.dumps({
        "attempted": ["FootballOutOfPlay"], "tuned_on": "period1",
        "note": ("team is predicted only where a teamed restart follows within "
                 f"{a.restart_window:.0f}s; the rest score 0 team-aware by construction"
                 if a.restart_pred else
                 "team is not predicted for this type, so the team-aware score is 0 by "
                 "construction; read the team-agnostic figure")}, indent=1))
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
