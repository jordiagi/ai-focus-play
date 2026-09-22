#!/usr/bin/env python3
"""G6 — ingest the D-B detector output so `analysis_mode="ml"` is a real thing.

`main.py` has advertised `"ml"` in `supported_analysis_modes` since the API was written,
and the database has had the column just as long, but **nothing could ever produce it**:
`cv_engine.py` only reports `mode: "demo"`, and no ingest existed. This closes that gap.

It deliberately does **not** go through `cv_engine.py`, which is frozen as the demo
fallback by an earlier decision. It reads the scored prediction set the mosaic pipeline
writes (`pred_all.json` + `manifest_all.json` + `score_all.json`), maps it onto the app's
vocabulary, and writes events, the capability surface and the mode.

What it will not do, and why each refusal matters:

* **No metric positions.** D-A failed to calibrate this footage five times; D-B works in
  panorama pixels and has no metres. `Event.pitch_x/pitch_y` used to default to
  (52.5, 34.0) -- the centre spot -- so ingesting without a position would have silently
  claimed every event happened on the centre spot. They are now optional and this writes
  `None`.
* **No analytics.** Possession, shot map and team stats come from the demo/heuristic
  engine. Leaving them beside ML events would present one pipeline's numbers as the
  other's, so any existing analytics row is **dropped**, and the stats tab serves 404
  rather than the wrong provenance. Tier B (G4) is what would fill it honestly.
* **No team where team is not a result.** Types whose team channel fails its own random
  control are ingested with the team omitted rather than guessed; the metric rewards
  guessing over abstaining, and this must not take that bait.
* **No jerseys or player names.** No roster exists (confirmed with the user), so
  `player_jersey` and `player_name` stay null.

The capability surface is the honest part. For each of the app's 16 labels it records
`detected` with a count, `not_attempted`, or `unavailable` with a reason -- and the
reasons here are the measured ones, not placeholders.
"""
import argparse, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.src.domain.models.match import Event, EventCapability  # noqa: E402

# benchmark type -> the app's label. OutOfPlay had no label until it was added to the
# vocabulary: Veo reports it and it is the largest Tier A type, so a surface that cannot
# name it cannot report it.
TYPE_TO_LABEL = {
    "FootballOutOfPlay": "Out of play",
    "FootballThrowIn": "Throw-in",
    "FootballGoalKick": "Goal kick",
    "FootballCornerKick": "Corner",
    "FootballKickOff": "Kickoff",
    "FootballGoal": "Goal",
    "FootballShot": "Shot",
    "FootballFreeKick": "Free kick",
    "FootballFoul": "Foul",
    "interception": "Interception",
    "tackle": "Tackle",
    "dribble": "Dribble",
    "loose": "Loose ball recovery",
    "save": "Save",
}

# Veo labels the uploading side "Own"; the app calls the same side "home". This is a
# convention, not a measurement, and it is recorded in the ingest report as one.
TEAM_TO_SIDE = {"Own": "home", "Opponent": "away"}

# Pinned to analysis_mode="demo" by the repository; see the refusal in main().
DEMO_MATCH_ID = "demo-arlington-skyline"

# Types whose team channel does not clear `control_team_shuffle.py`. Their events are
# ingested without a team rather than with a guessed one.
TEAM_NOT_A_RESULT = {"FootballOutOfPlay"}

# Why each label the ML pipeline does not deliver is missing. Measured reasons only.
UNAVAILABLE = {
    "Free kick": "not attempted: its position cloud sits inside Throw-in's with no "
                 "separating cue (D-B step 10)",
    "Shot": "not attempted: needs shot direction toward a goal mouth, which needs the "
            "metric calibration D-A failed to obtain",
    "Shot on goal": "not attempted: requires shot detection plus an on-target test, "
                    "neither of which exists",
    "Save": "not attempted: requires shot detection first",
    "Foul": "not attempted: no cue measured; whistle audio is not analysed",
    "Tackle": "not attempted: Tier B, needs possession (G4, deferred)",
    "Interception": "not attempted: Tier B, needs possession (G4, deferred)",
    "Dribble": "not attempted: Tier B, needs possession (G4, deferred)",
    "Loose ball recovery": "not attempted: Tier B, needs possession (G4, deferred)",
    "Pass": "not attempted: Tier B, needs possession (G4, deferred)",
}


def build(pred, manifest, score, match_id, half_offsets=None):
    """Turn the prediction set into events plus a capability surface."""
    attempted = set(manifest.get("attempted", []))
    agnostic = (score or {}).get("team_agnostic", {})
    aware = (score or {}).get("overall", {})

    events, per_label = [], {}
    for p in pred.get("events", []):
        et = p["event_type"]
        label = TYPE_TO_LABEL.get(et)
        if label is None:
            continue                       # nothing in the vocabulary can name it
        team = p.get("team")
        side = TEAM_TO_SIDE.get(team) if (team and et not in TEAM_NOT_A_RESULT) else None
        f1 = (agnostic.get(et) or {}).get("f1")
        bits = [f"{label} detected by the D-B pixel-space pipeline"]
        if f1 is not None:
            bits.append(f"type F1 {f1:.3f}")
        if side is None:
            bits.append("team not predicted")
        events.append(Event(
            match_id=match_id,
            timestamp=float(p["video_s"]),
            period=int(p.get("period", 1)),
            event_type=label,
            # The schema requires a team and the column is NOT NULL on existing
            # databases, so an unteamed event carries the explicit third value
            # "unknown" rather than being parked on "home". Nothing in the UI filters
            # events by team today, and "unknown" is the honest answer for a type whose
            # team channel does not clear its control.
            team=side or "unknown",
            player_jersey=None,
            player_name=None,
            description=" — ".join(bits),
            pitch_x=None,                  # no metric calibration exists; see module doc
            pitch_y=None,
            confidence=round(float(f1), 3) if f1 is not None else 0.5,
        ))
        per_label[label] = per_label.get(label, 0) + 1

    caps = {}
    for et, label in TYPE_TO_LABEL.items():
        if et in attempted:
            caps[label] = EventCapability(status="detected", count=per_label.get(label, 0))
    for label, reason in UNAVAILABLE.items():
        # never overwrite a type we actually detected; a measured reason otherwise
        if caps.get(label, EventCapability(status="not_attempted")).status != "detected":
            caps[label] = EventCapability(status="unavailable", reason=reason)
    # anything in the vocabulary we have said nothing about at all
    from backend.src.domain.models.match import default_event_capabilities
    for label in default_event_capabilities():
        caps.setdefault(label, EventCapability(status="not_attempted"))
    return events, caps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--score", default=None)
    ap.add_argument("--match-id", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="build and report, write nothing")
    a = ap.parse_args()

    pred = json.loads(Path(a.pred).read_text())
    manifest = json.loads(Path(a.manifest).read_text())
    score = json.loads(Path(a.score).read_text()) if a.score else {}

    events, caps = build(pred, manifest, score, a.match_id)
    unteamed = sum(1 for e in events if e.team == "unknown")

    report = {
        "job": "G6: ingest D-B detections as analysis_mode=ml",
        "command": " ".join(sys.argv),
        "match_id": a.match_id,
        "events_in": len(pred.get("events", [])),
        "events_ingested": len(events),
        "dropped_no_label": len(pred.get("events", [])) - len(events),
        "per_label": {k: v.count for k, v in caps.items() if v.status == "detected"},
        "events_without_team": unteamed,
        "positions": "none -- no metric calibration exists, pitch_x/pitch_y are null",
        "analytics": "dropped -- demo/heuristic numbers must not sit beside ML events",
        "team_convention": "Veo 'Own' -> app 'home'; a convention, not a measurement",
        "team_withheld_for": sorted(TEAM_NOT_A_RESULT),
        "capabilities": {k: v.model_dump() for k, v in caps.items()},
    }

    if not a.dry_run:
        from backend.src.storage.repository import MatchRepository
        # The seeded demo match is pinned to analysis_mode="demo" by the repository on
        # every construction -- that pin is what keeps the demo honestly labelled, and
        # probe d4 depends on it. Writing ML events there would leave them presented
        # under a "demo" label, which is a provenance lie. Refuse instead of fighting it.
        if a.match_id == DEMO_MATCH_ID:
            print(f"REFUSING: {DEMO_MATCH_ID!r} is the seeded demo match and is pinned "
                  f"to analysis_mode='demo'. Ingesting there would present ML events "
                  f"under a demo label. Ingest into a real match.", file=sys.stderr)
            return 2
        repo = MatchRepository()
        match = repo.get_match(a.match_id)
        if match is None:
            print(f"REFUSING: no match {a.match_id!r} in the database", file=sys.stderr)
            return 2
        repo.set_events(a.match_id, events)
        dropped = repo.clear_analytics(a.match_id)
        match.analysis_mode = "ml"
        # "medium" not "high": 6 of 14 types, 32 % of event mass, precision 0.21-1.00
        match.analysis_confidence = "medium"
        match.event_capabilities = caps
        repo.save_match(match)

        # Read it back and check what the DATABASE says, not what we sent. The first
        # version of this script passed pitch_x=None and the rows came back at
        # (52.5, 34.0), because a SQLAlchemy column default fires on an explicit None --
        # the model said "unknown" and the row said "centre spot". Verify, do not trust.
        back = repo.get_match(a.match_id)
        stored = repo.get_events(a.match_id)
        counts = {}
        for e in stored:
            counts[e.event_type] = counts.get(e.event_type, 0) + 1
        problems = []
        if back.analysis_mode != "ml":
            problems.append(f"analysis_mode came back {back.analysis_mode!r}, not 'ml'")
        if len(stored) != len(events):
            problems.append(f"{len(events)} events written, {len(stored)} read back")
        bad_pos = [e for e in stored if e.pitch_x is not None or e.pitch_y is not None]
        if bad_pos:
            problems.append(f"{len(bad_pos)} events came back with a pitch position "
                            f"though none was written (e.g. {bad_pos[0].pitch_x}, "
                            f"{bad_pos[0].pitch_y}) -- a column default is fabricating it")
        for label, cap in (back.event_capabilities or {}).items():
            if cap.status == "detected" and cap.count != counts.get(label, 0):
                problems.append(f"capability {label!r} claims {cap.count} but "
                                f"{counts.get(label, 0)} events are stored")
        report["verified"] = not problems
        report["problems"] = problems
        report["analytics_row_dropped"] = dropped
        report["written"] = True
        if problems:
            print("INGEST VERIFICATION FAILED:\n  " + "\n  ".join(problems),
                  file=sys.stderr)
            if a.report:
                Path(a.report).write_text(json.dumps(report, indent=1))
            return 3
    else:
        report["written"] = False

    if a.report:
        Path(a.report).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "capabilities"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
