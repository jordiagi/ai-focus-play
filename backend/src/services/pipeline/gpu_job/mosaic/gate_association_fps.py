#!/usr/bin/env python3
"""D-B step 18 — the pre-registered gate: does 15 fps rescue moving-ball association?

Step 16 tried to name the player who last touched the ball before it went out, and both
routes failed: the last-contact rule attributed 94 % of events and was a coin flip
anyway, and the strike-frame rule scored *below* its majority baseline on held-out data.
The diagnosis was frame rate -- at 5 fps a struck ball moves ~50 px between frames, so
the contact frame is often never sampled.

That diagnosis is what this tests, and it matters beyond OutOfPlay team: Tier B
(interception 89, tackle 84, dribble 41, loose ball 27 = **241 events, 54 % of the
benchmark**) all need who-has-the-ball during open play, which is the same association.

The pass condition was committed before the data was collected (see the README). On
held-out period 2 the rule selected by **period-1** accuracy must beat **both**:

  1. the period-2 majority-class baseline, and
  2. a balanced accuracy of 0.55

Everything is in frame coordinates, so no panorama registration is involved.
"""
import argparse, csv, json, sys
from pathlib import Path

import numpy as np

BALANCED_MIN = 0.55


def load(players_path, ball_path):
    pl = {round(d["t"], 2): d
          for d in json.loads(Path(players_path).read_text())["detections"]}
    ball = {round(d["t"], 2): d
            for d in json.loads(Path(ball_path).read_text())["detections"]}
    return pl, ball


def top_candidate(ball, k):
    c = ball.get(k, {}).get("c") or []
    return max(c, key=lambda x: x[3]) if c else None


def route_last_contact(t, pl, ball, keys, pad):
    """Latest frame in the window where the ball sits inside exactly one padded box."""
    hit = None
    for k in keys:
        b = top_candidate(ball, k)
        if b is None or k not in pl:
            continue
        inside = []
        for bb in pl[k]["boxes"]:
            if not bb["shirt"]:
                continue
            x1, y1, x2, y2 = bb["box"]
            m = pad * (y2 - y1)
            if x1 - m <= b[0] <= x2 + m and y1 - m <= b[1] <= y2 + m:
                inside.append(bb)
        if len(inside) == 1:
            hit = inside[0]["shirt"]["lab"][0]      # latest wins
    return hit


def route_strike_frame(t, pl, ball, keys, pad, maxd):
    """Player nearest the ball at the frame of largest ball acceleration."""
    pts = [(k, top_candidate(ball, k)) for k in keys]
    pts = [(k, b) for k, b in pts if b is not None]
    if len(pts) < 3:
        return None
    T = np.array([k for k, _ in pts])
    P = np.array([[b[0], b[1]] for _, b in pts])
    dt = np.diff(T)
    d = np.hypot(*np.diff(P, axis=0).T)
    with np.errstate(divide="ignore", invalid="ignore"):
        v = np.where(dt > 0, d / np.where(dt > 0, dt, 1), 0.0)
    if len(v) < 2:
        return None
    k = pts[int(np.argmax(np.diff(v)))][0]          # frame the ball was still at
    b = top_candidate(ball, k)
    if b is None or k not in pl:
        return None
    cands = []
    for bb in pl[k]["boxes"]:
        if not bb["shirt"]:
            continue
        x1, y1, x2, y2 = bb["box"]
        h = max(y2 - y1, 1.0)
        m = pad * h
        dx = max(x1 - m - b[0], 0, b[0] - (x2 + m))
        dy = max(y1 - m - b[1], 0, b[1] - (y2 + m))
        cands.append((np.hypot(dx, dy) / h, bb))
    if not cands:
        return None
    cands.sort(key=lambda z: z[0])
    if cands[0][0] > maxd:
        return None
    if len(cands) > 1 and cands[1][0] < 1.5 * max(cands[0][0], 0.02):
        return None                                  # ambiguous, decline
    return cands[0][1]["shirt"]["lab"][0]


def fit_and_score(rec):
    """Threshold+polarity on period 1; report period 2 untouched."""
    p1 = [x for x in rec if x["p"] == 1]
    p2 = [x for x in rec if x["p"] == 2]
    if not p1 or not p2:
        return None
    best = None
    for thr in range(10, 250, 5):
        for pol in (1, -1):
            ok = sum(1 for x in p1
                     if ("Own" if (x["L"] > thr) == (pol > 0) else "Opponent") == x["team"])
            if best is None or ok > best[0]:
                best = (ok, thr, pol)
    ok1, thr, pol = best
    pred = lambda L: "Own" if (L > thr) == (pol > 0) else "Opponent"
    ok2 = sum(1 for x in p2 if pred(x["L"]) == x["team"])
    maj = max(sum(1 for x in p2 if x["team"] == t) for t in ("Own", "Opponent"))
    bal = [np.mean([pred(x["L"]) == t for x in p2 if x["team"] == t])
           for t in ("Own", "Opponent") if any(x["team"] == t for x in p2)]
    bal = float(np.mean(bal)) if bal else 0.0
    acc2 = ok2 / len(p2)
    maj2 = maj / len(p2)
    return {"n_attributed": len(rec), "period1_acc": round(ok1 / len(p1), 4),
            "period1_n": len(p1), "period2_acc": round(acc2, 4), "period2_n": len(p2),
            "period2_majority": round(maj2, 4), "period2_balanced": round(bal, 4),
            "beats_majority": bool(acc2 > maj2),
            "beats_balanced_floor": bool(bal > BALANCED_MIN),
            "PASSES_GATE": bool(acc2 > maj2 and bal > BALANCED_MIN),
            "threshold_L": thr, "polarity": "L>thr -> " + ("Own" if pol > 0 else "Opponent")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", required=True)
    ap.add_argument("--ball-frame", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--fps-label", default="15")
    ap.add_argument("--window", type=float, nargs=2, default=[-3.2, -0.2])
    ap.add_argument("--out", required=True)
    ap.add_argument("--p1", type=float, nargs=2, default=[562.3, 2879.3])
    a = ap.parse_args()

    pl, ball = load(a.players, a.ball_frame)
    keys_all = sorted(set(pl) & set(ball))
    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    oop = []
    for r in csv.DictReader(open(bench)):
        if r["event_type"] == "FootballOutOfPlay":
            oop.append({"t": int(r["video_time_ms"]) / 1000.0, "team": r["team"]})
    in1 = lambda t: a.p1[0] <= t <= a.p1[1]

    doc = {"job": "D-B step 18: pre-registered 15 fps association gate",
           "command": " ".join(sys.argv), "fps": a.fps_label,
           "window_s": list(a.window),
           "pass_condition": "period-2 accuracy > majority AND balanced > "
                             f"{BALANCED_MIN}; parameters selected on period 1 only",
           "frames_available": len(keys_all), "events": len(oop), "routes": {}}

    for name, fn, params in (
            ("last_contact", route_last_contact, [{"pad": p} for p in (0.0, 0.10, 0.20)]),
            ("strike_frame", route_strike_frame,
             [{"pad": p, "maxd": d} for p in (0.0, 0.10) for d in (0.3, 0.6, 1.0)])):
        cells = []
        for kw in params:
            rec = []
            for e in oop:
                keys = [k for k in keys_all if e["t"] + a.window[0] <= k <= e["t"] + a.window[1]]
                L = fn(e["t"], pl, ball, keys, **kw)
                if L is not None:
                    rec.append({"team": e["team"], "L": L,
                                "p": 1 if in1(e["t"]) else 2})
            sc = fit_and_score(rec)
            if sc:
                sc["params"] = kw
                sc["attribution_rate"] = round(len(rec) / len(oop), 4)
                cells.append(sc)
        # the protocol picks by period-1 accuracy, never by period 2
        chosen = max(cells, key=lambda c: c["period1_acc"]) if cells else None
        doc["routes"][name] = {"cells": cells, "selected_on_period1": chosen}

    passed = [n for n, r in doc["routes"].items()
              if r["selected_on_period1"] and r["selected_on_period1"]["PASSES_GATE"]]
    doc["GATE"] = "PASS" if passed else "FAIL"
    doc["routes_passing"] = passed
    doc["verdict"] = (
        "possession association is reachable at this frame rate; Tier B is worth "
        "attempting" if passed else
        "the diagnosis that frame rate was the limit is NOT supported: the rule the "
        "protocol selects still fails on held-out data. Per the pre-registration, stop "
        "here rather than re-deriving the detectors against a new track.")
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps({k: v for k, v in doc.items() if k != "routes"}, indent=1))
    for n, r in doc["routes"].items():
        c = r["selected_on_period1"]
        if c:
            print(f"  {n:14s} attrib {c['attribution_rate']:.2f} | p1 {c['period1_acc']:.2f}"
                  f" | p2 {c['period2_acc']:.2f} (maj {c['period2_majority']:.2f},"
                  f" bal {c['period2_balanced']:.2f}) -> "
                  f"{'PASS' if c['PASSES_GATE'] else 'fail'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
