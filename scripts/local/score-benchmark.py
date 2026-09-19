#!/usr/bin/env python3
"""Score detector output against Veo's 447-event reference.

Design notes that matter more than the code:

* **Per-type tolerance.** A loose window lets a random detector score. Dense types
  (interception n=89) get +/-2 s; crisp restarts get +/-3 s; Shot gets +/-5 s.
* **Chance baseline beside every recall.** A detector emitting n candidates over
  duration D hits a given event by luck with probability 1-(1-2*tol/D)^n. For
  interception that is ~7.5%. A recall of 0.12 next to a chance of 0.075 is an honest
  row; 0.12 alone is not. This is the exact trap the old Colab notebook fell into.
* **The chance figure ignores team-matching**, so it slightly OVERESTIMATES chance when
  scoring team-aware. That errs toward a harder bar, which is the safe direction; a
  detector that beats it has genuinely beaten it. Do not "correct" this downward.
* **Macro-F1 over ATTEMPTED types is the headline**, so a 6-event type counts the same
  as an 89-event one.
* **The attempted set is declared up front, in a manifest, and the harness refuses to
  score without one.** Otherwise a type that scores badly can be quietly reclassified
  as "not attempted" after the fact. Enforced here rather than left to discipline.
* **Period 1 is dev, period 2 is held out**, reported side by side so tuning leakage
  shows up as a gap.

Usage:
  score-benchmark.py --pred PRED.json --manifest MANIFEST.json [--bench ...] [--json OUT]

PRED.json   : {"events":[{"video_s":float,"event_type":str,"team":"Own"|"Opponent"},...]}
MANIFEST.json: {"attempted":[...type names...], "tuned_on":"none"|"period1"|...}

Exit codes: 0 scored, 2 usage/missing manifest, 3 reference unreadable.
"""
import argparse, csv, json, math, os, sys
from collections import defaultdict

try:
    from scipy.optimize import linear_sum_assignment
    import numpy as np
except ImportError:
    linear_sum_assignment = None

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_BENCH = os.path.join(REPO, "benchmarks", "veo_reference.json")
DEFAULT_RAW = os.path.join(REPO, "benchmarks", "raw", "veo_events_447.csv")


def load_reference(bench_path, raw_path):
    with open(bench_path) as f:
        bench = json.load(f)
    rows = []
    with open(raw_path) as f:
        for r in csv.DictReader(f):
            rows.append({
                "video_s": int(r["video_time_ms"]) / 1000.0,
                "period": int(r["period_id"]),
                "event_type": r["event_type"],
                "team": r["team"],
            })
    return bench, rows


def match_one_type(ref, pred, tol):
    """Optimal one-to-one assignment within tol. Returns (tp, matched_pairs)."""
    if not ref or not pred:
        return 0, []
    if linear_sum_assignment is None:          # greedy fallback, documented as such
        used, tp, pairs = set(), 0, []
        for i, r in enumerate(ref):
            best, bj = None, None
            for j, p in enumerate(pred):
                if j in used:
                    continue
                d = abs(r["video_s"] - p["video_s"])
                if d <= tol and (best is None or d < best):
                    best, bj = d, j
            if bj is not None:
                used.add(bj); tp += 1; pairs.append((i, bj, best))
        return tp, pairs
    BIG = 1e6
    cost = np.full((len(ref), len(pred)), BIG)
    for i, r in enumerate(ref):
        for j, p in enumerate(pred):
            d = abs(r["video_s"] - p["video_s"])
            if d <= tol:
                cost[i, j] = d
    ri, ci = linear_sum_assignment(cost)
    pairs = [(int(i), int(j), float(cost[i, j])) for i, j in zip(ri, ci) if cost[i, j] < BIG]
    return len(pairs), pairs


def chance_recall(n_pred, tol, duration):
    """P(a given reference event is covered by >=1 of n random predictions)."""
    if duration <= 0 or n_pred <= 0:
        return 0.0
    p = min(1.0, 2.0 * tol / duration)
    return 1.0 - (1.0 - p) ** n_pred


def f1(tp, fp, fn):
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return prec, rec, (2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)


def score(ref_rows, pred_rows, tol_by_type, attempted, duration, team_aware=True):
    out = {}
    types = sorted(set([r["event_type"] for r in ref_rows]) | set([p["event_type"] for p in pred_rows]))
    for t in types:
        tol = tol_by_type.get(t, 3.0)
        ref_t = [r for r in ref_rows if r["event_type"] == t]
        pred_t = [p for p in pred_rows if p["event_type"] == t]
        if team_aware:
            tp = 0; pairs_all = []
            for team in ("Own", "Opponent"):
                a = [r for r in ref_t if r["team"] == team]
                b = [p for p in pred_t if p.get("team") == team]
                n, pairs = match_one_type(a, b, tol)
                tp += n; pairs_all += pairs
        else:
            tp, pairs_all = match_one_type(ref_t, pred_t, tol)
        fp = len(pred_t) - tp
        fn = len(ref_t) - tp
        prec, rec, f = f1(tp, fp, fn)
        out[t] = {
            "n_ref": len(ref_t), "n_pred": len(pred_t),
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f, 3),
            "tolerance_s": tol,
            "chance_recall": round(chance_recall(len(pred_t), tol, duration), 3),
            "low_n": len(ref_t) < 10,
            "status": "attempted" if t in attempted else "not_attempted",
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--manifest", help="declares the attempted set BEFORE the run")
    ap.add_argument("--bench", default=DEFAULT_BENCH)
    ap.add_argument("--raw", default=DEFAULT_RAW)
    ap.add_argument("--json", dest="json_out")
    a = ap.parse_args()

    if not a.manifest:
        print("REFUSING TO SCORE: --manifest is required.\n"
              "  The attempted set must be declared before the run, otherwise a type that\n"
              "  scores badly can be reclassified as 'not attempted' afterwards. That is the\n"
              "  whole point of the manifest.", file=sys.stderr)
        return 2
    try:
        bench, ref_rows = load_reference(a.bench, a.raw)
    except Exception as e:
        print(f"cannot read reference: {e}", file=sys.stderr)
        return 3
    with open(a.manifest) as f:
        man = json.load(f)
    attempted = set(man.get("attempted", []))
    tuned_on = man.get("tuned_on")
    if tuned_on is None:
        print("REFUSING TO SCORE: manifest has no 'tuned_on'. State it, even if 'none'.",
              file=sys.stderr)
        return 2
    with open(a.pred) as f:
        pred = json.load(f)
    pred_rows = pred.get("events", [])

    tol_by_type = {t: v.get("match_tolerance_s") or 3.0
                   for t, v in bench["events"]["per_type"].items()}
    duration = bench["match"]["duration_s"]

    rep = {"tuned_on": tuned_on, "n_ref": len(ref_rows), "n_pred": len(pred_rows)}
    rep["overall"] = score(ref_rows, pred_rows, tol_by_type, attempted, duration, True)
    rep["team_agnostic"] = score(ref_rows, pred_rows, tol_by_type, attempted, duration, False)
    for p in (1, 2):
        rep[f"period{p}"] = score([r for r in ref_rows if r["period"] == p],
                                  [q for q in pred_rows if q.get("period") == p],
                                  tol_by_type, attempted, duration / 2, True)

    att = [t for t, v in rep["overall"].items() if v["status"] == "attempted"]
    macro = sum(rep["overall"][t]["f1"] for t in att) / len(att) if att else 0.0
    tp = sum(rep["overall"][t]["tp"] for t in att)
    fp = sum(rep["overall"][t]["fp"] for t in att)
    fn = sum(rep["overall"][t]["fn"] for t in att)
    _, _, micro = f1(tp, fp, fn)
    parity = sum(1 for t in att if rep["overall"][t]["f1"] >= 0.5)
    mass = sum(rep["overall"][t]["n_ref"] for t in att)
    rep["summary"] = {
        "macro_f1_attempted": round(macro, 3), "micro_f1_attempted": round(micro, 3),
        "parity_count": parity, "types_attempted": len(att),
        "types_total": len(bench["events"]["per_type"]),
        "event_mass_attempted": mass, "event_mass_total": len(ref_rows),
    }

    w = max(len(t) for t in rep["overall"]) if rep["overall"] else 10
    print(f"{'type':<{w}}  {'n':>4} {'pred':>5} {'tp':>4} {'fp':>4} {'fn':>4} "
          f"{'prec':>5} {'rec':>5} {'chance':>6} {'F1':>5}  status")
    for t, v in sorted(rep["overall"].items(), key=lambda kv: -kv[1]["n_ref"]):
        flag = " low-n" if v["low_n"] else ""
        print(f"{t:<{w}}  {v['n_ref']:>4} {v['n_pred']:>5} {v['tp']:>4} {v['fp']:>4} "
              f"{v['fn']:>4} {v['precision']:>5} {v['recall']:>5} {v['chance_recall']:>6} "
              f"{v['f1']:>5}  {v['status']}{flag}")
    s = rep["summary"]
    print()
    print(f"  attempted {s['types_attempted']}/{s['types_total']} types, "
          f"covering {s['event_mass_attempted']}/{s['event_mass_total']} events "
          f"({100*s['event_mass_attempted']/max(1,s['event_mass_total']):.0f}% of mass)")
    print(f"  macro-F1 (attempted) {s['macro_f1_attempted']}   "
          f"micro-F1 {s['micro_f1_attempted']}   parity count {s['parity_count']}/14")
    print(f"  tuned_on: {tuned_on}   "
          f"period1 macro {round(sum(rep['period1'][t]['f1'] for t in att)/len(att),3) if att else 0}   "
          f"period2 macro {round(sum(rep['period2'][t]['f1'] for t in att)/len(att),3) if att else 0}")
    print("  NOTE: 'chance' is the recall a random detector emitting the same number of "
          "candidates would get. A recall at or below it is not a result.")
    if a.json_out:
        with open(a.json_out, "w") as f:
            json.dump(rep, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
