#!/usr/bin/env python3
"""D-B step 12 -- FootballGoal, inferred backwards from the kickoff that follows it.

The third use of the same trick. Step 10 found the restart is easier to see than the
stoppage it ends; this finds the **goal is easier to see through its kickoff** than
directly. A goal has no distinctive ball signature of its own -- the ball is struck,
which is what a shot looks like -- but it is always followed by a kickoff, and the
kickoff detector is the most precise thing in this repo (4 predictions, 4 correct).

So: every predicted kickoff with a goal behind it implies a goal, at a fitted offset.

**The offset.** Goal -> kickoff gaps in this match are 37.2, 38.2, 53.1, 38.1 (period 1)
and 28.0, 38.5 (period 2). Four of six sit within 0.4 s of 38.2, which at a 3 s matching
tolerance is the whole game: the median of the **period-1** gaps is the offset, and the
two outliers (53.1 s and 28.0 s) are simply missed. Nothing here can fix that -- the
restart is taken when the players are ready, and one of those is a substitution.

**Team comes free, and is the point.** A goal is scored at the end the *conceding* side
defends, so the defend-end map from step 11 names the conceder, and the scorer is the
other side. The same lookback that finds the goal also teams it. On true kickoff times
the end is read correctly **6 of 6**.

**What this cannot do.** 6 reference events: the harness flags it `low_n` and so should
anyone quoting it. Recall is capped by the kickoff detector's own recall -- a goal whose
kickoff is missed is invisible here -- and the two period-opening kickoffs have no goal
behind them and are correctly excluded rather than made to invent one.

**Protocol.** The offset is fitted on period-1 pairs and applied unchanged to period 2.
Predictions are suppressed outside the period bounds and where no goal is locatable.
"""
import argparse, csv, json, sys
from pathlib import Path

import numpy as np

TOL = 3.0


def prf(pred_t, ref_t):
    if len(pred_t) == 0 or len(ref_t) == 0:
        return 0.0, 0.0, 0.0, 0
    used, tp = set(), 0
    for r in ref_t:
        best, bj = None, None
        for j, p in enumerate(pred_t):
            if j in used:
                continue
            d = abs(p - r)
            if d <= TOL and (best is None or d < best):
                best, bj = d, j
        if bj is not None:
            used.add(bj)
            tp += 1
    prec, rec = tp / len(pred_t), tp / len(ref_t)
    return prec, rec, (2 * prec * rec / (prec + rec) if prec + rec else 0.0), tp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restart-pred", required=True, help="pred_restarts.json")
    ap.add_argument("--frame", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-gap", type=float, default=70.0,
                    help="how far back a kickoff may look for its goal, when pairing")
    ap.add_argument("--p1", type=float, nargs=2, default=[562.3, 2879.3])
    ap.add_argument("--p2", type=float, nargs=2, default=[3674.4, 6132.1])
    a = ap.parse_args()

    in1 = lambda x: (x >= a.p1[0]) & (x <= a.p1[1])
    dur = (a.p1[1] - a.p1[0]) + (a.p2[1] - a.p2[0])
    chance = lambda n: 1 - (1 - 2 * TOL / dur) ** max(n, 0)

    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    rows = []
    for r in csv.DictReader(open(bench)):
        rows.append({"t": int(r["video_time_ms"]) / 1000.0, "type": r["event_type"],
                     "team": r["team"], "period": int(r["period_id"])})
    rows.sort(key=lambda e: e["t"])
    goals = [e for e in rows if e["type"] == "FootballGoal"]
    kickoffs = [e for e in rows if e["type"] == "FootballKickOff"]

    # ---- fit the offset on period-1 pairs only ---------------------------------------
    pairs = [(g, k) for g in goals for k in kickoffs if 0 < k["t"] - g["t"] < a.max_gap]
    gaps1 = [k["t"] - g["t"] for g, k in pairs if in1(g["t"])]
    gaps2 = [k["t"] - g["t"] for g, k in pairs if not in1(g["t"])]
    if not gaps1:
        print("no period-1 goal/kickoff pairs to fit an offset on", file=sys.stderr)
        return 3
    offset = float(np.median(gaps1))

    # ---- predict ----------------------------------------------------------------------
    # `goal_xi` is written by detect_restarts.py: the ball's position in the lookback
    # window behind a kickoff, i.e. where the goal was. Its absence means the kickoff
    # opens a period, so there is no goal to infer.
    frame = json.loads(Path(a.frame).read_text())
    ko_pred = [p for p in json.loads(Path(a.restart_pred).read_text())["events"]
               if p["event_type"] == "FootballKickOff"]
    preds, skipped = [], 0
    for p in ko_pred:
        if "goal_xi" not in p:
            skipped += 1
            continue
        t = p["video_s"] - offset
        if not (in1(t) or (a.p2[0] <= t <= a.p2[1])):
            skipped += 1                      # would fall in halftime or before kickoff
            continue
        # scorer = the side that does NOT defend the end the goal was scored at
        team = p.get("team")                  # detect_restarts already stored the conceder
        preds.append({"video_s": round(t, 2), "event_type": "FootballGoal",
                      "period": 1 if in1(t) else 2,
                      **({"team": "Opponent" if team == "Own" else "Own"} if team else {}),
                      "from_kickoff_s": p["video_s"], "goal_xi": p["goal_xi"]})

    pt = np.array([p["video_s"] for p in preds])
    rt = np.array([g["t"] for g in goals])

    def block(pp, rr):
        pr, rc, f1, tp = prf(pp, rr)
        return {"n_pred": int(len(pp)), "n_ref": int(len(rr)), "tp": int(tp),
                "precision": round(pr, 4), "recall": round(rc, 4), "f1": round(f1, 4),
                "recall_expected_by_chance": round(chance(len(pp)), 4)}

    def team_block(sel):
        tp = 0
        for team in ("Own", "Opponent"):
            pp = np.array([p["video_s"] for p in preds if p.get("team") == team
                           and sel(p["video_s"])])
            rr = np.array([g["t"] for g in goals if g["team"] == team and sel(g["t"])])
            tp += prf(pp, rr)[3]
        n_p = len([p for p in preds if sel(p["video_s"])])
        n_r = len([g for g in goals if sel(g["t"])])
        pr = tp / n_p if n_p else 0.0
        rc = tp / n_r if n_r else 0.0
        return {"n_pred": n_p, "n_ref": n_r, "tp": tp, "precision": round(pr, 4),
                "recall": round(rc, 4),
                "f1": round(2 * pr * rc / (pr + rc) if pr + rc else 0.0, 4)}

    doc = {
        "job": "D-B step 12: FootballGoal inferred from the kickoff that follows it",
        "command": " ".join(sys.argv),
        "protocol": {"offset_fitted_on": "period1 goal->kickoff pairs",
                     "applied_unchanged_to": "period2", "tolerance_s": TOL,
                     "team": "predicted -- the scorer is the side that does not defend "
                             "the end the goal was scored at"},
        "offset_s": round(offset, 2),
        "gaps_period1_fitted": [round(g, 1) for g in sorted(gaps1)],
        "gaps_period2_heldout": [round(g, 1) for g in sorted(gaps2)],
        "kickoff_predictions_in": len(ko_pred),
        "skipped_no_goal_behind_them": skipped,
        "team_agnostic": {"period1_dev": block(pt[in1(pt)] if len(pt) else pt,
                                               rt[in1(rt)]),
                          "period2_heldout": block(pt[~in1(pt)] if len(pt) else pt,
                                                   rt[~in1(rt)]),
                          "both_periods": block(pt, rt)},
        "team_aware": {"period1_dev": team_block(lambda x: in1(x)),
                       "period2_heldout": team_block(lambda x: not in1(x)),
                       "both_periods": team_block(lambda x: True)},
    }

    # the same negative control the other detectors carry
    rng = np.random.default_rng(11)
    ctrl = []
    for _ in range(20):
        tt = np.array([(rng.uniform(*a.p1) if rng.random() < 0.5 else rng.uniform(*a.p2))
                       for _ in range(len(pt))])
        ctrl.append(prf(np.sort(tt), rt)[2])
    real = prf(pt, rt)[2]
    doc["random_control"] = {
        "trials": 20, "real_f1": round(real, 4),
        "random_f1_mean": round(float(np.mean(ctrl)), 4),
        "random_f1_max": round(float(np.max(ctrl)), 4),
        "is_a_result": bool(real > np.max(ctrl) + 1e-9)}

    doc["caveats"] = [
        "6 reference events -- low_n, and the harness says so",
        "recall is capped by the kickoff detector's recall: a goal whose kickoff is "
        "missed cannot be seen here at all",
        "the two period-opening kickoffs have no goal behind them and are excluded, "
        "not guessed",
        "one period-1 gap (53.1 s) and one period-2 gap (28.0 s) fall outside the 3 s "
        "tolerance around the fitted offset and are unreachable by this method",
    ]

    Path(a.pred).write_text(json.dumps({"events": preds}, indent=1))
    Path(a.manifest).write_text(json.dumps({
        "attempted": ["FootballGoal"], "tuned_on": "period1",
        "note": "team is predicted for this type"}, indent=1))
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
