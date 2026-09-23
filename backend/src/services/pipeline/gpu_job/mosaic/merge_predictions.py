#!/usr/bin/env python3
"""Merge per-detector prediction sets into the one the repo quotes as its headline.

Each detector writes its own `pred_*.json` / `manifest_*.json` so it can be scored in
isolation. The benchmark's macro-F1 is over *all* attempted types at once, so they have
to be pooled -- and the manifests pooled with them, because the harness refuses to score
without one and the attempted set is the whole point of it.

`team` is carried through when a detector predicts it and left absent when it does not.
Absent is not the same as wrong: the harness matches per (type, team), so a type with no
team simply scores 0 on the team-aware side, which is the honest outcome.
"""
import argparse, json, sys
from pathlib import Path

KEEP = ("video_s", "event_type", "team", "period")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", nargs="+", required=True, help="pred_*.json to pool")
    ap.add_argument("--manifest", nargs="+", required=True, help="their manifests, in order")
    ap.add_argument("--out-pred", required=True)
    ap.add_argument("--out-manifest", required=True)
    a = ap.parse_args()
    if len(a.pred) != len(a.manifest):
        raise SystemExit("each --pred needs its own --manifest, in the same order")

    events, attempted, not_attempted, tuned = [], [], {}, set()
    for pf, mf in zip(a.pred, a.manifest):
        for e in json.loads(Path(pf).read_text())["events"]:
            events.append({k: e[k] for k in KEEP if k in e})
        man = json.loads(Path(mf).read_text())
        attempted += man.get("attempted", [])
        not_attempted.update(man.get("not_attempted", {}))
        tuned.add(man.get("tuned_on", "unstated"))

    dupes = {t for t in attempted if attempted.count(t) > 1}
    if dupes:
        raise SystemExit(f"two detectors both claim {sorted(dupes)} -- pick one")

    Path(a.out_pred).write_text(json.dumps(
        {"events": sorted(events, key=lambda e: e["video_s"])}, indent=1))
    Path(a.out_manifest).write_text(json.dumps({
        "command": " ".join(sys.argv),
        "attempted": sorted(attempted),
        "tuned_on": tuned.pop() if len(tuned) == 1 else "mixed: " + ", ".join(sorted(tuned)),
        "not_attempted": not_attempted,
        "note": "team is predicted only for the types whose predictions carry a 'team' "
                "field; the rest score 0 on the team-aware side by construction",
    }, indent=1))
    print(f"{len(events)} predictions, {len(attempted)} attempted types "
          f"-> {a.out_pred}, {a.out_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
