# Veo feature parity on gpu-box

## Context

The previous plan (move to gpu-box, build an ML pipeline, close six defects) is **half
done**: nine defects are closed and verified (`pass=8 fail=0 skip=0`, 35 tests, all
recorded in `OPUS2.md`), and gpu-box is provisioned — torch 2.11.0+cu128 on 4× H100, the
3.5 GB match video uploaded and sha-verified. What was never built is the pipeline code
itself. That is what this plan covers, reframed around the question actually being
asked: **how do we reach feature parity with the Veo match page?**

Two things discovered since the last plan change the work materially:

1. **We now have Veo's own ground truth — 447 events with exact video timestamps.**
   Pulled today from Veo's private API in the browser. This replaces a 13-event
   benchmark that was *partly wrong*.
2. **The camera pans.** The export is Veo's ball-following virtual crop, not the static
   panorama, so per-frame homography is mandatory.

The governing rule is unchanged:

> When a capability is not implemented, **show that it is not implemented.** An empty
> state, a dimmed `—`, or a "not detected" badge is a correct and useful answer. A
> plausible fabricated number is not.

---

## The most important finding: our benchmark's time base was wrong

`benchmarks/veo_reference.json` derived video timestamps from Veo's displayed **match
clock** using inferred offsets (`+561` for H1, `+1080` for H2, ±40 s uncertainty).
Veo's API gives `video_time_ms` directly, and the true mapping is exactly linear:

| Period | Offset | Video range |
| :-- | :-- | :-- |
| 1 | **+562 s** | 562.3 → 2879.3 |
| 2 | **+3674 s** | 3674.4 → 6132.1 |

Kickoff at video **562.3**; H1 ends **2879.3**; halftime **795 s**; H2 kicks off
**3674.4**. (Halves are ~2317 s ≈ 38:37, not the assumed 2400 s.)

Our three home-goal predictions against reality:

| Predicted | Actual | Error |
| --: | --: | --: |
| 772 | 775.3 | 3 s ✓ |
| 2957 | **3709.3** | **752 s** ✗ |
| 5516 | **5749.6** | **234 s** ✗ |

**Two of three were wrong by far more than the ±30 s tolerance.** A correct pipeline
scored against that file would have been told it missed goals it actually found. Every
second-half entry was similarly wrong. This invalidates the old scoreboard, and it is
the single highest-value correction available to the project.

---

## The new ground truth

From `GET /api/app/matches/{uuid}/events/` (447 records). Each carries `event_type`,
`video_time_ms`, `period_id`, `period_time_ms`, `team` (`Own`/`Opponent`),
`player_jersey`, `outcome`, and `x`/`z` normalized pitch coordinates.

- **334/447 carry a jersey number**, **355/447 carry pitch coordinates**
- 14 event types; per-type counts reconcile *exactly* with Veo's published stats table
  (`FootballShot` Own=13/Opp=12 = "Total attempts 13/12"; tackle 41/43; throw-in 24/14;
  foul 8/7; corner 6/3; goal 3/3)
- Goals (video s): Opp 725.4 #35, **Own 775.3 #24**, Opp 1261.3 #49, Opp 2527.2 #19,
  **Own 3709.3 #44**, **Own 5749.6 #14** → 3-3

| Type | Own | Opp | | Type | Own | Opp |
| :-- | --: | --: | :-- | :-- | --: | --: |
| interception | 44 | 45 | | FootballGoalKick | 9 | 7 |
| tackle | 41 | 43 | | FootballFoul | 8 | 7 |
| FootballOutOfPlay | 24 | 40 | | FootballFreeKick | 7 | 8 |
| dribble | 12 | 29 | | save | 3 | 7 |
| FootballThrowIn | 24 | 14 | | FootballCornerKick | 6 | 3 |
| loose (ball recovery) | 14 | 13 | | FootballKickOff | 4 | 4 |
| FootballShot | 13 | 12 | | FootballGoal | 3 | 3 |

A 15th type, **Pass**, appears in Veo's Events drawer and stats (203 own / 283 opp) but
is absent from this endpoint.

**This resolves three documented `UNRESOLVED` items at once:** away-side events are now
scorable, every event has a timestamp, and the second-half offset is exact.

### How to re-capture it

The Bearer token is ephemeral and **must never be committed**. Procedure: open the match
in Chrome (logged in), patch `window.fetch` to capture the outgoing headers of any
`/api/app/matches/` call, switch to `#/lineup/` to trigger one, then re-issue
`GET /api/app/matches/{uuid}/events/` with those headers:
`Authorization: Bearer …`, `veo-agent: veo:svc:web-app`, `Veo-App-Id: hazard`,
`credentials: include`. The slug 403s; **the match UUID is required**.
Match UUID: `3ddc7b34-d737-4cd4-83ce-7490d9e07efa`.

Each page load POSTs to `/views/` and increments the match view counter — a real if
trivial write to the user's account, so minimise reloads.

---

## What parity actually means

Three separable axes. Only the second needs the GPUs.

### A. UI / routes — we have 1 of 7

Veo is a hash-routed match page: base (video), `#/analysis/`, `#/player-moments/`,
`#/highlights/`, `#/events/`, `#/lineup/`, `#/summary/`. Our clone has **no router at
all** — a single page with `useState` drawers (3,599 lines of frontend across 16 files,
not the 1,256 previously assumed).

**But this is cheaper than it looks.** `SidebarTabs.tsx` already implements six
mutually-exclusive drawer bodies — highlights, events, players, analytics, lineup,
summary — which map **1:1 onto Veo's six non-base routes**. Route parity is mostly
wiring existing panels to hash URLs plus deep-link/restore behaviour; no router is
installed (deps are just React 19, Tailwind 4, lucide-react, canvas-confetti), and
Veo's scheme is hash-based, so ~30 lines of `hashchange` handling avoids a dependency
entirely. Sharing becomes real at the same time: `Header.tsx:22-26` currently copies
`window.location.href`, which is identical for every match and every panel.

Notable real-Veo details our clone gets wrong or misses:
- **Veo never displays a player name anywhere** — jersey numbers only. Our clone
  fabricates "Eric Jordi", "Diego Morales", "Julian Vance". Veo renders `Player ` with a
  *blank* number for unresolved players, which is the honesty rule applied upstream.
- Stat labels are **singular** (`Goal`, `Shot`, `Corner`, `Tackle`, `Foul`), and derived
  metrics (`Passes completed`, `Possession %`, `Possession won`) render as **disabled**
  buttons because they have no discrete events to seek to.
- Each clip has its own comment thread at `#/highlights/<uuid>/comments/`.
- Events rows carry per-event actions: `video add` (promote to clip) and `arrow up right`
  (seek).
- Analytics has 6 accordions: `Stats`, `Shot map`, `Pass location`, `Possession
  location`, `Pass strings`, `Heat map` — the last with a dual-thumb second-range slider.

### B. Analysis / event detection — we have 3 of 15, and they barely work

Our CV pipeline emits only `Kickoff`, `Shot`, `Goal`. The 7 types people point at are
**demo-seed literals, not detections**. Reaching parity here is the GPU work.

### C. Stats table — we have 3 of 13 computed

Veo shows 13 rows. We genuinely compute goals, shots and possession%; `corners`,
`free_kicks`, `throw_ins`, `fouls`, `penalties`, `tackles`, `passes_completed`,
`possession_won` are all `None` → `—`. That is honest today, and each becomes real only
when its event type is detected.

---

## Still-open defect

One fabrication survived the last pass: **`cv_engine.py:551-554` hardcodes
`pass_strings`** to an invented decay curve (`[10,6,4,2,1,0,0,0]` / `[12,7,3,1,0,0,0,0]`)
which `SidebarTabs.tsx:341` renders as a real bar chart. The *seed* was fixed to `[]`;
the *pipeline* was not, so the two producers disagree. Must be `None`/empty.

**No probe covers `pass_strings`** — `scripts/local/verify.py` has nothing for it. It
needs a `d10` probe asserting no invented analytics literal survives anywhere.

Same class, same file: `cv_engine.py:544-549` substitutes a made-up 20/60/20 thirds
split (`h_def or 20.0`) whenever a genuinely computed third is `0.0` — a real zero
becomes a plausible fiction. And `cv_engine.py:485` emits `outcome="unknown"`, which is
not a member of `ShotRecord`'s documented `goal|saved|missed|blocked` set.

**A softer one in the UI:** `PitchRadar.tsx:290` does honour `ball.detected`, but only
by dimming to 30% opacity — it still draws the ball at the Kalman-coasted position. A
faded ball at an invented coordinate still asserts a coordinate. Compare Veo, which
renders `Player ` with a *blank* number rather than inventing one. Undetected should
draw nothing.

---

## Environment (unchanged, verified)

**gpu-box** — privileged Docker container, `--network host`, 4× H100 NVL (~65 GB free
each; Ollama holds `qwen3.8` + `mistral` resident, so budget ≤40 GB/GPU and never OOM
it), 128 cores, 251 GB RAM, `/workspace` = 64 GB tmpfs (nothing survives a restart;
`scripts/remote/restore.sh` rebuilds it), caches on `/opt`. Link is DERP-relayed at
**2.8 MB/s**. Python trap: never call bare `pip`; use the uv-managed 3.12 venv. torch
must be a **cu12x** wheel.

**Blocked right now:** Tailscale SSH auth expired mid-session and needs an interactive
re-auth (`https://login.tailscale.com/a/lfeaf6203a1626`) before any GPU work resumes.

**Video:** 1920x1080, 29.97 fps, 185,003 frames, GOP exactly 2.5025 s, **no audio stream
at all** — so whistle-based foul detection is structurally impossible for us.

**Camera pans**, the pitch carries **two overlapping line systems** (white + blue), and
**goals from adjacent pitches appear in frame**.

---

---

## Decisions taken (user-confirmed this session)

| Decision | Choice |
| :-- | :-- |
| Priority | **Both axes in parallel** — UI/routes is frontend-only and file-disjoint from the GPU pipeline |
| Done bar | **Everything honestly reachable**, including possession-derived types; explicitly excluding what we cannot do |
| Jersey recognition | **Yes, attempt it** — but see the honest ceiling below, and it is sequenced last because it unlocks zero event types |

---

## Three free structural identities in Veo's data

These need no detector to check and catch internal incoherence in *our* output faster
and cheaper than any scored comparison:

1. **KickOff 8 = 2 period starts + 6 goals.** Exact. Our kickoff and goal detectors must
   satisfy this identity or they contradict each other.
2. **Foul 8/7 mirrors FreeKick 7/8.** Veo emits a paired Foul(offender) +
   FreeKick(beneficiary). That is **one detector, not two** — free kick carries no
   independent information.
3. **Possession minutes 14/22 = 36 min of control out of ~79 min of play**, and
   14/36 = 38.9% ≈ the published 38%. So Veo's possession% is a **control-time ratio,
   and control is only 46% of playing time.** Any possession model attributing 70
   minutes of control is wrong by construction, before percentages are compared.

---

## Detectability: what we can honestly reach

### Tier A — geometry-driven, build first (196 events, 44% of mass)

`Goal`, `KickOff`, `Corner`, `GoalKick`, `ThrowIn`, `OutOfPlay`, `Shot`.

Needs only ball track + homography. `KickOff` is near-deterministic (ball on the centre
spot **and all players in their own half**). `Goal` is confirmed by the **restart
signature** — a centre-spot kickoff 20–60 s later — not by goal-mouth appearance, which
is useless here because adjacent pitches' goals are in frame. Expect Goal 5–6 of 6.

Build Tier A before Tier B **even though Tier B is 54% of the event mass**: it needs no
possession model, it contains every event a user actually cares about, its dead-ball
segmentation is a *prerequisite* for the possession denominator, and it is where
precision is achievable.

### Tier B — one detector, four types (241 events, 54%)

`interception`, `tackle`, `dribble`, `loose` are all boundary classifications of the
same possession-run segmentation. They stand or fall together. Expect per-event F1
0.25–0.45. `Pass` is **count-only** — Veo exposes no per-pass timestamps, so no
per-event score is possible.

### Tier C — marginal

`Foul`+`FreeKick` as one detector (stoppage with the ball inside the pitch, then a
stationary restart). **`save` renders "not detected"** — it needs GK-contact detection
at exactly the moment ball tracking is least reliable; promote it later as an *outcome*
on a detected Shot, never a standalone detector. **`Penalty` 0/0 "matching" proves
nothing** and must be reported as "no penalty-spot restart found", not as a hit.

### Not achievable, stated plainly

Save as an independent type; foul *onset timing* to Veo's precision (we lost the
whistle — no design recovers it); per-event Pass scoring (no reference data); shot
outcome saved/blocked/off-target.

---

## Homography: register to a mosaic, don't calibrate per frame

The key realisation: **the physical camera is fixed** — the export is a pan-and-zoom
crop of a static panorama. So:

```
frame pixel --(per-frame warp, easy)--> panorama pixel --(ONE fixed homography)--> pitch metres
```

Build a mosaic from the video's own keyframes, calibrate the mosaic **once** against the
pitch with 8+ points, then register each frame to a set of reference keyframes with
feature matching (SuperPoint + LightGlue on the H100s) — **never chained frame-to-frame**
across 185k frames. This sidesteps the two-overlapping-line-systems problem entirely
(features, not lines) and the adjacent-goals problem (calibrated geometry, not
appearance). Confidence = inlier count + reprojection RMS, and that is what the gate
thresholds on. Register at 10 Hz, interpolate, full rate only within ±2 s of candidates.

**Still worth minutes of checking first:** ask whether Veo will export the **panorama**
of this match. If yes, this whole layer collapses into a one-time 8-point calibration.

---

## Possession: an HMM, not per-frame nearest-neighbour

`cv_engine.py:501-513` currently takes `min(players, key=distance) < 3.0 m` per frame.
That flickers and 3 m is not control. Replace with a Viterbi decode per in-play segment:
states = one per visible track, plus `TRANSIT`, plus `NONE`; emission cost combines
metric distance, ball-vs-player velocity agreement, a penalty when the ball is fast, and
homography confidence. Transition switch-penalties give temporal smoothness so the
enter/exit hysteresis emerges rather than being hand-coded.

Runs = maximal intervals of constant owner, and Tier B falls out of one table:

| Before → after | Transit | Contact | Event |
| :-- | :-- | :-- | :-- |
| A:p1 → A:p2 | ≥5 m | — | Pass |
| A:p1 → B:q | ≥5 m | no | Interception |
| A:p1 → B:q | none | ≤2 m converging | Tackle |
| any → any | owner `NONE` ≥1.5 s | — | Loose ball recovery |
| within a run | — | opponent passed | Dribble |

**The honesty mechanics, non-negotiable:** never bridge a ball gap >1.0–1.5 s — truncate
the run and mark `UNKNOWN`; exclude `UNKNOWN` and dead time from **every denominator**
and publish coverage beside every percentage (*"38% / 62% — computed over 61% of play
time"*); and **emit no event at a boundary whose evidence lies inside a gap** (require
≥N attributed samples on both sides). That last rule kills the most seductive failure
mode — inventing an interception every time the ball track drops out.

### Pre-declared go/no-go gate (write it down before measuring)

> Tier B ships only if, on a held-out 10-minute slice: ball detected in **≥70%** of
> in-play sampled frames, median gap **≤0.4 s**, and **≥85%** of possession transitions
> have ≥3 attributed samples on both sides.

If the gate fails, those 5 types and 3 stat rows render **"not detected"** and we ship
Tier A alone. **Ball detection recall on this footage is currently unmeasured, and every
Tier B estimate is conditioned on it — measuring it is work package one.**

---

## Using Veo's 355 coordinates and 334 jerseys

**Step 0, free and first: decode the coordinate convention.** We don't know Veo's origin,
axis orientation, or whether coordinates are attack-relative. Recover it by fitting
against events with *known* geometry — KickOff (8) on the centre spot, Corner (9) at four
corners, ThrowIn (38) collapsing onto two lines, GoalKick (16) in two goal areas, Goal (6)
at two mouths. 77 events doing the work of a calibration rig, an afternoon of numpy. If
throw-ins don't collapse under any absolute convention, the coordinates are
attack-direction-relative — test by flipping per team and period.

**Then the best use: an unbiased homography accuracy meter that does not depend on our
detectors at all.** At each of the 71 restart events, project with our homography and
compare against geometric truth — a throw-in *is* on the touchline, so `|our_y − 0 or 68|`
is a direct error measurement. Bucket errors by our own confidence score and pick the gate
threshold empirically.

> **L2 gate: 90th-percentile error < 2 m on gated frames, with gate coverage ≥60% of
> in-play frames.** Both numbers matter — a gate passing 5% of frames at 0.2 m is useless.

Secondary: 355 free ball-position pseudo-labels; and ~6–7k weakly-labelled jersey crops
(nearest track to Veo's (x,z), requiring second-nearest >3 m to bound noise). **Split by
period — train on period 1, test on period 2.**

---

## Jersey recognition — do it, but last, and with an honest ceiling

It unlocks **zero event types and zero stat rows**; it is an attribute on events that must
exist first. Sequence after Tier B.

Design: crop from **native 1920×1080** (not the 0.5-scale frame the engine uses now);
filter hard (≥45 px tall, unoccluded, back-facing); super-resolve 4–8×; then a
**closed-set classifier over the squad's numbers plus a `none` class**, not open OCR —
at 12–20 px digit height that wins by a wide margin. Fuse per track with
quality-weighted voting, **abstain below a margin threshold**, and add Hungarian
track→squad assignment enforcing uniqueness per team. Stitch tracks with ReID first or
you vote over 20 fragments of one player.

**Honest ceiling: ~25–40% of events carrying a jersey, against Veo's 75%** (single-frame
read rate under 20%; after fusion, 30–50% of tracks at 80–90% per-decision accuracy). We
do not fill in a number to raise coverage. **If the roster is derived from Veo's 334
attributed events, that is leakage dressed as a prior and must be said out loud** —
prefer declaring the team sheet as a product input.

Worth building first as a cheaper alternative: **semi-automatic** — the user clicks each
track cluster once, ReID propagates it. Most of the product value, a fraction of the cost,
and it degrades honestly.

---

## Scoring the 447-event benchmark

Per type, Hungarian one-to-one matching within a **per-type** tolerance requiring team
match: ±3 s for crisp restarts (Goal, KickOff, Corner, GoalKick, ThrowIn) and for the
genuinely fuzzy ones (OutOfPlay, Foul, FreeKick); ±5 s for Shot; **±2 s for the dense
types** (interception, tackle, loose, dribble) — a loose tolerance lets a random detector
score.

**Print the chance baseline beside every recall.** For interception: 89 events × 4 s over
~4775 s of play ≈ **7.5% recall from a random detector emitting the same count**. This is
the same lesson the Colab notebook already taught us.

Three numbers, never one:
1. **Macro-F1 over *attempted* types** — the headline. This is the answer to "interception
   n=89 dominates": under macro weighting Goal (n=6) counts the same.
2. **Micro-F1**, reported separately and labelled.
3. **Parity count — the integer number of types at F1 ≥ 0.5** (0–14). Hard to game.

Types we don't attempt are `not_attempted`, excluded from the macro average but counted in
**two separate coverage figures** (type coverage and event-mass coverage are different
claims): *"We attempt 7 of 14 types, covering 196 of 447 events (44% of mass)."* A type we
**do** attempt and score 0 on **stays in the average** — the attempted-set is declared in a
manifest committed *before* the run, enforced by the harness, not by discipline.

Also required: `n` on every row with n<10 flagged low-n and reported in counts;
team-agnostic score alongside team-conditioned (separates detection from attribution
error); jersey accuracy on true positives only; the 13 stat rows as signed relative error
with `—` meaning **not produced**, explicitly not error 0. Period 1 is dev, **period 2 is
held out**, both reported side by side so leakage shows as a gap.

---

## Realistic parity estimate

**The number to defend: 7 of 14 types at usable quality (37–44% of event mass) plus 7 of
13 stat rows.** Best realistic case 11 of 14 types and 91% of mass at mixed quality; the
bet is **7 solid + 4 marked-uncertain**.

| | Types | Quality |
| :-- | :-- | :-- |
| Ship confidently (Tier A) | 7 | F1 0.5–0.9; Goal 5–6 of 6 |
| Ship low-confidence *if the ball gate passes* (Tier B) | +4 | F1 0.25–0.45 |
| Stretch | +2 (Foul, FreeKick) | F1 0.3–0.5 |
| Not attempted | save, per-event Pass, Penalty | renders "not detected" |

Stat rows: solid — Goal, Shot, Total attempts, Corner, Throw-in, Possession%, Possession
minutes (7). Marginal — Tackle, Possession won, Passes completed (3). Stretch — Foul, Free
kick (2). Meaningless — Penalty.

---

## Work packages (two parallel tracks, file-disjoint)

**Track 1 — GPU pipeline** (gpu-box; needs Tailscale re-auth first)

| WP | Work | Owns |
| :-- | :-- | :-- |
| G0 | Rebuild `benchmarks/veo_reference.json` from the 447-event API dump; fix `scripts/config.env` time base; decode Veo's x/z convention | `benchmarks/`, `scripts/config.env` |
| G1 | **Measure ball detection recall** on a 10-min slice — tiled inference + trajectory Viterbi. The go/no-go gate | `backend/src/services/pipeline/gpu_job/` |
| G2 | Mosaic homography + confidence gate, validated against the 71 restart coordinates | same |
| G3 | Tier A detectors (7 types) | same |
| G4 | Possession HMM → Tier B (4 types + Pass count) | same |
| G5 | Scoring harness: macro-F1, chance baseline, parity count, period split | `scripts/local/score-benchmark.py` |
| G6 | Ingest artifacts → `analysis_mode="ml"` | `backend/src/services/pipeline/ml_ingest.py` |
| G7 | Jersey recognition (last) | same |

**Track 2 — UI/route parity** (frontend only, no GPU, no overlap with Track 1)

| WP | Work | Owns |
| :-- | :-- | :-- |
| U1 | Hash router; wire the 6 existing drawers to Veo's routes; real deep-link Share | `frontend/src/App.tsx`, `Header.tsx` |
| U2 | Remove fabricated player names → jersey numbers only, blank when unresolved (Veo's own convention); derive the jersey bar from `lineup`, not the 17 hardcoded literals | `PlayerMomentsBar.tsx`, `SidebarTabs.tsx` |
| U3 | Events drawer renders **all 15 types with explicit per-type status** — `detected (n)` / `not attempted` / `disabled: quality gate not met`. Needs a per-match capability manifest in the data model | `SidebarTabs.tsx`, `match.py` |
| U4 | Stat labels singular; derived rows as disabled buttons; per-event `video add` + seek actions; comment-thread route | `SidebarTabs.tsx` |

**Cross-cutting, do immediately:** delete the surviving `pass_strings` fabrication and the
`or 20.0` thirds fallbacks in `cv_engine.py`; add probe `d10` so no invented literal can
return; make `PitchRadar` draw nothing for an undetected ball. **Freeze `cv_engine.py` as
the `demo` fallback — do not extend it.**

`scripts/README.md` documents `run-job.sh`, `ingest-artifacts.py` and
`score-benchmark.py` **which do not exist yet**. Those three are the first executables to
build.

---

## Verification

- `bash scripts/local/verify.sh all` → `pass=9 fail=0 skip=0` (d10 added)
- `backend/.venv/bin/python -m pytest backend/tests -q` → ≥35 passed, and the live DB /
  media dir unchanged afterwards
- `bash scripts/remote/doctor.sh` → one JSON line confirming 4 GPUs and the video sha
- `python scripts/local/score-benchmark.py --job <id>` → per-type table with `n`, chance
  baseline, macro-F1, micro-F1, parity count, and the period-1/period-2 split; **exits
  non-zero if the attempted-set manifest is missing**
- Structural identities on our own output: kickoffs = periods + goals; fouls mirror free
  kicks; possession% equals the possession-minutes ratio
- `npm run build` clean; `npm run lint` no new warnings

---

## Handoff prompt for Antigravity

Paste this into Antigravity (or run via `agy`, which headless **requires
`--dangerously-skip-permissions`** or it silently auto-denies every tool and returns
nothing):

```
Continue the ai-focus-play Veo-clone project in /home/ai/workspaces/users/jordi/ai-focus-play.

Read these first, in order:
  1. PLAN.md          <- the plan; start here
  2. context.md      - verified environment, gpu-box, traps
  3. OPUS2.md        - what was already fixed and how it was verified
  4. scripts/README.md - the script contract (<=3 lines out, exit codes are the API)

The governing rule, which overrides convenience everywhere:
  When a capability is not implemented, SHOW that it is not implemented. An empty
  state, a dimmed em-dash, or a "not detected" badge is a correct answer. A plausible
  fabricated number is not. This applies to your own progress reports too.

Start with work package G0, because everything downstream is scored against it:
  - benchmarks/veo_reference.json is WRONG. Its second-half timestamps are off by up to
    752 seconds because they were derived from Veo's displayed match clock with guessed
    offsets. Replace it wholesale with Veo's own 447-event API dump, keyed on
    video_time_ms, with (period_id, period_time_ms) as canonical. The plan's
    "How to re-capture it" section has the exact browser procedure and headers.
    Never commit the Bearer token.
  - Fix the time base in scripts/config.env: period 1 offset 562, period 2 offset 3674.
    Halves are 2317.0 s and 2457.7 s, NOT 2400.

Then G1: measure ball-detection recall on a 10-minute slice and publish the number in
coverage.json whatever it says. The pre-declared go/no-go gate in the plan decides
whether Tier B is attempted at all. Do not build event detectors before that number
exists.

Constraints you must respect:
  - gpu-box needs Tailscale re-auth before any remote work; run scripts/remote/doctor.sh
    first and stop if it cannot connect.
  - On gpu-box NEVER call bare `pip` (it is bound to 3.11 while python3 is 3.10). Use the
    uv-managed 3.12 venv at /workspace/aifp/.venv. torch must be a cu12x wheel.
  - /workspace is a 64 GB tmpfs: nothing survives a container restart.
    scripts/remote/restore.sh rebuilds it in one command.
  - Do NOT extend backend/src/services/pipeline/cv_engine.py. It is frozen as the demo
    fallback. The real producer is the gpu-box artifact path plus a local ingest.
  - Frontend work (Track 2 in the plan) is file-disjoint from the GPU work and can
    proceed in parallel.

Report honestly: status complete | partial | blocked, with the real pasted output of any
acceptance command you ran. A false "complete" poisons everything downstream.
```
