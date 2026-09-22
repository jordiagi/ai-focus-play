# STATE — live progress tracker

**Purpose:** survive interruption. If you are resuming (any agent, any harness), read
this file first, then `PLAN.md`. Update the status table as you go — a stale status here
is worse than none.

**Last updated:** 2026-09-22 · by Claude Opus 5 · **`analysis_mode="ml"` IS NOW REAL** —
G6 ingests the 6 scored types (210 predictions) into the app with an honest 16-label
capability surface. Primary metric **0.278 as reported, 0.253 conservative**, 32 % of
event mass. Baseline is now **`pass=10 fail=0 skip=0`, 36 pytest tests, frontend builds**
(new probe **d11**, negative-tested). Throw-in team is a result at p = 0.020; OutOfPlay
team is not reachable (three routes dead).

---

## Resume in 60 seconds

1. Read this file, then **`backend/src/services/pipeline/gpu_job/mosaic/README.md`** —
   that is the full record of the panorama, the calibration attempts and D-B. Then
   `context.md` (environment + traps) and `PLAN.md` (roadmap).
2. `bash scripts/local/verify.sh all` must print **`pass=10 fail=0 skip=0`**, and
   `backend/.venv/bin/python -m pytest backend/tests -q` **36 passed**. If not, fix that
   before new work.
2b. **Re-run before you extend.** Run the README's "Reproducing steps 8-14" block and
   check the figures come back. Step 8's originally published numbers did *not*, and that
   was found only by accident — see the incident log. Every score doc now carries the
   `command` that produced it; if a figure's `command` does not match how you ran it, the
   figure is not yours to quote.
3. Ground truth is on disk at `benchmarks/raw/` — 447 events. Never re-derive event
   times from match-clock strings.
4. **gpu-box is the compute, for CPU work too** — 128 cores / 251 GB against this box's
   8 / 15. See `context.md` §5a; ignoring it OOM'd the local machine and silently
   capped a sampling rate.

### Artifacts already computed — do NOT regenerate blindly

`backend/.local/artifacts/mosaic/` is **gitignored**, so it is invisible if you only
read the repo. It holds roughly 25 minutes of GPU + CPU work:

| file | what it is | cost to rebuild |
| :-- | :-- | :-- |
| `panorama.png` | 4414x1190, 125.4° FOV, players dissolved | ~5 min CPU |
| `line_map.png` | per-frame line response warped + accumulated | ~2 min |
| `cameras.json` | per-frame R and focal; **the `frame → panorama` mapping** | the BA above |
| `graph30.json` | 2798 gated homography edges over 186 frames | ~8 min |
| `ball_track.json` | the Viterbi ball track, 10,994 points | ~15 min GPU + reg |
| `occupancy_points.json` | 14,607 player foot points in panorama space | ~20 min |
| `pred_oop.json`, `score_oop.json` | the OutOfPlay detector output and its score | seconds |
| `pitch_frame.json` | the occupancy-derived `(xi, eta)` frame | seconds |
| `pred_restarts.json`, `score_restarts.json` | the 4 restart types and their scores | seconds |
| `pred_goals.json`, `score_goals.json` | Goal, inferred from its kickoff | seconds |
| `players_colour.json`, `pd_035060.json`, `players_predti.json`, `players_pre.json`, `players_ko.json`, `players_dense.json`, `players_oop.json` | player boxes **with shirt colour** at event times — **gpu-box; 10-35 s of GPU each but frame extraction dominates (~4 min for 960)** | needs gpu-box |
| `ball5_frame.json` | ball candidates in **frame** coords (pulled from the box) — what lets players and ball share a space with no registration | needs gpu-box |
| `pred_restarts_teamed.json`, `score_shirt.json` | restarts with throw-in team attached | seconds |
| `control_team.json` | the random-team control | ~2 min |
| `pred_all.json`, `manifest_all.json`, `score_all.json` | all 6 types pooled — the repo's current headline | seconds |

Cheap to regenerate from these: the 80 anchor frames (`f1280`, one ffmpeg pass at the
times in `cameras.json`). **`/workspace` on gpu-box is tmpfs and does not survive a
reboot** — treat the local artifacts directory as the only durable copy.

---

## Status 2026-09-20 — D-B is live and delivering

Work is **mid-flight, not parked**. Everything below is committed and reproducible.

- **Metric calibration (D-A): abandoned for now, after five measured failures.** Ball
  correspondences (1854 m, then 10-15 m), PnLCalib pretrained (88-110 m), 8-D ray-space
  search (degenerate), centre-circle anchor (pose plausible, outline unfitted), event
  azimuths (γ and L only). **There are no metric coordinates.**
- **D-0 (camera motion as the event signal): falsified.**
- **D-B (pixel-space, no metres): working.** Panorama, line map, player occupancy, ball
  track and the first scored detector all exist. See the D-B result below.

---

## Recommended next step

**B21 — raise ball-track coverage / frame rate.** It is now the only item that moves
several numbers at once: coverage 0.586 at 5 fps caps detection, typing *and* teaming,
and it is the named cause of the OutOfPlay-team failure (a struck ball moves ~50 px per
frame, so the contact frame is often never sampled). Re-detecting at 15 fps is ~30 min of
GPU, then the whole chain re-runs from the README's reproduce block and every figure in
this file gets restated. The ingest path is now stable, so the numbers churn once.

After that: **FreeKick (15)** is still unattempted with no candidate cue, **CornerKick**
is still not a result, and **jersey recognition (G7)** remains sequenced last with an
honest ceiling of ~25-40 %.

**Do not retry — all measured dead:** throw-in team by position or by post-throw ball
direction (17/35); thrower by nearest player at the throw-in instant (2 of 36); OutOfPlay
team by chaining off restarts (p = 0.26), by last player contact (attribution 0.94 and
still a coin flip), or by the strike frame (below baseline held out).

Full record: `backend/src/services/pipeline/gpu_job/mosaic/README.md`.

---

## G6 done (2026-09-22) — `analysis_mode="ml"` is real

`main.py` had advertised `"ml"` in `supported_analysis_modes` since the API was written
and the DB had the column, but **nothing could ever produce it**. `ml_ingest.py` closes
that: it reads `pred_all.json` + `manifest_all.json` + `score_all.json` and writes events,
the capability surface and the mode. It does not touch `cv_engine.py`, which stays frozen.

**210 events ingested** across 6 labels — Out of play 127, Throw-in 52, Goal kick 13,
Corner 11, Kickoff 4, Goal 3 — with the other 10 labels marked `unavailable` and a
*measured* reason each.

**Four refusals, each of which would otherwise have been a lie:**

- **No positions.** `Event.pitch_x/pitch_y` are now `Optional` and written `None`.
- **No analytics.** Possession / shot map / team stats come from the demo engine; any
  existing row is **dropped** so the stats tab 404s rather than serving one pipeline's
  numbers beside another's. Tier B (G4) is what would fill it.
- **No team where team is not a result.** OutOfPlay fails its random-team control, so its
  127 events carry `team="unknown"` rather than a guess (134 of 210 events in total).
- **No ingest into the seeded demo match**, which the repository pins to
  `analysis_mode="demo"`. Writing there would present ML events under a demo label, so
  the ingest exits 2 with that explanation.

**The bug this turned up, which only a database read could catch.** `pitch_x`/`pitch_y`
carried a column default of **(52.5, 34.0) — the centre spot** — and SQLAlchemy applies a
scalar default when the value is `None` at INSERT. The ingest passed `None` for "no
metric calibration exists" and **all 210 rows came back on the centre spot**: the model
said unknown, the database said centre spot. The defaults are removed, the ingest now
**re-reads what it wrote and fails loudly** if a position, mode or count disagrees, and
probe **d11** covers it (negative-tested: FAILS with the default restored, PASSES without).

**A vocabulary gap fixed rather than worked around.** The app's event-type list had 15
labels and **no "Out of play"** — though Veo reports it and it is the largest Tier A type
at 64 of 447 events. A surface that cannot name a type cannot report it, so the
vocabulary is now 16 labels (backend defaults, frontend union, sidebar list).

**Confidence is `"medium"`, not `"high"`:** 6 of 14 types, 32 % of event mass, per-type
precision 0.21-1.00.

```sh
backend/.venv/bin/python backend/src/services/pipeline/ml_ingest.py \
    --pred  backend/.local/artifacts/mosaic/pred_all.json \
    --manifest backend/.local/artifacts/mosaic/manifest_all.json \
    --score backend/.local/artifacts/mosaic/score_all.json \
    --match-id <a real match id> --report <report.json>      # --dry-run to preview
```

---

## ⚠ The metric rewards guessing — read before quoting any team number

A prediction with **no** team scores 0 on the team-aware side. A prediction with a
**coin-flip** team is right about half the time. So assigning random teams to the
throw-ins lifts macro from **0.229 to 0.260** while containing no information at all.

**"The primary metric went up" is therefore not evidence.** Every team channel must be
scored against `control_team_shuffle.py`, which replaces the team and keeps everything
else:

| team on ThrowIn | ThrowIn F1 | OutOfPlay F1 | macro |
| :-- | --: | --: | --: |
| **shirt colour (shipped)** | **0.200** | 0.147 | **0.278** |
| always Own | 0.133 | 0.147 | 0.267 |
| always Opponent | 0.067 | 0.105 | 0.249 |
| coin flip, 200 trials — mean | 0.112 | 0.126 | 0.260 |
| coin flip — p99 | 0.200 | 0.178 | 0.281 |
| no team at all | 0.000 | 0.052 | 0.229 |

* **ThrowIn team is a result** — p = **0.020** (3 of 200 random trials reach 0.200).
* **OutOfPlay team (step 13) is NOT** — p = **0.259** (51 of 200). Retracted as a result,
  still emitted and labelled, exactly as CornerKick is.
* The verdict is a **permutation p-value**, not a comparison against the trials' maximum.
  The max criterion tightens as trials grow and turns on one seed's tail; it briefly
  mislabelled an improved channel as a non-result.
* GoalKick and Goal need no control to survive one: they score **identically** team-aware
  and team-agnostic, so every true positive carries the right side, which no coin flip
  can do.

---

## D-B result (2026-09-21) — step 14: throw-in team from the thrower's shirt

gpu-box came back (Tailscale re-auth), so possession could finally be asked about.

**Finding the thrower.** At the instant Veo timestamps, the ball is already in flight —
it falls inside a player box in **2 of 36**, and the second-nearest player is a median
24 px further than the nearest, so "nearest" is a toss-up. *Before* the throw the ball is
in the taker's hands: requiring it inside **exactly one** box at any 5 fps step in
[-2.6,-0.4] s attributes **25 of 38 (0.66)**. The ball is detectable there — present at
37 of 38 throw-ins, at lower confidence (0.44 vs 0.74 after).

**Reading the shirt.** Kits are white against dark navy. Own throwers land at L median
**84**, Opponent at **177**. Threshold and polarity fitted on period 1.

| | n | correct | accuracy | majority baseline | balanced |
| :-- | --: | --: | --: | --: | --: |
| period 1 (fitted) | 10 | 7 | 0.70 | 0.60 | 0.75 |
| **period 2 (held out)** | 15 | 12 | **0.80** | **0.80** | **0.88** |

It **ties its majority-class baseline** held out, because the attributable subsample is
12 Own to 3 Opponent while all 38 throw-ins are roughly even. Balanced accuracy 0.88 vs
0.50 says the colour is informative; n=15 says it cannot be shown that way. The
benchmark-level control above is what settles it.

**A bug found by looking.** The first shirt band (0.15-0.45 of box height) sits on head
and shoulders — cropping the boxes and viewing them showed the swatches were grass and
hair. Sweeping it improved the class medians (97/143 → 84/177) and held-out accuracy
**not at all**, so the visual check was right that the descriptor was wrong and wrong
about it mattering.

**Where it lands:** ThrowIn team-aware **0.000 → 0.178**, macro **0.229 → 0.274**, micro
**0.085 → 0.182**.

---

## D-B result (2026-09-21) — step 13: OutOfPlay team by chaining, and two dead ends

**The chain.** Veo labels an OutOfPlay with the side that put the ball out and the
restart goes to the other side — **exact on 64/64** (throw-ins 39/39, goal kicks 16/16,
corners 9/9). So an OutOfPlay followed by a restart we can team, we can team by
inversion. The dependency runs *backwards through the step numbers* — step 8 now reads
step 10's output — which is the third time this inversion has paid.

Thin channel, honestly: only GoalKick and Corner predictions carry a team, so 41 of 127
OutOfPlay predictions get teamed, 8 of those are also true positives, and the team is
right on **6 of 8**. A relation perfect in the ground truth degrades to what our own
restart predictions are worth. **OutOfPlay team-aware 0.000 → 0.052**, macro 0.220 →
**0.229**, micro 0.057 → **0.085**.

> **⚠ RETRACTED as a result (step 14).** Scored against a random-team control this
> channel is indistinguishable from guessing — 12 of 40 coin-flip trials match or beat
> it. The 64/64 ground-truth relation is still exact; our own restart type-and-team
> predictions are simply wrong often enough that inverting them adds nothing. It is
> still emitted, and labelled, exactly as CornerKick is.

**Dead end 1 — throw-in direction.** The obvious cue (the taker keeps the ball, so it
drifts toward the end they attack) is a **coin flip: 17/35 = 0.486**, and the drift
medians are not even ordered the right way (-0.000 attacking `hi` vs -0.152 attacking
`lo`). A throw-in goes backwards as often as forwards. **Position and direction are now
both exhausted for throw-in team.**

**Dead end 2 — no local compute.** No `torch`/`ultralytics`/`sklearn` in the venv, and
gpu-box needs interactive Tailscale re-auth. Colour separability itself is *not* in
doubt — the kits were viewed: white vs dark navy on uniform green.

---

## D-B result (2026-09-21) — step 12: Goal from its kickoff, and a prediction budget

**Goal, inferred backwards.** The same trick a third time: a goal has no ball signature
of its own, but it is always followed by a kickoff, and the kickoff detector is the most
precise thing here. Goal→kickoff gaps are 37.2, 38.1, 38.2, 53.1 (period 1) and 28.0,
38.5 (period 2) — four of six within 0.4 s of 38.2, at a 3 s tolerance. Offset fitted on
period 1 (38.13 s):

| | n_pred | n_ref | tp | precision | recall | chance | F1 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| period 1 (dev) | 1 | 4 | 1 | 1.000 | 0.250 | 0.001 | 0.400 |
| **period 2 (held out)** | 2 | 2 | 1 | 0.500 | 0.500 | 0.002 | **0.500** |
| both periods | 3 | 6 | 2 | 0.667 | 0.333 | 0.003 | **0.444** |

Team is free and exact: a goal is scored at the end the *conceding* side defends, so the
step-11 map names the conceder and the scorer is the other. **Team-aware = team-agnostic.**
Random control 0.000 mean and max. **Low-n: 6 events, 3 predictions.**

**KickOff team, by the same lookback** — the kickoff after a goal is taken by the side
that conceded. On true times the end is read correctly **6 of 6**; the two period-opening
kickoffs have no goal behind them and are emitted unteamed rather than guessed. The team
rule across all four teamed types is now **30/30 on true event times**.

**A prediction budget, and what it fixed.** Step 8's F1-optimal threshold sat at 187
predictions for 64 events — chance recall 0.209, at which the headline stops meaning
much. F1 is gameable at low precision. The fix: cap `n_pred` at K × `n_ref` on period 1
and take **the smallest K whose period-1 F1 is within 5 % of the unconstrained optimum**,
decided on period-1 data alone. It selects K=3 for OutOfPlay:

| | before | after |
| :-- | --: | --: |
| held-out F1 | 0.383 | **0.467** |
| held-out precision | 0.272 | **0.375** |
| held-out recall / chance | 6.7x | **9.1x** |
| n_pred | 187 | **127** |

**On the restart detector the same rule is a no-op** (optimum already at 1.0x, identical
F1 at every cap) — which is the evidence it is not doing the detector's work.

### Where the benchmark stands

| type | n_ref | n_pred | F1 agnostic | F1 team-aware |
| :-- | --: | --: | --: | --: |
| OutOfPlay | 64 | 127 | 0.356 | 0.147 |
| ThrowIn | 38 | 52 | 0.244 | 0.200 |
| GoalKick | 16 | 13 | 0.276 | **0.276** |
| CornerKick | 9 | 11 | 0.100 | 0.100 |
| **KickOff** | 8 | 4 | **0.667** | **0.500** |
| **Goal** | 6 | 3 | **0.444** | **0.444** |
| **macro** | | | **0.348** | **0.278** |
| **macro, conservative** (channels failing their control zeroed) | | | — | **0.253** |

| | start of 2026-09-20 | now |
| :-- | --: | --: |
| types attempted | 1 | **6** |
| event mass | 14 % | **32 %** |
| macro-F1 team-agnostic | 0.338 | **0.348** |
| **macro-F1 team-aware (primary)** | **0.000** | **0.278** |
| **parity count (F1 >= 0.5)** | **0/14** | **1/14** |

Period-2 macro (0.261) again beats period-1 (0.186). **Every type that predicts team
scores identically team-aware and team-agnostic** — when these detectors fire, they get
the side right. **Caveat worth repeating: macro-F1 over attempted types rewards doing
well on small types, and the two best (KickOff 8, Goal 6) are both low-n.** Micro-F1 is
0.057.

---

## D-B result (2026-09-20) — step 11: team, and the primary metric off zero

Every detector before this scored **0 team-aware by construction**. For two restart
types the laws of the game decide the side: a goal kick is taken by the team **defending**
that end, a corner by the team **attacking** it. That is one bit — which side defends
which end — because the sides swap at half time.

The bit is fitted on period-1 goal-kick team labels; period 2 follows from the swap,
which makes period 2 a genuine test of it. **On true event times the rule is right
24 of 24**, including **8 of 8 on held-out period-2 goal kicks**.

Supporting measurements: our `xi` side agrees with Veo's own pitch-length coordinate on
**14 of 14** goal kicks that carry one, and goal-kick team is separable by
(our `xi` side, period) on **16 of 16**, flipping sign at half time.

| metric | before | now |
| :-- | --: | --: |
| types attempted | 1 | **5** |
| event mass | 14 % | **30 %** |
| macro-F1, team-agnostic | 0.338 | **0.321** |
| **macro-F1, team-aware (primary)** | **0.000** | **0.075** |

GoalKick scores **0.276 identically** team-aware and team-agnostic — every true positive
carries the right side. CornerKick likewise (0.100, but see the control). ThrowIn and
KickOff are declared unteamed: throw-in needs possession, and kickoff needs to know who
conceded — the one positional cue tried (ball drift over [+4,+12] s) does not separate.

**This is one bit of label supervision, and it is named rather than hidden.** Without a
roster or a shirt-colour mapping it cannot be had for free.

---

## D-B result (2026-09-20) — the dead-ball restart family: 5 types, 30 % of event mass

**The consequence relation ran backwards.** Step 8 proposed the OutOfPlay detector as a
candidate generator for the restarts that follow it. Measuring the restart first showed
it is the *stronger* signal and needs no OutOfPlay detector at all — the ball is
stationary at 1-13 px/s beforehand, where every in-play event sits at 125-150. One
detector covers all five dead-ball types, 86 events against OutOfPlay's 64.

**Detection (family pooled, timing only):**

| | n_pred | n_ref | tp | precision | recall | chance | F1 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| period 1 (dev) | 40 | 40 | 19 | 0.475 | 0.475 | 0.049 | 0.475 |
| **period 2 (held out)** | 43 | 46 | 17 | **0.395** | **0.370** | **0.053** | **0.382** |
| both periods | 83 | 86 | 36 | 0.434 | 0.419 | 0.099 | 0.426 |

Unlike step 8 this one *is* mildly optimistic on dev (gap +0.093) — 36 configs were tried
on period 1. Held-out precision 0.395 still beats step 8's 0.359 over a larger type set.

**Per type, end to end** (team-agnostic; `score-benchmark.py` reproduces every row):

| type | n_ref | n_pred | tp | precision | recall | chance | F1 | held-out F1 | vs random control |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | :-- |
| **KickOff** | 8 | 4 | 4 | **1.000** | 0.500 | 0.004 | **0.667** | **0.800** | result |
| GoalKick | 16 | 13 | 4 | 0.308 | 0.250 | 0.013 | 0.276 | 0.267 | result |
| ThrowIn | 38 | 52 | 11 | 0.212 | 0.289 | 0.049 | 0.244 | 0.235 | result |
| CornerKick | 9 | 11 | 1 | 0.091 | 0.111 | 0.011 | 0.100 | 0.000 | **not a result** |

The control is 20 trials per type at the same `n_pred`, times drawn uniformly in play:
macro-F1 **0.019** against the real 0.322. **CornerKick exactly ties the control's best
trial**, which is why it is marked not a result rather than quoted as a small one.

**FreeKick is declared not attempted** in the manifest, before scoring: its position
cloud sits inside ThrowIn's with no cue between them. Given *true* event times the
classifier is right 61 % of the time — that is the ceiling the rows above are multiplied
down from by detection recall.

**Benchmark coverage is now 5 of 14 types, 135 of 447 events (30 % of mass)**, up from 1
type and 14 %. Macro-F1 over the five, team-agnostic: **0.321** (see step 11 for the
team-aware figure, and the step-8 restatement for why this is 0.321 and not 0.325).

**Caveats that travel with it.** Team is predicted only for GoalKick and CornerKick
(step 11); OutOfPlay, ThrowIn and KickOff score 0 team-aware by construction. ThrowIn is
the catch-all — four positive-cue rules were tried
and every one lost on period-1 F1. Both the detector and the classifier read the same
Viterbi track (coverage 0.586). And the (xi, eta) frame is *not* calibrated: its
boundaries land on a detected line no more often than a random curve (0.028 / 0.010 vs
0.040 chance), so it is a monotone re-parameterisation and every threshold on it is
fitted, not geometric.

---

## D-B result (2026-09-20) — step 8, RESTATED (the original figures did not reproduce)

**The figures first published for this detector — period 1 n=51 tp=12 F1 0.296; period 2
n=39 tp=14 F1 0.384; both n=90 tp=26 F1 0.338 — cannot be regenerated.** See the incident
note below. What reproduces, with `min_sep` selected on period-1 F1 (8-cell sweep, 5.0
wins) and the threshold then fitted on period 1:

| unbudgeted (what the restatement first found) | n_pred | n_ref | tp | precision | recall | chance | F1 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| period 1 (dev) | 106 | 30 | 18 | 0.170 | 0.600 | 0.125 | 0.265 |
| period 2 (held out) | 81 | 34 | 22 | 0.272 | 0.647 | 0.097 | 0.383 |
| both periods | 187 | 64 | 40 | 0.214 | 0.625 | 0.209 | 0.319 |

Held-out F1 0.383 lands within 0.001 of the old row, which is a coincidence and not a
vindication: the profile differs throughout (recall 0.647 not 0.412, precision 0.272 not
0.359, 187 predictions not 90).

**187 predictions for 64 events is itself the finding** — chance recall 0.209, so that
0.625 recall is only 3x chance. That is what motivated the prediction budget (step 12).
**The current, quotable figures are the budgeted ones:**

| budgeted, K=3 (current) | n_pred | n_ref | tp | precision | recall | chance | F1 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| period 1 (dev) | 71 | 30 | 13 | 0.183 | 0.433 | 0.085 | 0.257 |
| **period 2 (held out)** | 56 | 34 | 21 | **0.375** | **0.618** | **0.068** | **0.467** |
| both periods | 127 | 64 | 34 | 0.268 | 0.531 | 0.148 | **0.356** |

Held-out recall is **9.1x chance**. The held-out half again scores higher than dev.

**The signature** (medians over 64 events vs 600 random in-play times), re-measured
2026-09-20 because the original figures (196/0.20/35 vs 77/0.53/93) did not reproduce
either: ball speed [-1,+0.5]s **267 vs 93 px/s**; track coverage [+0.5,+3.5]s
**0.13 vs 0.47**; ball speed [+2,+6]s **42 vs 98 px/s**. Every contrast holds in the same
direction and roughly the same size — the ball is struck hard, leaves the field, stops
being trackable, then sits still — so the signature is real and the detector stands.

**Caveats that travel with it.** Team is not predicted for this type, so its team-aware
score is 0 by construction. Precision 0.214. One feature is a *detector
failure* (coverage collapse), legitimate because the event causes it, but it ties the
detector to the tracker's weakness. Benchmark coverage is still 1 of 14 types, 14 % of
event mass.

---

---

## D-B result (2026-09-20) — zones coarse, ball real but trajectory dirty

**A test-design error worth remembering.** Ball association was first scored by
correlating the chosen candidate's azimuth with Veo's pitch-length `x`, against the
camera's aim as baseline. Every selector lost (top-conf 0.824, Viterbi 0.833, nearest-
to-centre 0.846, conf-gated 0.882, camera aim **0.909**). **That test is contaminated:**
Veo's camera aim and Veo's event coordinates are both outputs of Veo's own ball tracker,
so it asks an independent detector to beat Veo at reproducing Veo. The suspiciously
tight 0.82-0.88 band across unrelated selectors was the clue.

**The uncontaminated test.** A kickoff puts the ball on the centre spot, whose panorama
position comes from the fitted centre circle — no Veo tracker involved. Top-confidence
candidate (not nearest-of-five, which would be oracle selection):

| | median distance from the centre spot |
| :-- | --: |
| top-confidence candidate (n=8) | **94 px = 3.0 m** |
| ... conf >= 0.45 (n=6) | **58 px = 1.9 m** |
| arbitrary candidate, any time (control) | 619 px = **20 m** |

Caveats that travel with it: **n = 8**; two of the six confident kickoffs were still
3.6 m and 4.4 m out, so confidence is not a guarantee; and at 5 fps a ±0.1 s timing
offset moves a just-kicked ball a metre or two, so part of the residual is sampling.

**Zones (steps 1-3).** Player occupancy gives a derived pitch region holding 86 % of
players, but its boundary beats chance by only **2.35x** (8 % on a detected line). Good
enough for coarse zone use (Goal), not for "ball crosses a boundary" (corner / throw-in
/ goal kick).

**And the measurement that justifies D-B at all:** inverting the 14,607 player points
onto the fitted ground plane gives a **105.8 x 104.5 m box, aspect 1.01** — a square.
Near the horizon a few pixels is tens of metres. Metres here are unusable; pixel space
is fine.

---

---

## D-B result (2026-09-20) — zones derived, but coarse

| step | state |
| :-- | :-- |
| 1. player detection (gpu-box) | ☑ 600 in-play frames, **15,380 persons**, 16.5 s on one H100 |
| 2. occupancy in panorama space | ☑ **95.7 % registered**, 14,607 foot points, 92 % in one blob |
| 3. pitch region polygon | ◐ **derived and tested — 2.35x chance, not a sharp boundary** |
| 4. ball in panorama space | ☐ not started |
| 5. Tier A detectors + scoring | ☑ 6 types, 32 % of event mass |

**The premise is now measured, not assumed.** Inverting the same 14,607 points onto the
fitted ground plane gives an oriented box of **105.8 x 104.5 m, aspect 1.01** — a square,
where a pitch is ~1.5 — with a 124 m depth spread. Metres are not merely unnecessary
here, they are unusable; pixel space is fine.

**The zone test, run because containing the players is not the same as being the pitch:**

| density pct | area frac | players inside | boundary on a line | chance | lift |
| --: | --: | --: | --: | --: | --: |
| 70 | 0.159 | 0.922 | 0.034 | 0.033 | 1.03 |
| **80** | 0.109 | 0.864 | **0.083** | 0.036 | **2.35** |

Usable as a soft "on the playing surface" test; **not** a touchline. Of D-B's three zone
uses it serves the coarse one (Goal) and not the sharp one (corner / throw-in / goal
kick).

---

---

## D-A result (2026-09-20) — panorama YES, calibration NO

| step | state |
| :-- | :-- |
| 0. is a consistent mosaic possible? | ☑ 3-frame loop closure **0.97 px**, flat in span |
| 1. stitch the panorama | ☑ **4414x1190, 125.4° FOV**, players dissolved |
| 2. line evidence map | ☑ centre circle, halfway, touchlines, penalty areas |
| 3a. which field is ours | ☑ **213/220 event frames located (96.8 %)** |
| 3b. fit the pitch pose | ✗ **pose converges, outline does not** — no metres |

**The pose now agrees across independent methods:**

| quantity | value | agreeing sources |
| :-- | :-- | :-- |
| camera height | **6.71 m** | centre circle (known 9.15 m radius) |
| ground normal | **0.87° off vertical** | centre circle; matches wave correction |
| in-plane rotation γ | **168.6-171.1°** | three routes within 2.5° |
| pitch width W | **68.5-69.8 m** | touchline offset, line-evidence scan |
| centre circle fit | **0.0 px median, 68 % within 3 px** | event cloud confirms it is ours |

**But the outline does not fit:** touchlines 24-39 px out, goal lines 31-51 px, halfway
24 px (<=3 px fractions 0-14 %), while the circle stays at 0.0 px. L stays unstable
(101-120 m, often on a bound).

**Two measurements that removed whole hypotheses:**

- **Not panorama distortion.** Line half-width in the accumulated map grows only
  **1.17x** centre to edge (1.96 → 2.30 px); the panorama registers to a few px
  throughout.
- **Frame centre tracks the ball in azimuth only.** The event cloud is a narrow
  elevation band barely taller than the centre circle — the virtual camera pans and
  zooms but hardly tilts. corr(veo_x, azimuth) = **+0.904** and monotone across all ten
  deciles; corr(veo_z, azimuth) = +0.08. Azimuth-only fit residual **4.9°** against a
  39.9° baseline.
- **Which field is ours is now settled.** The bright foreground curves along the bottom
  of the panorama — which every line fit had been chasing — fall *outside* the play
  region. They belong to a nearer field.

Three degeneracies were found by unit-testing against synthetic ground truth rather
than by reading output: `pitch_model` scaled the penalty areas with the pitch (which is
the only thing breaking the similarity degeneracy); the objective was piecewise
constant, so Nelder-Mead descended a staircase; and letting camera height float has a
**trivial global optimum at h = 0** where all rays collapse to the camera centre — both
scipy optimisers drove straight to it.

---

---

## D-A result (2026-09-20) — panorama YES, calibration NO

| step | state |
| :-- | :-- |
| 0. is a consistent mosaic possible? | ☑ 3-frame loop closure **0.97 px** median, flat in span |
| 1. stitch the panorama | ☑ **4414x1190, 125.4° FOV**, whole pitch, players dissolved |
| 2. line evidence map | ☑ centre circle, halfway, both touchlines, both penalty areas |
| 3. fit the pitch pose | ✗ **pose plausible, pitch does not fit** — no metres |

**The line map was the first big gain.** The RGB median composite is what removes the
players, but it also averages away a 1-2 px line. Detecting lines per frame — where they
are sharp — and compositing the *response* took alignment from 0.096 to 0.26 and median
error from 118 px to 15 px.

**The centre-circle anchor was the second.** A circle of known radius (9.15 m) seen by a
calibrated camera determines the plane, so it pins normal, height and centre at once:

| | 8-D search | centre-circle anchor |
| :-- | :-- | :-- |
| camera height | 1-2 m, **on the bound** | **6.71 m** — plausible for a pole |
| ground normal | unconstrained | **0.87° off vertical** — matches wave correction |
| parameters on bounds | several, every run | **none** |
| pitch size | on bounds | **104.3 x 69.6 m**, read off the line offsets |
| centre circle fit | — | **median 0.0 px, 68 % within 3 px** |

**But no standard pitch aligns with the rest.** An exhaustive 0.5° rotation scan over a
grid of L and W, pose held fixed, never gets the outline above ~25 % within 3 px
(touchlines 16-42 px, goal lines 17-36 px, halfway 17-31 px) while the circle stays at
0.0 px.

**It is not panorama distortion** — the obvious suspect, so it was measured: line
half-width grows only **1.17x** from centre to edge (1.96 → 2.30 px). The panorama
registers to a few pixels throughout.

**It looks like the multi-pitch complex.** Only **one** touchline-parallel line sits at a
pitch-like distance from the fitted circle (-34.9 m, found nine times); a real pitch
centre would have two, symmetric at ±W/2.

Two degeneracies were found and fixed by unit-testing against synthetic ground truth,
not by reading output: letting `h` float has a **trivial global optimum at h=0** (all
rays collapse to the camera centre; both scipy optimisers drove straight to it), and the
parameters span 0.05-200 in magnitude so the solve needs an explicit `x_scale`.

---

---

## D-0 result (2026-09-20) — FALSIFIED, in ~30 min of CPU

The falsification test `specs/deferred.md` demanded was run exactly as pre-registered.
Scripts: `backend/src/services/pipeline/gpu_job/camera/` (README there is the full
record). All CPU, on the local 720p proxy — **not blocked by the Tailscale outage**.

| criterion | result | |
| :-- | --: | :-- |
| C1 ROC AUC of camera speed >= 0.80 | 0.613 | fail |
| C2 median in-play speed >= 2x halftime | 1.70 | fail |
| C3 both boundaries within +/-30 s | 0.7 s / 2825 s | fail |

**The premise was wrong.** "Out of play → camera goes static" is false here: Veo's
virtual camera keeps roaming through halftime at ~10 px/s, following warm-up activity on
an empty pitch. A kickoff detector built on the surviving step signature scored **0/8**.

**Three things worth keeping:**

1. **Dense registration works.** 12,343 pairs at 2 fps over the full match, median
   **612 inliers, 99.6 % above the gate**, 11 min of CPU. Registration is not the weak link.
2. **Kickoffs are a free ground truth for a repeated view.** All 8 are centre-circle
   restarts; registering those frames directly against each other gives a median offset
   of **58 px** (max 122). No calibration, no annotation needed. D-0's positional claim
   was right.
3. **Chaining drifts 10.6x.** Integrating per-pair `dx` reports **616 px** median
   (max 1490) between those same 58 px-apart frames — a third of the full 4578 px pan
   range. Over a 30-minute window the chained trajectory looks bounded and fine; only the
   full match exposes it. **Do not validate registration on a short window.**

Caution for whoever picks this up: *sweep* (how far the camera ranged over the last W s)
reaches AUC 0.80 at W=60 s and 0.91 at W=240 s, but that was selected post-hoc on the
same window and the gain is just W fitting inside the 795 s halftime. It buys nothing at
the few-second scale of the 64 `FootballOutOfPlay` events. Not a result.

---

## Blockers

| Blocker | Impact | Who clears it |
| :-- | :-- | :-- |
| ~~Tailscale SSH to gpu-box expired AGAIN (2026-09-21)~~ | **CLEARED same day** by a human opening the auth URL. `doctor.sh` exits 0; `/workspace` survived (video sha256 `ef7552326b0ab24e`, ball5 output intact). **This expires repeatedly — budget for it.** Fix: run `ssh root@gpu-box`, open the URL it prints | done |
| ~~Tailscale SSH to gpu-box expired~~ (2026-09-20) | Cleared that day; recurred. **This expires repeatedly — budget for it** | see above |
| Veo Bearer token is ephemeral (~minutes) | Only matters if ground truth needs re-capturing; it does not right now | Re-run the capture procedure in `PLAN.md` |

Track 2 (frontend/UI) is **not** blocked by either. All D-0 and D-A work so far is CPU-only
on the local 720p proxy and needed neither.

---

## Ground truth captured (2026-09-19)

Pulled from Veo's own API in an authenticated browser session. **This replaces the old
13-event benchmark, whose second-half timestamps were wrong by up to 752 s.**

| File | Contents |
| :-- | :-- |
| `benchmarks/raw/veo_events_447.csv` | **447 events** — `video_time_ms, period_id, period_time_ms, event_type, team, player_jersey, outcome, x, z`. 14 types. 334 carry a jersey, 355 carry pitch coords |
| `benchmarks/raw/veo_highlights_31.csv` | 31 AI highlight clips (goal / shot_on_goal), clip-start seconds |

Verified on disk: type histogram matches the API exactly; 6 goals in both files.

**Time base (measured, exact, linear):** period 1 `video = period_time + 562`;
period 2 `video = period_time + 3674`. Kickoff 562.3; H1 ends 2879.3; halftime 795 s;
H2 starts 3674.4; last event 6132.1. Halves are 2317.0 s and 2457.7 s — **not 2400**.

**Do not re-derive these from match-clock strings.** That is exactly how the old
benchmark went wrong.

---

## Work package status

Legend: ☐ not started · ◐ in progress · ☑ done & verified · ⊘ blocked · ⏸ deferred by decision · ✗ abandoned

### Cross-cutting (do first, cheap, no GPU)

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| X1 | Delete surviving `pass_strings` fabrication and `or 20.0` thirds fallbacks | ☑ | `c38d62f` |
| X2 | Add probe `d10` — no invented analytics literal anywhere | ☑ | **Negative-tested**: FAILS on pre-fix code, PASSES after |
| X3 | `PitchRadar` must draw nothing for an undetected ball | ☑ | Now renders "Ball not detected" instead |

### Track 1 — GPU pipeline (⊘ blocked on Tailscale re-auth)

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| G0 | Rebuild `benchmarks/veo_reference.json`; fix `scripts/config.env` time base; decode Veo's x/z convention | ☑ | `c38d62f`. Coords decoded: x=length, z=width, absolute. Centre spot lands 2 m off ideal — Veo's own bias, recorded not corrected |
| G1 | **Measure ball-detection rate** — the go/no-go gate | ☑ | **Both halves measured.** tiled 0.833 / 0.828 — **gate passes**. full-frame 0.677 / 0.716 — fails one half. Caveat below: this is candidate presence, not correctness |
| G2 | Pitch calibration | ⏸ **STOPPED** | Three approaches measured and failed (1854 m → 10-15 m → 88-110 m). Cause is structural, not tuning: all pretrained models are broadcast-trained and each of our frames shows too little pitch. Parked as **D-A** in `specs/deferred.md` |
| G3 | Tier A detectors (7 types) | ◐ | **6 of 14 types scored via D-B** (OutOfPlay + 4 restarts + Goal), 32 % of event mass. Macro-F1 **0.348 team-agnostic / 0.278 team-aware** (p = 0.025), micro 0.188, parity 1/14 |
| G4 | Possession HMM → Tier B (4 types + Pass count) | ⏸ | Conditional on G1 gate |
| G5 | Scoring harness (macro-F1, chance baseline, parity count, period split) | ☑ | Built and validated on 4 cases: refuses without manifest; empty→honest zeros; perfect→1.0; **random detector scores BELOW its chance baseline** |
| G6 | Ingest artifacts → `analysis_mode="ml"` | ☑ | **`ml_ingest.py`.** 210 events, 6 labels, 16-label honest surface. Refuses positions, analytics, unteamed guesses and the pinned demo match. Probe **d11**, negative-tested |
| D-A | Panorama + line map (frame → panorama) | ◐ | **BUILT** 2026-09-20: panorama 4414x1190 125.4° FOV; line map shows centre circle, halfway, both touchlines, both penalty areas. Loop closure 0.97 px |
| D-A3 | Ray-space pitch pose fit | ✗ | **Pose converges across 3 independent methods** (h=6.71 m, normal 0.87° off vertical, γ within 2.5°, W 68.5-69.8 m; circle fits 0.0 px / 68%). **But the outline does not** (24-51 px). **No metres.** Recommend D-B instead |
| D-A4 | Play region from Veo events | ☑ | 213/220 event frames located (96.8%). Settles which field is ours; foreground lines are a different pitch. Frame centre tracks the ball in **azimuth only** |
| D-0 | Camera motion as the event signal | ✗ | **Falsified 2026-09-20.** Premise "stoppage = static camera" is false; kickoff detector 0/8. Yielded the 10.6x chaining-drift constraint on D-A |
| G7 | Jersey recognition | ⏸ | Last. **No roster available**, so open-set with abstention, or Veo-label leakage that must be declared. Honest ceiling ~25-40% vs Veo's 75% |

### Track 3 — D-B, pitch-relative detection without metres

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| B1 | Player detection on gpu-box | ☑ | 600 in-play frames, 15,380 persons, 16.5 s on one H100. `detect_players.py` |
| B2 | Occupancy map in panorama space | ☑ | 95.7% registered, 14,607 foot points, 92% in one blob |
| B3 | Pitch region polygon, derived + tested | ◐ | 86% of players inside, boundary **2.35x chance** (8% on-line). Coarse, not a touchline |
| B4 | Ball in panorama space | ☑ | 5 fps, 23,874 frames, **candidate rate 0.8344** over the whole match (G1 measured 0.833/0.828 on slices). 94.1% registered, 36,291 candidates mapped |
| B5 | Ball trajectory (Viterbi + miss state) | ☑ | **Impossible steps 13.6% → 0.1-0.9%.** 58.6% coverage, 10,994 points. Accuracy vs the centre spot at kickoff **5.7 m** (±0.6 s window, n=8) against a 24.5 m control |
| B6 | **FootballOutOfPlay detector** | ☑ **restated + budgeted** | Original figures did not reproduce (see incident note). Under the prediction budget: held-out F1 **0.467**, precision 0.375, recall/chance **9.1x**; both periods F1 0.356 at 127 predictions. Team not predicted |
| B7 | **Dead-ball restart family** (ThrowIn / GoalKick / Corner / KickOff) | ☑ | **KickOff F1 0.667 at precision 1.000** (held-out 0.800); GoalKick 0.276; ThrowIn 0.244; Corner 0.100 = **not a result** (ties the random control). Family timing held-out F1 0.382. `detect_restarts.py` |
| B8 | `(xi, eta)` frame from occupancy | ☑ | `derive_pitch_frame.py`. Quadratic beats linear 2.8x (7.4 vs 20.3 px). **Not the touchlines** — 0.028/0.010 on-line vs 0.040 chance, so all thresholds fitted, none geometric |
| B9 | FreeKick (15) | ⏸ **not attempted, declared** | Position cloud sits inside ThrowIn's with no separating cue; its events land as ThrowIn false positives |
| B10 | Team for GoalKick + Corner | ☑ | **24/24 correct on true times, 8/8 held out.** One fitted bit (which side defends which end in period 1) + the half-time swap. **Takes team-aware macro-F1 from 0.000 to 0.075** — the primary metric off zero for the first time |
| B11 | Team for KickOff (8) | ☑ | Solved by the goal-end lookback, not by drift: the kickoff after a goal is taken by the side that conceded. **6/6 on true times**; the 2 period-opening kickoffs are emitted unteamed |
| B13 | **FootballGoal from its kickoff** | ☑ | **F1 0.444 (held-out 0.500), team-aware = team-agnostic.** Offset 38.13 s fitted on period 1. `detect_goals.py`. Low-n: 6 events, 3 predictions |
| B14 | **Prediction budget** | ☑ | Smallest K with period-1 F1 within 5 % of unconstrained. Lifts OutOfPlay held-out F1 0.383 → **0.467** and its chance-lift 6.7x → **9.1x**; **no-op on the restart detector** |
| B15 | Team for OutOfPlay (64), by chaining | ☑ emitted, **NOT a result** | Relation exact 64/64 in ground truth, but **a coin flip matches it** (12/40 trials ≥ 0.147). Retracted as a result; still emitted and labelled |
| B16 | **Team for ThrowIn (38), from the thrower's shirt** | ☑ | **0.000 → 0.200, a result at p = 0.020.** Held-out colour accuracy 0.83 vs a 0.78 baseline, balanced 0.89 |
| B17 | Player detection with shirt colour | ☑ | `detect_players_colour.py` on gpu-box — times from a file, upper-torso Lab/HSV per box. 4 runs, ~10-22 s each |
| B18 | **`control_team_shuffle.py`** | ☑ | **The control every team claim must clear.** Replaces the team, keeps the predictions. Exposed that random teams alone lift macro 0.229 → 0.260 |
| B19 | Raise thrower attribution above 0.66 | ☑ | **0.66 → 0.79** by padding each box 0.10 x its own height. Diagnosis first: **12 of 13 failures were "ball outside every box", 0 were ambiguous**, 7 missed by only 1.6-32 px — the ball is held above the head. Larger pads catch the wrong player |
| B20 | OutOfPlay team from a direct channel | ✗ **three routes measured dead** | Chain off restarts **p = 0.26**; last contact attributes **0.94** and is still a coin flip; strike frame scores **below baseline** held out. Cause: the last touch is instantaneous, and at 5 fps a struck ball moves ~50 px per frame. **This machinery works where the ball is held, not struck** |
| B21 | Raise ball-track coverage / frame rate | ☐ | **The one remaining item that moves several numbers.** Coverage 0.586 at 5 fps; now the named cause of B20's failure as well as the cap on detection and typing |
| B12 | Reproducibility guard | ☑ | Every detector now writes the **exact command** into its own output. Added after step 8's figures proved unreproducible |

### Track 2 — UI / route parity — ☑ **COMPLETE**

| ID | Work | Status | Notes |
| :-- | :-- | :-- | :-- |
| U1 | Hash router; wire the 6 drawers to Veo's routes; real deep-link Share | ☑ | **codex**, merged `35a0659`. Verified behaviourally: loading `/#/events/` directly opens the panel |
| U2 | Jersey numbers only, never invented names; jersey bar from `lineup` | ☑ | **agy/gemini-3.8-flash-high**, merged `c9054d9`. 36 tests, 0 invented names, follows Veo's blank-number convention |
| U3 | Events drawer type status surface **+ singular stat labels** | ☑ | **codex** (re-dispatch after claude hit a 429 quota limit). Model validator refuses `detected` without a count or `unavailable` without a reason. **Extended 15 → 16 types 2026-09-22**: "Out of play" was missing though Veo reports it and it is the largest Tier A type |

---

## G1 result so far (the gate the roadmap hangs on)

Slice 1200-1800 s of period 1, 3000 frames at 5 fps, `yolo11x`, conf 0.05, COCO
`sports ball`, tiles 3x2 with 0.15 overlap above y=0.22h.

Two slices, one per half, 3000 frames each, so the figure is not a cherry-picked window.

| config | period 1 (1200-1800s) | period 2 (4200-4800s) |
| :-- | --: | --: |
| full frame @1280 | **0.677 — fails** (median gap 0.2s) | 0.716 (median gap **0.4s**, at the limit) |
| **tiled @640** | **0.833 — passes** (0.2s) | **0.828 — passes** (0.2s) |

Tiled is stable at ~0.83 across both halves. Full-frame straddles the gate and fails on
one of them, so it is not merely worse, it is unreliable.

The full-frame configuration is effectively what the Colab notebook used, and it
**misses the gate**. Tiling is what clears it — which is the single most useful thing
this measurement has established.

**Caveat that must travel with this number.** `detection_rate` means a COCO
`sports ball` candidate was present at conf>0.05 *somewhere in the frame*. It does
**not** verify the candidate is the ball — a head or a line marking can fire. This is
candidate presence, not correctness. Do not quote it as tracking accuracy. Trajectory
association plus validation against known ball positions is a separate step, and the
honest per-trajectory number will be lower.

---

## G2 registration — feasibility proven, calibration NOT yet working

### Feasibility: yes, with a measured confidence gate

46 frames across 600-6100 s, SIFT + RANSAC. Median 3231 keypoints per frame, so
features are not the problem. **Inliers do not decay with time separation** — the
constraint is *view overlap*, not drift, because the virtual camera pans across the
pitch and distant views share no content. Anchor placement is set-cover over the pan
range, not over time.

**The confidence gate is measured, not guessed.** Round-trip test (`H_AB · H_BA`
should be identity):

| inliers | round-trip error |
| --: | :-- |
| 678, 271, 181, 126, 74 | **0.31–3.93 px** — excellent |
| 33, 33 | **36–52 px** — garbage |

Registration is bimodal. Use **min_inliers >= 100**. Anchors needed for full coverage
at that gate: **4** (at 50 or 70 it is 3). An earlier "4 anchors → 100%" figure was
computed at min_inliers=30 and was therefore meaningless; re-measured, the conclusion
happens to survive.

### Calibration: TWO attempts failed. Do not retry the same way.

| | attempt 1 (71 restarts, gate 30) | attempt 2 (355 events, gate 100) |
| :-- | :-- | :-- |
| correspondences | 46 | 217 |
| max error | 1854 m — degenerate | 50-81 m — stable |
| median error | 3.3-8.2 m | **10-15 m (worse)** |
| RANSAC inlier fraction | — | **only ~40%** |

The strict gate fixed the degenerate blowups. It did not fix accuracy, and the ~40%
inlier fraction is the tell: **most correspondences do not agree with any single
homography, so the correspondences themselves are bad.** For an interception or tackle
Veo's coordinate marks where the *action* was, not where a detected ball is, and
"best ball candidate anywhere in frame" is unverified — a head or a shoe also fires.

**Conclusion: ball-position correspondences cannot calibrate this. Stop trying.**

### What the footage actually looks like (viewed, not assumed)

This is a **multi-pitch complex**. A single frame contains our match pitch plus **four
or more goals belonging to adjacent fields**, tents, parked cars, a building, crowd,
and a second blue line system crossing diagonally. Two consequences:

- **The camera is low and very oblique.** Our pitch recedes sharply and the far half
  compresses into a thin band, so a few pixels of error there is many metres. That is
  a physical limit, and it is consistent with the 10-15 m median we measured.
- **Most SIFT features are off the pitch plane** — trees, tents, crowd, other pitches.
  A homography fitted through them does not describe the pitch plane, which is the
  plane we actually need.

The anchor at t=960 s is much more promising than the midfield one: it shows a penalty
area with genuinely identifiable landmarks (penalty box corners, six-yard box, goal
posts, penalty arc) and the white match lines are separable from the blue ones.

### The right method: learned pitch-keypoint calibration (researched 2026-09-19)

My two failures shared one root cause: **I used generic SIFT features.** On this footage
those land on trees, tents, parked cars and adjacent pitches — all *off the pitch plane*,
which is the one plane we need. The established solution does not use generic features at
all.

This is a solved research problem with an annual benchmark — the **SoccerNet Camera
Calibration challenge**. The pitch is a planar target of known dimensions, so a homography
follows from four lines. 2025-era pipelines (NBJW, **PnLCalib**, Broadtrack) all do
*learned landmark/line detection* then solve for the camera. Semantics is exactly what
fixes our multi-pitch problem: a model trained on pitch classes knows a halfway line from
a stray blue line on an adjacent field.

**PnLCalib is installed and running on the box** (`/opt/PnLCalib`, weights `SV_kp` /
`SV_lines`, GPL-2.0 — fine locally, relevant only if this is ever distributed).

Measured across 46 frames. **Coverage is not accuracy**, so each calibration was scored
by projecting the known 105x68 pitch model back into the image and measuring how much of
it lands on real white-line pixels (bright + desaturated; the other field's lines are
blue and saturated, so they are excluded by construction). This test needs no ball
detection and no Veo coordinates, so it cannot be fooled by the noise that broke the
SIFT attempts.

| thresholds | calibrated | median alignment | well-aligned (>=0.50) |
| :-- | --: | --: | --: |
| 0.3434 / 0.7867 (default) | 12/46 | 0.26 | 4 (9%) |
| **0.15 / 0.30 (best)** | 27/46 | **0.29** | **12 (26%)** |
| 0.10 / 0.20 | 39/46 (85%) | 0.19 | 11 (24%) |

Dropping the threshold to 0.10 lifts "success" to 85% while **degrading** alignment and
producing no more well-aligned frames — the same failure shape as `min_inliers=30`. That
85% is mostly confidently-wrong calibration. **Use 0.15 / 0.30.**

Caveats that may understate true accuracy: the pitch model is fixed at 105x68 and a U16
field is likely ~100x64, so part of the misalignment could be model mismatch rather than
camera error; and faint or worn lines may fall outside the white mask.

### End-to-end metric test: PnLCalib pretrained FAILS on this footage

The decisive measurement — metres, not proxy scores. For each of 355 Veo events:
calibrate the frame, keep it only if independently well-aligned, detect the ball, invert
onto the ground plane, compare against Veo's own (x,z).

| stage | count |
| :-- | --: |
| event frames tried | 355 |
| calibrated | 253 |
| **independently well-aligned (>=0.5)** | **16 (4.5%)** |
| scored | 10 |

**Median error 88 m (restarts) / 110 m (open play)** on a 105 m pitch. Essentially
random. Note the well-aligned rate collapsed from 26% on wide frames to 4.5% on *event*
frames, which are action close-ups showing little pitch structure.

**Conclusion: PnLCalib's pretrained weights do not transfer here.** Fair test, fair
failure. The Roboflow `football-field-detection` model shares the problem — it was
trained on 317 frames from TV matches.

### Why, and what it implies

Every available pretrained pitch-calibration model is trained on **broadcast TV**
footage. Ours is amateur, low, extremely oblique, set in a multi-pitch complex, and is
itself a *virtual pan-and-zoom crop* with heavy zoom variation.

And the framing of the whole problem was wrong. **Veo is not solving our problem.** Veo
calibrates its own camera rig against the *full panorama* — known intrinsics, known
mounting, whole pitch in view. We are trying to calibrate from a ball-following crop of
that panorama, which discards exactly the context that makes calibration tractable. "Veo
can do it from an upload" is true, but Veo holds the raw camera feed and we hold a
derived crop.

### Next: rebuild the panorama by stitching, then calibrate THAT

The individual frames fail because each shows too little pitch. But registration between
frames is already proven (0.31-3.93 px above 100 inliers). So:

1. **Stitch frames into a pitch mosaic** — recovering, approximately, the panorama Veo
   will not export.
2. **Calibrate the mosaic once.** It shows the whole pitch, which is far closer to the
   broadcast-style input the pretrained models expect.
3. **Propagate**: every frame inherits metric coordinates through
   `frame → mosaic (registration) → pitch (one homography)`.

This attacks the root cause rather than the symptom, and both ingredients are measured
rather than assumed.

### The reframe — still useful as a fallback



**Most Tier A detection does not need metres — it needs pitch-relative regions.**

- Shot: ball speed and direction toward the goal mouth. Definable in **anchor pixel
  space** if the goal mouth is marked there. No metric needed.
- Corner / throw-in / goal kick: ball crossing a boundary. Boundaries can be drawn as
  polygons in anchor pixel space.
- Goal: the restart signature (ball near the centre spot, players split by half). Needs
  only coarse position.

Precise metric coordinates are genuinely required for only two things: the radar
display and speed in m/s. So a sensible next step is **annotate the pitch polygon and
key zones directly in each anchor's pixel space**, ship Tier A detection on that, and
treat accurate metric calibration as a separate, later problem for the radar. That
inverts the current dependency, where everything waits on a homography that has now
failed twice.

---

## Incident log (read before touching worktrees)

**2026-09-20 — step 8's published figures did not reproduce, and the evidence was
overwritten before anyone checked.** `detect_out_of_play.py` was committed in `3a8d4a1`
with its result recorded in this file and in the mosaic README. Re-running the committed
script the next day against the same stored `ball_track.json` gave **187 predictions and
both-periods F1 0.319**, not the recorded **90 and 0.338**; period-1 F1 topped out at
0.265 where the record claimed 0.296. Three sweeps failed to find any setting that
reproduces it — `min_sep` over 8 values, `fps` over 5, and a 48-cell sweep over
NaN-rank handling x candidate cap x `min_sep`. The *signature* table did not reproduce
either (267/0.13/42 where the record said 196/0.20/35), though every contrast holds in
the same direction and size.

**What made it unrecoverable.** `backend/.local/artifacts/` is gitignored, so
`pred_oop.json` and `score_oop.json` were the only copies of the original output — and
re-running the detector overwrote them before the discrepancy was noticed. The exact
invocation was never written down anywhere.

The likely cause is a script edited after the run that produced the artifacts, then
committed once; but it cannot be established now, which is precisely the problem.

Three things changed as a result:

- **Every detector writes the exact command that produced it** into its own output
  (`command` field in the score doc). Do not report a figure whose `command` does not
  match how you ran it.
- **Step 8 has been restated** to what reproduces, with `min_sep` selected under its own
  stated protocol (period-1 F1) rather than left at an undocumented value.
- The README's reproduce block covers **steps 8-11**, not just the new work, so the whole
  chain can be re-run in one go from the stored artifacts.

The lesson generalises past this repo: a result that lives only in a gitignored artifact
plus a prose summary is a result you do not have. **Re-run before you extend** — this was
caught only because the next step happened to re-run the previous one.


**2026-09-19 — the worktree symlink that ate the venv.** I created `.venv`/`.local`
symlinks inside each UI worktree so agents could run acceptance commands. `.gitignore`
had `backend/.venv/` and `backend/.local/` **with a trailing slash**, which matches a
*directory* but **not a symlink**, so `git add -A` in a worktree tracked them and merging
replaced the real directories with self-referential links.

Lost and rebuilt: the venv (now **Python 3.14.7**, not the previous 3.12.14 — all pinned
deps install and import fine), the seeded DB, the demo fixtures, and the 916 MB 720p
proxy. Nothing was unrecoverable: everything in `.local` was either seed data or derived
from the source mp4, which is intact in `~/Downloads` and on gpu-box.

Two things worth keeping:
- The ignore patterns are now **slash-free**, so a symlink is caught. Verified with
  `git check-ignore`.
- After the rebuild the CV determinism signature was **identical** (`61075316940f2cb1`)
  across a Python 3.12 → 3.14 change, and the regenerated demo clips were byte-identical
  in size. That is real evidence the pipeline is deterministic, obtained by accident.

---

## Done already (do not redo)

- 10 defects closed and verified — `verify.sh all` → `pass=10 fail=0 skip=0`, 36 tests.
  Full record in `OPUS2.md`.
- gpu-box provisioned: torch 2.11.0+cu128, CUDA 12.8, 4× H100, uv-managed CPython 3.12.
  `scripts/remote/provision.sh` is idempotent (re-run → `cached`, exit 10).
- Match video uploaded to `/workspace/aifp/media/video.mp4`, **sha256 verified**
  (`ef7552326b0ab24e...`), 185,003 frames, decodes on the box.
- `scripts/` built: doctor, provision, push-video (resumable), push-code, job-status,
  pull-artifacts, restore, verify, plus the agent dispatch wrapper.
- Veo ground truth captured (above).
- `scripts/local/score-benchmark.py` (G5) — validated on four cases including a random
  detector scoring BELOW its own chance baseline.
- **Track 2 complete**: U1 (hash routing), U2 (jersey-only identity), U3 (now a **16**-type
  status surface -- "Out of play" was missing) all merged and independently verified.
  Baseline **`pass=10 fail=0 skip=0`, 36 pytest tests**, and the frontend builds clean.
- 720p proxy rebuilt and verified (1280x720, duration 6172.933433 exact).

---

## Decisions already made (don't relitigate)

- **Both tracks in parallel**; UI is file-disjoint from GPU work.
- **Done bar:** everything honestly reachable; explicitly excluding what we cannot do.
- **Jersey recognition: yes**, but sequenced last.
- `/workspace` is a 64 GB tmpfs — ephemeral by design; `restore.sh` rebuilds it.
- `cv_engine.py` is **frozen** as the `demo` fallback. Do not extend it.

---

## Answered by the user (2026-09-19) — both close off an easier path

- **No panorama export.** Veo does not allow exporting or downloading the full panoramic
  / interactive view. So the ball-following crop is all we get and **per-frame homography
  (G2) is mandatory** — the mosaic-registration design is now the plan, not one option of
  two. Budget accordingly; this is the most expensive layer.
- **No roster / team sheet available from Veo.** So jersey recognition cannot be framed
  as a closed-set classification over a declared squad. That leaves two honest options,
  and the choice must be stated in the output either way:
  1. **Open-set**: read digits with abstention, cluster per track, never assert a number
     below the confidence margin. Lower coverage, no leakage.
  2. **Derive the number set from Veo's 334 attributed events** — which is *leakage
     dressed as a prior* and must be labelled as such wherever the result is reported.
  Default to (1). Do not quietly do (2).
