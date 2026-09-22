#!/usr/bin/env python3
"""D-B step 14 — throw-in team from the thrower's shirt, and why it is borderline.

Throw-in team is the one thing the defend-end map cannot reach: it is ~50/50 in every
(end, period) cell, and post-throw ball direction is a coin flip (17/35). It needs
**possession** — who has the ball — and for a throw-in specifically that reduces to a
much smaller question: *who is holding it before the throw*.

The pipeline, all of it measured rather than assumed:

1. **Find the thrower.** In the pre-throw window the ball is in the taker's hands, so
   the taker is the player whose box *contains* the ball. Sampling every 5 fps step in
   [-2.6, -0.4] s and keeping only frames where the ball falls inside **exactly one**
   box -- padded by 0.10 of box height, because the ball is held above the head and
   often lands just outside -- attributes **30 of 38** throw-ins (0.79). At the throw-in
   instant itself this fails completely: the ball is inside a box in 2 of 36, because by
   then it is in flight, and the second-nearest player is a median 24 px further than
   the nearest, so "nearest player" is a toss-up.
2. **Read the shirt.** Median Lab lightness over an upper-torso band, the frames for one
   event combined by a ball-confidence-weighted average. The kits are white against dark
   navy: Own throwers land at L median **84**, Opponent at **177**.
3. **Map colour to side** with a threshold and polarity fitted on **period 1**.

**Read the result honestly.** Held out on period 2 the rule is right **15 of 18 = 0.83**
against a majority-class baseline of 0.78 and a balanced accuracy of **0.89**. Under
strict containment it was 12 of 15 = 0.80 against a baseline of *also* 0.80 — the
padding is what moved it off a tie, by attributing 5 more throw-ins without loosening
the rule enough to start catching the wrong player. The benchmark-level random-team
control (`control_team_shuffle.py`) is still what settles whether it is a result.

**A descriptor bug found by looking rather than by reasoning.** The first band, 0.15-0.45
of box height, sits on head and shoulders; cropping the boxes and viewing them showed the
sampled swatches were grass and hair. Sweeping the band (0.25-0.50, 0.30-0.55, 0.35-0.60)
separates the class medians much better (97 vs 143 -> 84 vs 177) and changes held-out
accuracy **not at all**, so the band was never the binding constraint — attribution rate
and sample size are.
"""
import argparse, csv, json, sys
from pathlib import Path

import numpy as np


def load_players(paths):
    by_t = {}
    for p in paths:
        for d in json.loads(Path(p).read_text())["detections"]:
            by_t[round(d["t"], 2)] = d
    return by_t


def thrower_L(t, players, ball_t, ball, pad=0.10, lo=-2.6, hi=-0.4):
    """Ball-confidence-weighted shirt lightness of the player holding the ball.

    `pad` widens each box by a fraction of **its own height**, which is what makes the
    rule scale-invariant: players here run 13-298 px tall, so a fixed pixel tolerance
    would be nothing up close and enormous at the far touchline. It exists because a
    throw-in ball is held *above the head*, often just outside the person box -- of the
    13 unattributed throw-ins under strict containment, 12 were "ball outside every box"
    and 7 of those missed the nearest edge by only 1.6-32 px. None were ambiguous.
    """
    hits = []
    for k in [x for x in ball_t if t + lo <= x <= t + hi]:
        cands = ball.get(k, {}).get("c") or []
        if not cands or round(k, 2) not in players:
            continue
        b = max(cands, key=lambda x: x[3])
        inside = []
        for bb in players[round(k, 2)]["boxes"]:
            if not bb["shirt"]:
                continue
            x1, y1, x2, y2 = bb["box"]
            m = pad * (y2 - y1)
            if x1 - m <= b[0] <= x2 + m and y1 - m <= b[1] <= y2 + m:
                inside.append(bb)
        if len(inside) == 1:                 # exactly one: no ambiguity to resolve
            hits.append((b[3], inside[0]["shirt"]["lab"][0]))
    if not hits:
        return None
    w = np.array([h[0] for h in hits])
    return float(np.average([h[1] for h in hits], weights=w)), len(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", nargs="+", required=True)
    ap.add_argument("--ball-frame", required=True)
    ap.add_argument("--restart-pred", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--out-pred", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pad", type=float, default=0.10,
                    help="box tolerance as a fraction of box height; 0.10 chosen on "
                         "attribution + period-1 accuracy over a 10-cell sweep")
    ap.add_argument("--emit-team", action="store_true",
                    help="write the team onto ThrowIn predictions; opt-in, because the "
                         "claim rests on control_team_shuffle.py rather than on the "
                         "held-out accuracy alone")
    ap.add_argument("--p1", type=float, nargs=2, default=[562.3, 2879.3])
    a = ap.parse_args()

    players = load_players(a.players)
    ball = {round(d["t"], 2): d for d in json.loads(Path(a.ball_frame).read_text())["detections"]}
    ball_t = np.array(sorted(ball))
    in1 = lambda t: a.p1[0] <= t <= a.p1[1]

    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    truth = []
    for r in csv.DictReader(open(bench)):
        if r["event_type"] == "FootballThrowIn":
            truth.append({"t": int(r["video_time_ms"]) / 1000.0, "team": r["team"]})

    # ---- fit threshold + polarity on period-1 true throw-ins ------------------------
    lab = []
    for e in truth:
        got = thrower_L(e["t"], players, ball_t, ball, a.pad)
        if got:
            lab.append({"t": e["t"], "team": e["team"], "L": got[0], "frames": got[1],
                        "p": 1 if in1(e["t"]) else 2})
    p1 = [x for x in lab if x["p"] == 1]
    p2 = [x for x in lab if x["p"] == 2]
    best = None
    for thr in range(10, 250, 5):
        for pol in (1, -1):
            ok = sum(1 for x in p1
                     if ("Own" if (x["L"] > thr) == (pol > 0) else "Opponent") == x["team"])
            if best is None or ok > best[0]:
                best = (ok, thr, pol)
    ok1, thr, pol = best
    predict = lambda L: "Own" if (L > thr) == (pol > 0) else "Opponent"

    def block(rows):
        if not rows:
            return None
        ok = sum(1 for x in rows if predict(x["L"]) == x["team"])
        maj = max(sum(1 for x in rows if x["team"] == t) for t in ("Own", "Opponent"))
        bal = []
        for t in ("Own", "Opponent"):
            sub = [x for x in rows if x["team"] == t]
            if sub:
                bal.append(sum(1 for x in sub if predict(x["L"]) == t) / len(sub))
        return {"n": len(rows), "correct": ok, "accuracy": round(ok / len(rows), 4),
                "majority_class_baseline": round(maj / len(rows), 4),
                "balanced_accuracy": round(float(np.mean(bal)), 4),
                "beats_majority": bool(ok / len(rows) > maj / len(rows))}

    doc = {"job": "D-B step 14: throw-in team from the thrower's shirt",
           "command": " ".join(sys.argv),
           "attribution": {"attributed": len(lab), "of": len(truth),
                           "rate": round(len(lab) / max(len(truth), 1), 4),
                           "rule": "ball inside exactly one player box (padded by "
                                   f"{a.pad:.2f} x box height), any 5 fps step in "
                                   "[-2.6,-0.4]s before the throw",
                           "pad_fraction_of_box_height": a.pad,
                           "pad_sweep_note": "0 -> 0.66 attributed (p1 acc 0.70); "
                                             "0.10 -> 0.79 (p1 0.83, the best in the "
                                             "sweep); 0.15-0.20 -> 0.84 but p1 falls to "
                                             "0.77 and held-out to 0.68"},
           "fit": {"fitted_on": "period1 true throw-ins",
                   "threshold_L": thr, "polarity": "L>thr -> " + ("Own" if pol > 0 else "Opponent")},
           "period1_fitted": block(p1),
           "period2_heldout": block(p2),
           "class_separation_L_median": {
               "Own": round(float(np.median([x["L"] for x in lab if x["team"] == "Own"])), 1),
               "Opponent": round(float(np.median([x["L"] for x in lab if x["team"] == "Opponent"])), 1)},
           "emit_team": bool(a.emit_team)}

    # ---- apply to our own predictions -------------------------------------------------
    pred = json.loads(Path(a.restart_pred).read_text())["events"]
    n_teamed = 0
    for e in pred:
        if e["event_type"] != "FootballThrowIn":
            continue
        got = thrower_L(e["video_s"], players, ball_t, ball, a.pad)
        if not got:
            continue
        e["thrower_L"] = round(got[0], 1)
        e["thrower_frames"] = got[1]
        if a.emit_team:
            e["team"] = predict(got[0])
            n_teamed += 1
    doc["predictions_teamed"] = n_teamed
    doc["caveat"] = (
        "held-out n is 18 of 38 throw-ins -- small, and the attributable subsample is "
        "skewed toward Own, so quote the majority-class baseline and the balanced "
        "accuracy alongside the raw figure. Whether this is a result is settled by "
        "control_team_shuffle.py, not by this block.")

    Path(a.out_pred).write_text(json.dumps({"events": pred}, indent=1))
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
