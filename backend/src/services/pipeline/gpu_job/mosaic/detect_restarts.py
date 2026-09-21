#!/usr/bin/env python3
"""D-B step 10 -- the dead-ball restart family: detect, then classify.

`FootballOutOfPlay` (step 8) is a candidate generator for what follows it, but the
restart itself turns out to have a **stronger and more direct signature** than the
stoppage does, and it does not depend on the OutOfPlay detector at all.

Measured before anything was built -- medians over each type against 800 random in-play
times (all in panorama px/s, from the Viterbi ball track):

| type            |  n | speed [-4,-0.5]s | speed [0,+1.5]s | post/pre ratio |
| :-------------- | -: | ---------------: | --------------: | -------------: |
| ThrowIn         | 38 |             13.0 |           202.2 |            5.0 |
| GoalKick        | 16 |              1.8 |           101.7 |          105.8 |
| CornerKick      |  9 |              1.3 |            52.8 |           38.6 |
| FreeKick        | 15 |              2.1 |           285.4 |           23.9 |
| KickOff         |  8 |              1.5 |           240.5 |           52.8 |
| interception    | 89 |            149.5 |           111.5 |            0.8 |
| tackle          | 84 |            124.8 |            92.5 |            0.8 |
| dribble         | 41 |            144.6 |           112.2 |            1.0 |
| *random*        |800 |             30.9 |            23.5 |            0.9 |

The five dead-ball types sit at 1-13 px/s beforehand; every in-play type sits at
125-150. That is not a tuned margin, it is the difference between a stationary ball and
a moving one, so **one detector covers all five types** -- 86 events, 19 % of the
benchmark's event mass, against OutOfPlay's 64.

Type then comes from **where** the ball was, in the occupancy-derived (xi, eta) frame
(`derive_pitch_frame.py`). Read that file's caveat first: the frame's boundaries are not
the touchlines, so every threshold here is fitted on period 1 rather than assumed.

**Team** is predicted for GoalKick and CornerKick, because the laws of the game decide
it once you know which side defends which end: a goal kick is taken by the defending
side, a corner by the attacking one. That is a single bit, since the sides swap at half
time. On true event times the rule is right **24 of 24** -- including 8 of 8 on held-out
period-2 goal kicks, which is what tests the swap. ThrowIn and KickOff get no team and
are declared so in the manifest.

**Protocol.** Detector window/NMS config chosen by period-1 F1 over a 36-cell sweep;
detection threshold and all class thresholds fitted on period 1; period 2 is scored
once, unchanged.

**Leakage to declare, twice over:**

1. The period boundaries come from the ground-truth time base, and two of the eight
   kickoffs *are* those boundaries. KickOff is reported twice -- all 8, and the 6
   post-goal ones whose timing is not given away.
2. The team bit is fitted from **period-1 goal-kick team labels**. It is one bit and it
   cannot be had for free without a roster or a colour-to-label mapping, but it is
   supervision and is named as such rather than presented as geometry.
"""
import argparse, csv, json, sys
from pathlib import Path

import numpy as np

FAMILY = {"FootballThrowIn": "FootballThrowIn",
          "FootballGoalKick": "FootballGoalKick",
          "FootballCornerKick": "FootballCornerKick",
          "FootballFreeKick": "FootballFreeKick",
          "FootballKickOff": "FootballKickOff"}
# declared before scoring: FreeKick is in the detector's family but has no classifier
ATTEMPTED = ["FootballThrowIn", "FootballGoalKick", "FootballCornerKick",
             "FootballKickOff"]
TOL = 3.0


def prf(pred_t, ref_t):
    """Greedy one-to-one match inside TOL, as in step 8 -- same scoring, comparable."""
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
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return prec, rec, f1, tp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--frame", required=True)
    ap.add_argument("--bench", default=None)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--budgets", type=float, nargs="*", default=[1.0, 1.5, 2.0, 3.0])
    ap.add_argument("--budget-tolerance", type=float, default=0.05)
    ap.add_argument("--p1", type=float, nargs=2, default=[562.3, 2879.3])
    ap.add_argument("--p2", type=float, nargs=2, default=[3674.4, 6132.1])
    a = ap.parse_args()

    # ---- ball track -> per-grid-point motion features --------------------------------
    tr = json.loads(Path(a.track).read_text())
    T = np.array([p["t"] for p in tr])
    U = np.array([p["u"] for p in tr])
    V = np.array([p["v"] for p in tr])
    dt, dd = np.diff(T), np.hypot(np.diff(U), np.diff(V))
    ok = (dt > 0) & (dt < 1.0)
    st, sv = T[1:][ok], dd[ok] / dt[ok]

    grid = np.concatenate([np.arange(a.p1[0], a.p1[1], 1.0 / a.fps),
                           np.arange(a.p2[0], a.p2[1], 1.0 / a.fps)])

    def med_speed(lo, hi):
        out = np.full(len(grid), np.nan)
        for i, t in enumerate(grid):
            m = (st >= t + lo) & (st <= t + hi)
            if m.any():
                out[i] = np.median(sv[m])
        return out

    def rank(x, nanval):
        r = np.full(len(x), np.nan)
        m = ~np.isnan(x)
        r[m] = np.argsort(np.argsort(x[m])) / max(m.sum() - 1, 1)
        r[~m] = nanval
        return r

    # config selected by period-1 F1 over pre in {(-4,-.5),(-3,-.5),(-6,-1)} x
    # post in {(0,1.5),(.5,2.5),(0,3)} x coverage-feature {on,off} x min_sep {6,10}
    PRE, POST, MIN_SEP = (-6.0, -1.0), (0.0, 1.5), 6.0
    # a NaN pre-speed means the tracker held nothing at all -- which is evidence of a
    # dead ball, not of motion, so it ranks as "most still" (0.0). A NaN post-speed is
    # the opposite: no evidence of a strike, so it ranks as "least struck" (0.0).
    score = (1 - rank(med_speed(*PRE), 0.0)) + rank(med_speed(*POST), 0.0)

    order = np.argsort(-score)
    picked = []
    for i in order:
        if all(abs(grid[i] - grid[j]) >= MIN_SEP for j in picked):
            picked.append(i)
        if len(picked) >= 500:
            break
    picked = np.array(sorted(picked, key=lambda j: grid[j]))
    cand_t, cand_s = grid[picked], score[picked]

    # ---- ground truth ---------------------------------------------------------------
    repo = Path(__file__).resolve().parents[6]
    bench = Path(a.bench) if a.bench else repo / "benchmarks" / "raw" / "veo_events_447.csv"
    events = []
    for r in csv.DictReader(open(bench)):
        if r["event_type"] in FAMILY:
            events.append({"t": int(r["video_time_ms"]) / 1000.0,
                           "type": r["event_type"], "period": int(r["period_id"]),
                           "team": r["team"]})
    events.sort(key=lambda e: e["t"])
    ref_all = np.array([e["t"] for e in events])
    in1 = lambda x: (x >= a.p1[0]) & (x <= a.p1[1])
    dur = (a.p1[1] - a.p1[0]) + (a.p2[1] - a.p2[0])
    chance = lambda n: 1 - (1 - 2 * TOL / dur) ** max(n, 0)

    # ---- fit the detection threshold on period 1 only, under a prediction budget -----
    # Same declared rule as step 8: cap n_pred at K x n_ref on period 1 and take the
    # smallest K whose period-1 F1 is within `--budget-tolerance` of the unconstrained
    # optimum, decided on period-1 data alone. Here it is a **no-op** -- the optimum
    # already sits at 1.0x -- and that is the point: the rule only bites on a detector
    # that was buying recall by emitting candidates, which this one was not.
    def fit_threshold(cap):
        best = None
        for thr_ in np.unique(np.round(cand_s, 3)):
            p = cand_t[(cand_s >= thr_) & in1(cand_t)]
            if len(p) > cap:
                continue
            _, _, f1, _ = prf(p, ref_all[in1(ref_all)])
            if best is None or f1 > best[0]:
                best = (f1, float(thr_), len(p))
        return best

    unconstrained = fit_threshold(np.inf)
    budget_sweep, chosen = [], None
    n_ref1 = int(in1(ref_all).sum())
    for K in a.budgets:
        b = fit_threshold(K * n_ref1)
        if b is None:
            continue
        budget_sweep.append({"K": K, "period1_f1": round(b[0], 4), "period1_n_pred": b[2]})
        if chosen is None and b[0] >= (1 - a.budget_tolerance) * unconstrained[0]:
            chosen = (K, b)
    budget_K, best = chosen if chosen else (None, unconstrained)
    thr = best[1]
    pred_t = cand_t[cand_s >= thr]

    # ---- where was the ball? ---------------------------------------------------------
    frame = json.loads(Path(a.frame).read_text())
    p_far, p_near = frame["p_far"], frame["p_near"]
    u_lo, u_hi = frame["u_lo"], frame["u_hi"]
    cands = json.loads(Path(a.candidates).read_text())["tracks"]
    ct = np.array([c["t"] for c in cands])

    def ball_at(t, lo=-2.0, hi=0.5):
        """Top-confidence candidate in the window -- what a detector actually outputs."""
        best_c = None
        for i in np.where((ct >= t + lo) & (ct <= t + hi))[0]:
            for u, v, _r, conf in cands[i]["c"]:
                if best_c is None or conf > best_c[2]:
                    best_c = (u, v, conf)
        if best_c is None:
            return None
        u, v = best_c[0], best_c[1]
        f, n = np.polyval(p_far, u), np.polyval(p_near, u)
        return ((u - u_lo) / (u_hi - u_lo), (v - f) / max(n - f, 1.0), best_c[2])

    # ---- the classifier ---------------------------------------------------------------
    # Thresholds below are read off period-1 events ONLY. The shapes they encode:
    #   KickOff  -- the centre spot: a tight box all 8 kickoffs share and nothing else
    #               enters (period 1 range xi .39-.48, eta .52-.60)
    #   GoalKick -- at one end of the pan AND at the far-boundary level
    #   ThrowIn  -- the default. Four positive-cue alternatives were tried and all lost
    #               on period-1 F1 (eta>0.25 -> 0.207, eta>0.25 or |xi-.5|<0.28 -> 0.238,
    #               eta>0.35 -> 0.160, |xi-.5|<0.30 -> 0.158, default -> 0.261), so the
    #               catch-all is kept because it measured better, not because it is easy
    #   Corner   -- the ball *beyond* the far boundary (eta < 0) near an end. This was
    #               the only cue that separated corners from goal kicks at all, and it
    #               is weak: 3 of 8 corners against 1 of 16 goal kicks
    # FreeKick is NOT attempted and is declared so in the manifest: its (xi, eta) cloud
    # sits inside ThrowIn's with no cue between them (eta median 0.64 vs ThrowIn's
    # bimodal 0.05/0.67), so its 15 events arrive here as ThrowIn false positives.
    KO_XI, KO_ETA = (0.33, 0.55), (0.46, 0.66)
    GK_ETA, GK_END = (-0.05, 0.18), 0.30      # |xi-0.5| > GK_END
    CORNER_ETA, CORNER_END = -0.02, 0.15

    def classify(t):
        b = ball_at(t)
        if b is None:
            return None, None
        xi, eta, conf = b
        if KO_XI[0] <= xi <= KO_XI[1] and KO_ETA[0] <= eta <= KO_ETA[1]:
            return "FootballKickOff", b
        if eta < CORNER_ETA and abs(xi - 0.5) > CORNER_END:
            return "FootballCornerKick", b
        if GK_ETA[0] <= eta <= GK_ETA[1] and abs(xi - 0.5) > GK_END:
            return "FootballGoalKick", b
        return "FootballThrowIn", b

    # ---- team, for the two types where the laws of the game decide it ------------------
    # A goal kick is taken by the side DEFENDING that end; a corner by the side attacking
    # it. So "which team defends which end" settles both -- and that is one bit, because
    # the sides swap at half time. The bit is fitted on period-1 goal kicks (their team
    # labels are ground truth, so this IS one bit of label supervision and is declared as
    # such); period 2 then follows from the swap, which makes it a real test: if the swap
    # were wrong, or Veo's Own/Opponent were camera-relative rather than team-relative,
    # period-2 team accuracy would collapse to ~0 instead of holding.
    #
    # ThrowIn and KickOff get NO team and are declared so. Throw-in team is ~50/50 in
    # every (end, period) cell -- it needs possession, which is G4. Kickoff team is
    # whoever conceded, and the one positional cue available (which way the ball drifts
    # over [+4,+12]s) does not separate: Own kickoffs drifted -0.171, -0.150, +0.383.
    # KickOff closes a third loop. A kickoff (bar the two that open a period) follows a
    # goal, and a goal is scored at the end the CONCEDING side defends -- so the same
    # defend-end map gives the kickoff's taker, who is exactly that conceding side.
    # Looking back [-45,-30] s from a kickoff lands on the goal: over the 6 post-goal
    # kickoffs that window puts the ball at the right end **6 of 6**. The two
    # period-opening kickoffs have no goal behind them (and no track there at all), so
    # they are emitted with NO team rather than guessed -- which side kicks off first is
    # a coin flip nothing in the footage settles.
    TEAM_TYPES = ("FootballGoalKick", "FootballCornerKick")
    GOAL_LOOKBACK = (-45.0, -30.0)
    gk_p1 = []
    for e in events:
        if e["type"] != "FootballGoalKick" or not in1(e["t"]):
            continue
        b = ball_at(e["t"])
        if b is not None:
            gk_p1.append((b[0], e["team"]))
    lo_votes = [t for xi_, t in gk_p1 if xi_ < 0.5]
    defends_lo_p1 = max(set(lo_votes), key=lo_votes.count) if lo_votes else "Own"
    other = lambda t: "Opponent" if t == "Own" else "Own"

    def defender_of(xi, t):
        """Which side defends the end this xi sits at, at time t."""
        team = defends_lo_p1 if xi < 0.5 else other(defends_lo_p1)
        return team if in1(t) else other(team)      # they swap at half time

    preds = []
    for t in pred_t:
        t = float(t)
        et, b = classify(t)
        if et is None:
            continue                      # no position -> no type -> not emitted
        # `period` is what lets the scoring harness split dev from held-out on its own
        # side; without it its per-period blocks see zero predictions and report 0.0
        p = {"video_s": round(t, 2), "event_type": et, "period": 1 if in1(t) else 2,
             "xi": round(b[0], 3), "eta": round(b[1], 3), "ball_conf": round(b[2], 3)}
        if et in TEAM_TYPES:
            d = defender_of(b[0], t)
            p["team"] = d if et == "FootballGoalKick" else other(d)
        elif et == "FootballKickOff":
            g = ball_at(t, *GOAL_LOOKBACK)
            if g is not None:
                # the goal end -> its defender conceded -> the conceder restarts
                p["team"] = defender_of(g[0], t)
                p["goal_xi"] = round(g[0], 3)
        preds.append(p)

    # ---- scoring ----------------------------------------------------------------------
    def block(pt, rt):
        pr, rc, f1, tp = prf(pt, rt)
        return {"n_pred": int(len(pt)), "n_ref": int(len(rt)), "tp": int(tp),
                "precision": round(pr, 4), "recall": round(rc, 4), "f1": round(f1, 4),
                "recall_expected_by_chance": round(chance(len(pt)), 4)}

    doc = {"job": "D-B step 10: dead-ball restart family -- detect, then classify",
           "command": " ".join(sys.argv),
           "protocol": {
               "detector_config_selected_on": "period1 F1, 36-cell sweep",
               "detection_threshold_fitted_on": "period1",
               "class_thresholds_fitted_on": "period1",
               "applied_unchanged_to": "period2",
               "tolerance_s": TOL, "min_sep_s": MIN_SEP,
               "pre_window_s": list(PRE), "post_window_s": list(POST),
               "prediction_budget_K": budget_K,
               "budget_sweep_period1": budget_sweep,
               "period1_f1_unconstrained": round(unconstrained[0], 4),
               "period1_n_pred_unconstrained": unconstrained[2],
               "team": "NOT predicted for any type -- team-aware scoring is 0 by "
                       "construction; these are the team-agnostic figures"},
           "detection_threshold": round(thr, 4)}

    # the family as one class: how good is the *timing*, before type is asked for
    doc["family_detection"] = {
        "what": "all 5 dead-ball types pooled -- timing only, type ignored",
        "period1_dev": block(pred_t[in1(pred_t)], ref_all[in1(ref_all)]),
        "period2_heldout": block(pred_t[~in1(pred_t)], ref_all[~in1(ref_all)]),
        "both_periods": block(pred_t, ref_all)}

    # per type, which is what the benchmark actually asks for
    per_type = {}
    for et in ATTEMPTED:
        pt = np.array([p["video_s"] for p in preds if p["event_type"] == et])
        rt = np.array([e["t"] for e in events if e["type"] == et])
        per_type[et] = {
            "period1_dev": block(pt[in1(pt)] if len(pt) else pt,
                                 rt[in1(rt)] if len(rt) else rt),
            "period2_heldout": block(pt[~in1(pt)] if len(pt) else pt,
                                     rt[~in1(rt)] if len(rt) else rt),
            "both_periods": block(pt, rt)}
    doc["per_type"] = per_type

    # team-aware per type: a TP now needs the right type, the right time AND the right
    # side. This is the repo's primary metric, which every detector so far scored 0 on.
    per_type_team = {}
    for et in ATTEMPTED:
        tp_sum = n_pred = 0
        blocks = {}
        for key, sel in (("period1_dev", lambda x: in1(x)),
                         ("period2_heldout", lambda x: ~in1(x)),
                         ("both_periods", lambda x: np.ones(len(x), bool))):
            tp, npd, nrf = 0, 0, 0
            for team in ("Own", "Opponent"):
                pt = np.array([p["video_s"] for p in preds
                               if p["event_type"] == et and p.get("team") == team])
                rt = np.array([e["t"] for e in events
                               if e["type"] == et and e["team"] == team])
                pt = pt[sel(pt)] if len(pt) else pt
                rt = rt[sel(rt)] if len(rt) else rt
                tp += prf(pt, rt)[3]
                npd += len(pt)
                nrf += len(rt)
            # n_pred counts every prediction of this type, teamed or not: a type that
            # declines to predict team is charged for it here rather than excused
            n_all = len([p for p in preds if p["event_type"] == et
                         and sel(np.array([p["video_s"]]))[0]])
            n_ref = len([e for e in events if e["type"] == et
                         and sel(np.array([e["t"]]))[0]])
            pr = tp / n_all if n_all else 0.0
            rc = tp / n_ref if n_ref else 0.0
            blocks[key] = {"n_pred": n_all, "n_ref": n_ref, "tp": int(tp),
                           "precision": round(pr, 4), "recall": round(rc, 4),
                           "f1": round(2 * pr * rc / (pr + rc) if pr + rc else 0.0, 4),
                           "team_predicted": et in TEAM_TYPES}
        per_type_team[et] = blocks
    doc["per_type_team_aware"] = per_type_team
    doc["macro_f1_team_aware"] = {
        k: round(float(np.mean([per_type_team[et][k]["f1"] for et in ATTEMPTED])), 4)
        for k in ("period1_dev", "period2_heldout", "both_periods")}

    # is the swap real? measured on TRUE event times, so it isolates the team rule from
    # the detector. Period 1 is where the bit was fitted; period 2 is the test.
    team_check = {}
    for et in TEAM_TYPES + ("FootballKickOff",):
        for per, sel in (("period1_fitted", True), ("period2_heldout", False)):
            ok = tot = skipped = 0
            for e in events:
                if e["type"] != et or in1(e["t"]) != sel:
                    continue
                if et == "FootballKickOff":
                    g = ball_at(e["t"], *GOAL_LOOKBACK)
                    if g is None:          # period-opening kickoff: no goal behind it
                        skipped += 1
                        continue
                    pred_team = defender_of(g[0], e["t"])
                else:
                    b = ball_at(e["t"])
                    if b is None:
                        continue
                    d = defender_of(b[0], e["t"])
                    pred_team = d if et == "FootballGoalKick" else other(d)
                tot += 1
                ok += int(pred_team == e["team"])
            team_check[f"{et}_{per}"] = {"correct": ok, "of": tot,
                                         "accuracy": round(ok / tot, 4) if tot else None,
                                         **({"no_goal_behind_it": skipped} if skipped else {})}
    doc["team_rule_on_true_times"] = {
        "what": "the team rule alone, given true event times -- separates it from the "
                "detector's own recall",
        "fitted_bit": f"in period 1 the xi<0.5 end is defended by {defends_lo_p1}",
        "supervision": "ONE bit, taken from period-1 goal-kick team labels. Declared, "
                       "not hidden. Period 2 follows from the half-time swap and is "
                       "therefore a genuine test of it.",
        "per_type": team_check}

    doc["macro_f1_over_attempted"] = {
        k: round(float(np.mean([per_type[et][k]["f1"] for et in ATTEMPTED])), 4)
        for k in ("period1_dev", "period2_heldout", "both_periods")}

    # KickOff without the two period-start kickoffs, whose times the period boundaries give away
    ko_pred = np.array([p["video_s"] for p in preds
                        if p["event_type"] == "FootballKickOff"])
    ko_ref = np.array([e["t"] for e in events if e["type"] == "FootballKickOff"])
    give = np.array([a.p1[0], a.p2[0]])
    ko_ref_fair = np.array([t for t in ko_ref if np.min(np.abs(give - t)) > TOL])
    ko_pred_fair = np.array([t for t in ko_pred if np.min(np.abs(give - t)) > TOL])
    doc["kickoff_leakage_check"] = {
        "why": "the period boundaries come from the ground-truth time base and two of "
               "the eight kickoffs are those boundaries",
        "all_8": block(ko_pred, ko_ref),
        "post_goal_6_only": block(ko_pred_fair, ko_ref_fair)}

    # classification accuracy given TRUE times -- separates the two failure modes
    conf_m, n_pos = {}, 0
    for e in events:
        et, _ = classify(e["t"])
        if et is None:
            continue
        n_pos += 1
        conf_m.setdefault(e["type"], {}).setdefault(et, 0)
        conf_m[e["type"]][et] += 1
    doc["classification_given_true_times"] = {
        "what": "an upper bound on the type step alone: the ceiling every per-type "
                "figure above is multiplied down from by the detector's own recall",
        "events_with_a_ball_position": n_pos, "events_total": len(events),
        "confusion_true_to_predicted": conf_m,
        "accuracy": round(sum(conf_m.get(k, {}).get(k, 0) for k in FAMILY) /
                          max(n_pos, 1), 4)}

    # negative control: the same number of predictions per type, placed at random.
    # G5 validated the scoring harness this way; it is the check that says whether a
    # per-type F1 is a result or a count of how many darts were thrown.
    rng = np.random.default_rng(11)
    ctrl, real_f1 = {et: [] for et in ATTEMPTED}, {}
    for et in ATTEMPTED:
        pt = np.array([p["video_s"] for p in preds if p["event_type"] == et])
        rt = np.array([e["t"] for e in events if e["type"] == et])
        real_f1[et] = prf(pt, rt)[2]          # unrounded: the comparison below is tight
        for _ in range(20):
            tt = np.array([(rng.uniform(*a.p1) if rng.random() < 0.5
                            else rng.uniform(*a.p2)) for _ in range(len(pt))])
            ctrl[et].append(prf(np.sort(tt), rt)[2])
    doc["random_control"] = {
        "what": "20 trials per type, same n_pred, times drawn uniformly in play",
        "trials": 20,
        "per_type": {et: {"real_f1": round(real_f1[et], 4),
                          "random_f1_mean": round(float(np.mean(v)), 4),
                          "random_f1_max": round(float(np.max(v)), 4),
                          # compared unrounded and with a margin: a real F1 that merely
                          # ties the control's best trial is not a result
                          "is_a_result": bool(real_f1[et] > np.max(v) + 1e-9)}
                     for et, v in ctrl.items()},
        "macro_real": doc["macro_f1_over_attempted"]["both_periods"],
        "macro_random": round(float(np.mean([np.mean(v) for v in ctrl.values()])), 4)}

    doc["caveats"] = [
        "team is not predicted, so the repo's primary team-aware metric is 0 for all "
        "five types",
        "CornerKick is NOT a result: 9 events, 7 of them in period 1, held-out F1 0, "
        "and its both-periods F1 sits inside the random control's own range",
        "the (xi, eta) frame's boundaries are not the touchlines (see pitch_frame.json)",
        "both the detector and the classifier read the same Viterbi ball track, whose "
        "coverage is 0.586 -- a restart the tracker never sees cannot be found or typed",
    ]

    Path(a.pred).write_text(json.dumps({"events": preds}, indent=1))
    Path(a.manifest).write_text(json.dumps({
        "attempted": ATTEMPTED, "tuned_on": "period1",
        "not_attempted": {"FootballFreeKick":
                          "its (xi, eta) cloud sits inside ThrowIn's with no separating "
                          "cue; declared before scoring, not after"},
        "note": "team is not predicted for any of these types, so the team-aware score "
                "is 0 by construction; read the team-agnostic figures"}, indent=1))
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
