#!/usr/bin/env python3
"""P4 problem 1 -- an ML-provenance `AnalyticsData`, not a dropped one.

`ml_ingest.py` used to call `repo.clear_analytics()` for every ML-analysed match: the
demo/heuristic engine's possession, shot map and team stats must not sit beside ML
events (mixing pipelines would misattribute one's numbers to the other), so it dropped
the whole row and let the API 404. That refusal overshot -- the honest middle ground is
an analytics object that carries every row an ML detector's own control actually
cleared, and a measured reason for every row it did not. This module builds that
object; `ml_ingest.py` stores it instead of dropping it.

The rule this follows (`specs/complete-veo-parity/spec.md`, "The rule for which stat
rows may carry a number"): **a row shows a count only if its detector cleared its own
control.** Applied to the 13 `TeamStats` rows against what has actually been measured
in `backend/.local/artifacts/mosaic/`:

* `goals` (`FootballGoal`, F1 0.444, team-aware == team-agnostic) and `throw_ins`
  (`FootballThrowIn`, F1 0.244 team-agnostic, team-channel p = 0.020 in
  `control_team.json`) both clear their control -> counted, per team.
* `corners` (`FootballCornerKick`) is *attempted* -- it has events and a capability
  entry -- but its F1 0.100 exactly ties its own matched-count random control's max
  (`score_restarts.json`'s `random_control.per_type.FootballCornerKick`,
  `is_a_result: false`), so the count is not a measured result. Unavailable.
* `shots`, `free_kicks`, `fouls` were attempted today (commit `070ba47`,
  `score_shots.json` / `score_setpieces.json`) and failed their held-out gates.
  Unavailable, with the measured numbers -- see `ml_ingest.UNAVAILABLE`, which this
  module reuses verbatim so the event-capability surface and the stats table never
  quote the failure two different ways.
* `attempts`, `penalties`, `tackles`, `passes_completed`, `possession_won` have no
  detector at all (or, for `penalties`, a 0/0 reference that cannot be a result).
  Unavailable.
* `possession_percent` / `possession_minutes` were closed by the pre-registered 15 fps
  gate (`486e082`): attribution rose 0.94 -> 0.98 but accuracy stayed at chance and
  shirt AUC was 0.503. Unavailable -- and, per that same rule, `possession_percent`
  must NOT be set to 0.0 either: it is a non-Optional float, so a zero would be exactly
  as invented as its 50.0 default. The `unavailable` map, not the field value, is what
  says "never measured".

Team attribution reuses `ml_ingest`'s `TEAM_TO_SIDE` / `TEAM_NOT_A_RESULT` so an event
that is unteamed here is unteamed the same way in the event list. An event whose team
cannot be resolved is not counted for either side -- guessing a side would be worse
than an undercount, and the metric rewards guessing over abstaining, which is exactly
what must not happen.
"""
import sys
from pathlib import Path
from typing import Any, Dict

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.src.domain.models.match import AnalyticsData, TeamStats  # noqa: E402
from backend.src.services.pipeline.ml_ingest import (  # noqa: E402
    TEAM_TO_SIDE, TEAM_NOT_A_RESULT, UNAVAILABLE,
)

# Benchmark type -> the TeamStats row it fills, for the two types that clear the
# stats-row rule today. Every other type in ml_ingest.TYPE_TO_LABEL either has no
# TeamStats field to fill (Out of play, Goal kick, Kickoff, Interception, ...), or
# does have one but failed its control -- those live in STATS_UNAVAILABLE instead.
_COUNTED_TYPES = {"FootballGoal": "goals", "FootballThrowIn": "throw_ins"}

# Found by adversarial verification AFTER this module was first written, and it
# retracts the rule that produced it.
#
# The original rule was "a row shows a count if its detector cleared its own
# control". `FootballGoal` (F1 0.444) and `FootballThrowIn` (F1 0.244) both clear
# theirs, so both were served as numbers. Then the numbers were read back against
# the reference:
#
#   goals      -- we predict 3, all attributed Own. The match was 3-3. The stats
#                 row would have displayed "3 - 0", which is a scoreline, and a
#                 wrong one. The away 0 is not a measurement that the away side
#                 failed to score; it is the absence of a detection.
#   throw_ins  -- we predict 52 and attribute 46. The reference has 38. The row
#                 would have claimed 46 throw-ins, over-counting by 8, because
#                 precision at F1 0.244 is low.
#
# A stats table states match facts. These detectors do not produce match facts at
# these F1 values -- they produce detections, which is a different claim. Clearing
# a random control makes a detector *a result*; it does not make its count *a
# statistic*. Those are separate bars and only the first was ever tested.
#
# Detection counts already have an honest home: the Events tab capability surface,
# where each label is shown as "detected, n" beside its measured F1. That framing
# is correct and it already passes probe d11. This one is not, so every
# scoreboard-shaped row renders as an em-dash with the reason below.
_SCOREBOARD_SHAPED = {
    "goals": "3 goals detected (FootballGoal, held-out F1 0.444), all attributed to "
             "one side. The reference match was 3-3, so serving this into a score "
             "row would read as 3-0. A detection count is not a scoreline: the "
             "opposing 0 is an absence of detection, not a measured zero. The count "
             "itself is shown, correctly framed, on the Events tab.",
    "throw_ins": "52 throw-ins detected and 46 attributed to a side (FootballThrowIn, "
                 "held-out F1 0.244, team channel p = 0.020). The reference has 38, so "
                 "this row would over-count by 8. Clearing a random control makes the "
                 "detector a result; it does not make its count a match statistic. The "
                 "count is shown, correctly framed, on the Events tab.",
}

# stat-row key -> the measured reason it is not a count. `AnalyticsData.unavailable`
# renders every key here as an em dash plus this text, regardless of what placeholder
# value the corresponding (often non-Optional) TeamStats field carries.
STATS_UNAVAILABLE: Dict[str, str] = {
    "shots": UNAVAILABLE["Shot"],
    "free_kicks": UNAVAILABLE["Free kick"],
    "fouls": UNAVAILABLE["Foul"],
    "corners": (
        "FootballCornerKick real F1 0.100 exactly ties its own matched-count random "
        "control's max (0.100) over 20 trials, is_a_result=false "
        "(score_restarts.json random_control.FootballCornerKick); events are still "
        "detected and listed, but the count is not a measured result"
    ),
    "attempts": (
        "no detector distinct from `shots`, which itself failed its held-out gate "
        "(see the `shots` row) -- there is no separate signal to count a broader "
        "attempt tally from"
    ),
    "penalties": (
        "0 penalties in the 447-event reference benchmark; \"0/0 matching\" is not a "
        "result (specs/complete-veo-parity/spec.md sec 2)"
    ),
    "tackles": UNAVAILABLE["Tackle"],
    "passes_completed": UNAVAILABLE["Pass"],
    "possession_won": (
        "not attempted: Tier B, needs possession (G4, deferred) -- the same closure "
        "as tackles and interceptions, which is what winning the ball back would be "
        "measured from"
    ),
    "possession_percent": (
        "Tier B closed by the pre-registered 15 fps gate: attribution rose 0.94 -> "
        "0.98, accuracy stayed at chance, shirt AUC 0.503 (486e082)"
    ),
    "possession_minutes": (
        "Tier B closed by the pre-registered 15 fps gate: attribution rose 0.94 -> "
        "0.98, accuracy stayed at chance, shirt AUC 0.503 (486e082)"
    ),
}


def build_ml_analytics(pred: Dict[str, Any], manifest: Dict[str, Any],
                        score: Dict[str, Any]) -> AnalyticsData:
    """Build an ML-provenance `AnalyticsData` from the mosaic prediction set.

    `manifest` and `score` are accepted (and part of the public signature the
    acceptance harness calls) for parity with `ml_ingest.build()` and so a caller
    already has them on hand -- the two counted rows here come from `pred` alone,
    since `FootballGoal` and `FootballThrowIn` are the only types that both fill a
    `TeamStats` field and clear their own control (see the module docstring). Every
    other row is filled with its measured reason from `STATS_UNAVAILABLE`.
    """
    counts: Dict[str, Dict[str, int]] = {"home": {}, "away": {}}
    for p in pred.get("events", []):
        row = _COUNTED_TYPES.get(p.get("event_type"))
        if row is None:
            continue
        et = p.get("event_type")
        team = p.get("team")
        side = TEAM_TO_SIDE.get(team) if (team and et not in TEAM_NOT_A_RESULT) else None
        if side is None:
            continue  # team not a result for this event -- do not guess a side
        counts[side][row] = counts[side].get(row, 0) + 1

    def _team_stats(side: str) -> TeamStats:
        c = counts[side]
        # `goals` and `throw_ins` are carried so the count is not lost, but BOTH are
        # listed in `unavailable` and therefore render as an em-dash. See
        # _SCOREBOARD_SHAPED below for why a detection count must not be served into
        # a match-statistics row.
        return TeamStats(
            goals=c.get("goals", 0),
            shots=0,
            attempts=None,
            corners=None,
            free_kicks=None,
            throw_ins=c.get("throw_ins", 0),
            fouls=None,
            penalties=None,
            tackles=None,
            passes_completed=None,
            possession_percent=50.0,
            possession_minutes=0.0,
            possession_won=None,
        )

    return AnalyticsData(
        home_stats=_team_stats("home"),
        away_stats=_team_stats("away"),
        shot_map=[],
        pass_locations={"home": {}, "away": {}},
        possession_locations={"home": {}, "away": {}},
        pass_strings={"home": [], "away": []},
        heatmaps={"home": [], "away": []},
        provenance="ml",
        unavailable={**STATS_UNAVAILABLE, **_SCOREBOARD_SHAPED},
    )
