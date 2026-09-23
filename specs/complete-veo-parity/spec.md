# Complete the Veo replica — the remaining honestly-reachable work

**Written 2026-09-23, before any of the measurements below exist.** The gates in
§3 are pre-registered: they are committed now so that a later failure cannot be
re-described as a success.

## 0. Where this starts

Verified by me on 2026-09-23 before writing a line:

- `bash scripts/local/verify.sh all` → `pass=10 fail=0 skip=0`
- `backend/.venv/bin/python -m pytest backend/tests -q` → `36 passed`
- `cd frontend && npm run build` → clean, 1891 modules

`STATE.md` closes the measurement track. Its closing summary is accurate about what
it covers. This spec exists because three things it does **not** cover are still
honestly reachable:

1. **`FootballShot` (25 events) was never attempted.** `PLAN.md` classes it Tier A
   alongside the six types that *were* built. It is not in `STATE.md`'s "cannot do"
   table — it is simply missing. That is a gap in the record, not a closed question.
2. **`FootballFoul` + `FootballFreeKick` (30 events) were closed on the wrong cue.**
   `B9` rejected FreeKick because *its position cloud sits inside ThrowIn's*.
   `PLAN.md`'s Tier C design never proposed position — it proposed *a stoppage with
   the ball still inside the pitch*, which is the exact complement of the
   already-working `OutOfPlay` detector. That design has not been tested.
3. **Parity axes A and C were never finished.** `PLAN.md` says the stats table
   computes 3 of 13 rows and the UI misses several real-Veo behaviours. Six event
   types are now detected; the rows they imply are still dark.

## 1. What "complete" means here

Three axes, from `PLAN.md`:

| axis | done bar |
| :-- | :-- |
| **A. UI / routes** | Every real-Veo behaviour listed in `PLAN.md:125-153` is either implemented or has a named, visible reason it is not |
| **B. Detection** | Every one of Veo's 14 event types is either **detected and scored** against `benchmarks/raw/veo_events_447.csv`, or **closed by a measurement** with a recorded command |
| **C. Stats** | Every one of the 13 stat rows is either a **real count derived from detected events** or a visible `—` with a reason |

The done bar is *not* a target F1. It is that **no type is left in the "never
looked" state**. A pre-registered failure is a completed item.

## 2. Scope

### In

- **P1 — `FootballShot` detector** (25 events, 5.6 % of mass), scored, with saves
  promoted as an outcome on detected shots only if P1 passes.
- **P2 — `FootballFreeKick` / `FootballFoul` detector** (30 events, 6.7 %) on the
  ball-stays-inside-the-pitch cue, scored.
- **P3 — Stats table**: every row that a detected type implies becomes a real count;
  every other row stays `—` with a reason.
- **P4 — UI parity gaps** against `PLAN.md:125-153`.
- **P5 — Close the record**: fold every result, pass or fail, into `STATE.md` and
  the mosaic `README.md`, and update the 16-label capability surface.

### Out — and why

- **Tier B** (interception / tackle / dribble / loose, 241 events). Closed by the
  pre-registered 15 fps gate at `486e082`. Not reopened.
- **Metric calibration / radar in metres / speeds in m/s.** Five measured failures;
  the ground plane inverts to a square.
- **`save` as a standalone detector.** `PLAN.md` states it is not achievable
  independently. It is allowed **only** as an outcome on a shot P1 already found.
- **`Penalty`.** 0 in the reference. "0/0 matching" is not a result.
- **Per-event `Pass` scoring.** No reference timestamps exist.
- **G7 jersey recognition.** No roster, so open-set with a ~25-40 % ceiling, and it
  unlocks zero event types. It stays deferred; `specs/deferred.md` already records
  the reasoning. **If it is not built, the capability surface must say so.**
- **Raising ball-track coverage.** Falsified at `84e6275`.

## 3. Pre-registered gates — committed before the data exists

### 3.1 Rules that bind every detector in this spec

1. **Fit on period 1 only. Period 2 is held out** and is looked at once, after the
   period-1 configuration is frozen. This is how the six existing detectors were
   scored; changing it now would make the numbers incomparable.
2. **Matched-K chance control.** Every claim is reported against a random detector
   emitting the same number of predictions K over the same in-play span.
3. **The OutOfPlay-proxy control (new, and the one that matters).** The existing
   `OutOfPlay` detector fires on the ball track's *coverage collapse*. A shot and a
   free kick both also occur near a stoppage. So a new detector must be scored
   against a control that simply **re-labels the existing OutOfPlay predictions** as
   the new type. **Beating chance is not enough — it must beat this control**, or it
   has found stoppages, not shots.
4. **Every detector writes the exact command that produced it** (B12), or its
   figures are not quotable.
5. Tolerance window and the scoring harness are **unchanged** from the six existing
   types. No new tolerance may be introduced for a new type.

### 3.2 P1 — `FootballShot`

**Premise, measured from period 1 only:** the 14 period-1 shots are bimodal along
the pitch length — x in 0.05–0.25 (n=8) and 0.77–0.93 (n=6), never the middle third.
The goal-end geometry needed to express that in pixel space **already exists and is
already validated**: B10's defend-end map scored 24/24 on true times and 8/8 held
out. So the detector may use it without re-fitting it.

**PASS iff all three hold on period 2, held out:**

- **S1** F1 ≥ 0.25
- **S2** F1 ≥ 2.0 × the matched-K chance baseline
- **S3** F1 strictly greater than the OutOfPlay-proxy control of §3.1.3

**FAIL** → `FootballShot` is recorded in `STATE.md`'s "cannot do" table with the
measured numbers and the reason, and the capability surface names it. A failed P1
also **cancels the save-as-outcome item**; saves then render "not detected".

### 3.3 P2 — `FootballFreeKick` / `FootballFoul`

**Cue (from `PLAN.md`'s Tier C, not from position):** a stoppage — the same
signature `OutOfPlay` uses — where the ball is **inside** the pitch region rather
than crossing its boundary, followed by a stationary restart.

Scored separately for the two types, because Veo timestamps them differently: the
foul is the offence, the free kick is the restart.

**PASS iff, on period 2, held out, for `FootballFreeKick`:**

- **F1a** F1 ≥ 0.20
- **F1b** F1 ≥ 2.0 × matched-K chance
- **F1c** F1 strictly greater than the OutOfPlay-proxy control

`FootballFoul` is reported alongside but is **not** gated: `PLAN.md` states its onset
timing is unrecoverable (we lost the whistle). Its number is published for the record
whatever it is.

**FAIL** → both types recorded as closed with numbers, exactly as P1.

### 3.4 What a pass changes

A passing detector is merged into `merge_predictions.py`, re-scored as part of the
macro, cleared by `control_team_shuffle.py` if it carries a team, and ingested by
`ml_ingest.py` so it reaches the app. **The headline macro-F1 must be restated
whether it goes up or down.** A new type that lowers the macro is still reported.

## 4. Acceptance for the whole spec

Executable, run by me and not by any package author:

| # | command | expected |
| :-- | :-- | :-- |
| A1 | `bash scripts/local/verify.sh all` | `pass=N fail=0 skip=0`, N ≥ 10 |
| A2 | `backend/.venv/bin/python -m pytest backend/tests -q` | ≥ 36 passed, 0 failed |
| A3 | `cd frontend && npm run build` | exit 0 |
| A4 | the scoring harness re-run from its own recorded `command` | reproduces the published macro to the digit |
| A5 | every one of Veo's 14 types | appears in the capability surface as detected-with-a-count or unavailable-with-a-reason |
| A6 | every one of the 13 stat rows | a real count or `—`; no literal invented anywhere (probe `d10`) |

## 5. The rule that outranks every gate

When a capability is not implemented, **show that it is not implemented**. An empty
state, a dimmed `—` or a "not detected" badge is a correct and useful answer. A
plausible fabricated number is not. This binds agent reports as hard as it binds
product output: `partial` reported accurately beats `complete` reported fast.
