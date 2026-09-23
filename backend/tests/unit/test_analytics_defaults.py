"""Regression tests for the P3-defaults defect (verify.py probe d12).

STATE.md item X1 claims the `pass_strings` fabrication was deleted at c38d62f. The
*producers* (cv_engine.py, repository.py) were fixed to pass real values explicitly,
but the Pydantic field DEFAULTS on AnalyticsData still carried three invented
literals (pass_locations, possession_locations, pass_strings), live until this fix.
Any code path that constructs AnalyticsData without those fields -- like the stub in
test_export_zip.py -- silently materialised a fabricated decay curve.

These tests inspect the model's own defaults directly, not engine output (that is
what makes them different from d10, which only ever sees the real engine's explicit
values and would never catch a fabricated default).
"""
from backend.src.domain.models.match import AnalyticsData, TeamStats


def _fresh():
    return AnalyticsData(home_stats=TeamStats(), away_stats=TeamStats())


def test_pass_strings_default_is_empty():
    a = _fresh()
    assert a.pass_strings == {"home": [], "away": []}


def test_pass_locations_default_is_empty():
    a = _fresh()
    assert a.pass_locations == {"home": {}, "away": {}}


def test_possession_locations_default_is_empty():
    a = _fresh()
    assert a.possession_locations == {"home": {}, "away": {}}


def test_heatmaps_default_is_empty():
    a = _fresh()
    assert a.heatmaps == {"home": [], "away": []}


def test_no_numeric_literal_in_any_default():
    """A substituted default betrays itself as a plausible-looking number. None of
    the four fields may contain one."""
    a = _fresh()
    for field in ("pass_strings", "pass_locations", "possession_locations", "heatmaps"):
        val = getattr(a, field)
        for side in ("home", "away"):
            series = val[side]
            assert series in ([], {}), f"{field}[{side}]={series!r} is not empty"


def test_defaults_are_not_shared_between_instances():
    """The invented literals were class-level mutable containers (plain dict/list
    defaults), shared across every AnalyticsData instance unless default_factory is
    used. Mutating one instance's field must never leak into a freshly constructed
    instance."""
    a = _fresh()
    b = _fresh()

    a.pass_strings["home"].append(99)
    assert b.pass_strings["home"] == []

    a.pass_locations["home"]["attacking"] = 42.0
    assert b.pass_locations["home"] == {}

    a.possession_locations["home"]["attacking"] = 42.0
    assert b.possession_locations["home"] == {}

    a.heatmaps["home"].append({"x": 1, "y": 1})
    assert b.heatmaps["home"] == []
