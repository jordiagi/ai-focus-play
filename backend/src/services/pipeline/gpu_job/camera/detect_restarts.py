#!/usr/bin/env python3
"""D-0 follow-up — can kickoffs be detected from camera motion alone?

WHERE THIS HYPOTHESIS CAME FROM (it is post-hoc, and that changes how to read it).
`falsify_halftime.py` failed its pre-registered test: the camera does NOT go static
during halftime, it keeps roaming at ~10 px/s, so "stoppage = static camera" is wrong
on this footage. But one of its three criteria hit hard -- an automatic changepoint
landed at 3673.75 s against a true H2 kickoff of 3674.4 s, an error of 0.7 s.

That was a period-2 observation. So the signature tested here -- a kickoff is a DWELL
followed by a BURST, i.e. a step up in camera speed -- was formed on period 2 and
period 1 is genuinely held out. That is the reverse of the usual split in this repo
and it is the honest way round here: read the period-1 row as the real result.

Emits PRED.json for `scripts/local/score-benchmark.py`, which prints the
expected-by-chance recall next to every number. A step detector that fires 8 times in
a 6172 s match hits a given kickoff by luck ~0.8% of the time at +/-3 s, so anything
well above that is signal.

No pitch calibration is involved anywhere in this file.
"""
import argparse, csv, json, statistics as st
from pathlib import Path


def median_filter(v, k):
    if k <= 1:
        return list(v)
    h = k // 2
    return [st.median(v[max(0, i - h):min(len(v), i + h + 1)]) for i in range(len(v))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="trajectory CSV from falsify_halftime.py")
    ap.add_argument("--window", type=float, default=20.0,
                    help="seconds either side of the candidate step")
    ap.add_argument("--smooth", type=float, default=2.0, help="median-filter width, s")
    ap.add_argument("--min-sep", type=float, default=60.0,
                    help="non-max suppression; no two kickoffs are closer than this")
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--exclude", type=float, nargs=2, action="append", default=[],
                    help="time spans to suppress, e.g. the halftime gap")
    ap.add_argument("--pred", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default=None, help="diagnostic JSON")
    a = ap.parse_args()

    rows = [r for r in csv.DictReader(open(a.csv)) if r["reliable"] == "True"]
    t = [float(r["t"]) for r in rows]
    s = [float(r["speed_px_s"]) for r in rows]
    if len(t) < 100:
        raise SystemExit("not enough reliable pairs")

    dt = st.median([t[i + 1] - t[i] for i in range(len(t) - 1)])
    s = median_filter(s, max(1, int(round(a.smooth / dt)) | 1))
    w = max(2, int(round(a.window / dt)))

    # step score: how much faster is the camera just AFTER t than just before it
    step = []
    for i in range(len(t)):
        before = s[max(0, i - w):i]
        after = s[i:min(len(s), i + w)]
        if len(before) < w // 2 or len(after) < w // 2:
            step.append(None)
            continue
        step.append(st.median(after) - st.median(before))

    cand = [(step[i], t[i]) for i in range(len(t))
            if step[i] is not None
            and not any(lo <= t[i] <= hi for lo, hi in a.exclude)]
    cand.sort(reverse=True)

    picked = []
    for sc, tt in cand:
        if all(abs(tt - p[1]) >= a.min_sep for p in picked):
            picked.append((sc, tt))
        if len(picked) >= a.topk:
            break
    picked.sort(key=lambda p: p[1])

    events = [{"video_s": round(tt, 2), "event_type": "FootballKickOff",
               "team": "Own", "score": round(sc, 3)} for sc, tt in picked]
    Path(a.pred).parent.mkdir(parents=True, exist_ok=True)
    Path(a.pred).write_text(json.dumps({"events": events}, indent=1))
    Path(a.manifest).write_text(json.dumps({
        "attempted": ["FootballKickOff"],
        "tuned_on": "period2",
        "note": ("signature (dwell->burst step in camera speed) was formed from the "
                 "period-2 kickoff at 3674.4 s; period 1 is the held-out split"),
    }, indent=1))

    doc = {"job": "D-0 kickoff detection from camera motion",
           "params": {"window_s": a.window, "smooth_s": a.smooth,
                      "min_sep_s": a.min_sep, "topk": a.topk, "exclude": a.exclude},
           "pairs_used": len(t), "sample_dt_s": round(dt, 3),
           "predictions": events}
    if a.out:
        Path(a.out).write_text(json.dumps(doc, indent=1))
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
