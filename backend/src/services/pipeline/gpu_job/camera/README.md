# Camera motion as an event signal (D-0)

The footage is a **ball-following virtual crop** of a fixed Veo panorama. D-0's bet was
that the crop's own pan/zoom trajectory already encodes the match state, so events could
be read off it with **no pitch calibration at all** — which matters, because calibration
has failed three times (see `../pitch/README.md` and `STATE.md`).

**Verdict: D-0 is falsified as specified.** It was worth the ~30 minutes it cost, because
the way it failed is a measurement that constrains D-A.

Everything here runs on CPU against the local 720p proxy — no GPU, so none of it was
blocked by the Tailscale outage.

## Scripts, in the order they were used

| script | question it answers |
| :-- | :-- |
| `falsify_halftime.py` | the pre-registered kill-test: does the trajectory show the 795 s halftime gap? |
| `detect_restarts.py` | follow-up: can kickoffs be detected from camera motion alone? |
| `measure_drift.py` | why both failed: how far does chained registration drift? |

## Result 1 — registration is not the problem

Full match, 2 fps, 12,343 pairs: **median 612 RANSAC inliers, 99.6 % above the
min-inliers=100 gate**, 11 min of CPU for 103 minutes of video. Dense registration works.

## Result 2 — "stoppage = static camera" is FALSE

The pre-registered test failed 2 of 3 criteria (AUC 0.613 vs 0.80; median ratio 1.70 vs
2.0). Veo's virtual camera **keeps roaming during halftime** at a median ~10 px/s,
tracking warm-up activity on an otherwise empty pitch, and play contains plenty of slow
stretches. Camera *speed* barely separates the two.

A tempting repair is *sweep* — how far the camera ranged over the last W seconds — which
reaches AUC 0.80 at W=60 s and 0.91 at W=240 s. **Do not quote those numbers.** They were
selected post-hoc on the same window, and the gain comes from W fitting inside the 795 s
halftime; at the few-second scale of the 64 `FootballOutOfPlay` events it buys nothing.

## Result 3 — the positional claim is TRUE, but unreachable by integration

D-0 also predicted "kickoff = the camera returns to the same central view". That is
**correct**, and kickoffs are a free ground truth for it: all 8 are restarts from the
centre circle, so those frames must show near-identical views.

Registering the kickoff frames directly against each other confirms it — but integrating
the same offset along the trajectory does not:

| between kickoff frames (20 gated pairs of 28) | median | max |
| :-- | --: | --: |
| **direct** registration — the true view offset | **58 px** | 122 px |
| **chained** integration of per-pair `dx` | **616 px** | 1490 px |

**Drift factor 10.6x.** The worst chained error is a third of the camera's entire 4578 px
pan range, so the trajectory's absolute position is meaningless over match timescales —
which is why the kickoff detector put all 8 predictions in period 2 and scored 0/8.

Over a 30-minute window the integrated pan looks bounded and well-behaved. It is not.
Only the full-match span exposes the secular drift, so **do not validate this on a short
window**.

## The lesson worth keeping

Two things that look equivalent are not: *speed* (how fast the view moves) and *sweep*
(how far it ranged). A camera fidgeting in place has high speed and low sweep, and only
sweep distinguishes it from play.

And the one that matters for D-A: **absolute camera position must come from registration
to an anchor, never from chaining frame-to-frame.** The anchor/set-cover design in D-A is
therefore not one option among two — it is required, and this is the measurement that
says so.
