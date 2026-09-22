#!/usr/bin/env python3
"""The control that any team claim has to clear: replace the team, keep everything else.

**The team-aware metric rewards guessing over abstaining, and by a lot.** A prediction
with no team scores 0 on the team-aware side; a prediction with a *randomly chosen* team
is right about half the time. So assigning coin-flip teams to the throw-ins lifts macro
from 0.229 to ~0.260 while containing no information whatsoever.

That makes "the primary metric went up" worthless on its own as evidence. Every team
channel has to be scored against the same predictions with the team replaced by:

  * a coin flip (the real null -- 40 trials)
  * a constant, each side in turn (catches a channel that has only learned the prior)
  * nothing at all (shows how much of the gain is merely *having* a team)

The defend-end channels do not need this test to survive it -- GoalKick and Goal score
*identically* team-aware and team-agnostic, meaning every true positive carries the right
side, which no coin flip can do. The shirt-colour channel does need it, and passes on the
type it is about: ThrowIn F1 0.178 against a random maximum of 0.156 over 40 trials.

Its macro margin is thin (0.274 against a random maximum of 0.274) and that is not a
contradiction: most of the macro movement is the OutOfPlay knock-on, which benefits from
*any* team on the throw-ins it chains off, informative or not.
"""
import argparse, copy, json, subprocess, sys, tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]


def run_chain(events, art, tmp, py):
    """Re-run everything downstream of the restart predictions, then score."""
    pr = tmp / "pr.json"
    pr.write_text(json.dumps({"events": events}))
    q = lambda *c: subprocess.run(c, capture_output=True)
    q(py, str(HERE / "detect_out_of_play.py"), "--track", str(art / "ball_track.json"),
      "--restart-pred", str(pr), "--pred", str(tmp / "po.json"),
      "--manifest", str(tmp / "mo.json"), "--out", str(tmp / "so.json"))
    q(py, str(HERE / "merge_predictions.py"),
      "--pred", str(tmp / "po.json"), str(pr), str(art / "pred_goals.json"),
      "--manifest", str(tmp / "mo.json"), str(art / "manifest_restarts.json"),
      str(art / "manifest_goals.json"),
      "--out-pred", str(tmp / "pa.json"), "--out-manifest", str(tmp / "ma.json"))
    q(py, str(REPO / "scripts/local/score-benchmark.py"), "--pred", str(tmp / "pa.json"),
      "--manifest", str(tmp / "ma.json"), "--json", str(tmp / "sa.json"))
    ov = json.loads((tmp / "sa.json").read_text())["overall"]
    att = [t for t, v in ov.items() if v["status"] == "attempted"]
    return {"ThrowIn": ov["FootballThrowIn"]["f1"],
            "OutOfPlay": ov["FootballOutOfPlay"]["f1"],
            "macro": round(float(np.mean([ov[t]["f1"] for t in att])), 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--restart-pred", required=True, help="the teamed restart predictions")
    ap.add_argument("--type", default="FootballThrowIn", help="the type whose team is replaced")
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    art = Path(a.artifacts)
    base = json.loads(Path(a.restart_pred).read_text())["events"]
    # only predictions the channel actually teamed are eligible for replacement
    eligible = lambda e: e["event_type"] == a.type and "team" in e

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        doc = {"job": "control: replace the team, keep the predictions",
               "command": " ".join(sys.argv), "type": a.type, "trials": a.trials,
               "real": run_chain(base, art, tmp, a.python)}

        for fixed in ("Own", "Opponent"):
            ev = copy.deepcopy(base)
            for e in ev:
                if eligible(e):
                    e["team"] = fixed
            doc[f"always_{fixed}"] = run_chain(ev, art, tmp, a.python)

        ev = copy.deepcopy(base)
        for e in ev:
            if e["event_type"] == a.type:
                e.pop("team", None)
        doc["no_team"] = run_chain(ev, art, tmp, a.python)

        rng = np.random.default_rng(a.seed)
        trials = []
        for _ in range(a.trials):
            ev = copy.deepcopy(base)
            for e in ev:
                if eligible(e):
                    e["team"] = "Own" if rng.random() < 0.5 else "Opponent"
            trials.append(run_chain(ev, art, tmp, a.python))

    for key in ("ThrowIn", "OutOfPlay", "macro"):
        v = np.array([t[key] for t in trials])
        real = doc["real"][key]
        doc[f"random_{key}"] = {
            "mean": round(float(v.mean()), 4), "p90": round(float(np.percentile(v, 90)), 4),
            "max": round(float(v.max()), 4), "real": real,
            "trials_at_or_above_real": int((v >= real).sum()),
            "is_a_result": bool(real > v.max())}
    doc["reading"] = (
        "a team channel is a result only where `is_a_result` is true. The macro row is "
        "the weakest because random teams on this type still feed the OutOfPlay chain.")
    Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
