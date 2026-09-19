# OPUS2 — verification record

Written 2026-09-19. This is the follow-up `OPUS.md` asked for: a record of what was
actually verified, how, and what remains unverified.

The rule that governs it, unchanged:

> When a capability is not implemented, **show that it is not implemented.** An empty
> state, a dimmed `—`, or a "not detected" badge is a correct and useful answer. A
> plausible fabricated number is not.

That rule applies to this document too. Everything below was executed; the pasted
output is real. Where something was not verified, it says so.

## Headline

| | Before | After |
| :-- | :-- | :-- |
| Adversarial probes | `pass=0 fail=6 skip=2` | **`pass=8 fail=0 skip=0`** |
| Backend tests | 18 passed | **35 passed** |
| Defects closed | 0 | **9** |

```
$ bash scripts/local/verify.sh all
PASS  d1  read-only enforcement   all gated, negative case holds
PASS  d2  CV determinism          repeatable in-process and no cross-match leak (sig=61075316940f2cb1)
PASS  d3  radar index on live db  migration creates index on an existing db
PASS  d4  honest fallback label   no unconditional heuristic label
PASS  d5  seed self-consistency   seed is internally consistent
PASS  d6  streaming zip export    5 clip member(s), all distinct, none a full video
PASS  d7  orphaned-job sweep      stale job reclaimed (status=interrupted)
PASS  d8  invented shot outcome   no invented shot outcome
RESULT: pass=8 fail=0 skip=0
```

`npm run build` clean; `npm run lint` 1 pre-existing warning; `pytest` leaves the live
database and media directory unchanged (13 → 13 files, 1 → 1 match).

## Why the original 18 tests caught none of this

Each defect had a specific reason the suite could not see it. This is the useful part.

| # | Defect | Why 18 green tests missed it |
| :-- | :-- | :-- |
| 1 | `AIFP_READ_ONLY` unenforced | `config.py` reads the env at **import** time, so flipping it inside a running pytest process changes nothing. The only honest probe launches a **separate uvicorn process**. |
| 2 | Non-deterministic team assignment | A per-process test passes every time. The leak only appears when **two videos run in one process** through the module singleton. |
| 3 | Missing radar index | `create_all` really does create it — **on a fresh database**. Every test used a fresh database. The bug only exists on a DB that predates the index. |
| 4 | Fallback mislabelled | No test asserted on the *fallback* branch, only the happy path. |
| 5 | Seed contradicts its own events | The suite tested the seed's *presence*, never its internal *consistency*. |
| 6 | Zip substitutes the full video | Nothing compared zip member bytes against the source video. |
| 7 | No crash-recovery sweep | `'interrupted'` appears in the source, so a grep "passes". Only a **behavioural** probe that plants a stale job catches it. |
| 8 | `outcome="saved"` invented | It is a plausible string in a valid enum. Nothing was wrong *structurally*. |
| 9 | Tests polluted live data | The pollution *was* the shared state the tests depended on. |

## The defects

Each entry: reproduction, root cause, fix, verification.

### D1 — `AIFP_READ_ONLY=1` was unenforced
**Root cause.** `main.py:70` hardcoded `"allow_uploads": True` so it could never track
the flag; enforcement existed in only four places (`repository.py:153,179`,
`matches.py:275,294`), all highlights routes. Upload, delete-match, drawings,
teams/swap and journal were ungated.

**This was not theoretical.** An early probe of mine ran `DELETE /api/matches/
demo-arlington-skyline` against the live database expecting a 403. It got a 200 and
**deleted the demo match.** I restored it by reseeding, and made the harness copy the
DB rather than use it.

**Fix.** `ReadOnlyAPIMiddleware` (new `backend/src/api/guards.py`) rejects every
mutating method under `/api/` with 403; `allow_uploads` is computed.

```
$ bash scripts/local/verify.sh d1
PASS  d1  read-only enforcement  all gated, negative case holds

# direct probe of the write surface, AIFP_READ_ONLY=1
upload -> 403   teams/swap -> 403   delete match -> 403
GET events -> 200   GET /media -> 200   GET /docs -> 200
capabilities -> {"read_only":true,"allow_uploads":false,...}
```
Negative case holds: with `AIFP_READ_ONLY=0` the same writes succeed, so this is not
middleware that simply blocks everything.

### D2 — Team assignment was non-deterministic and leaked across matches
**Root cause.** `cv_engine.py:197` labelled by cluster index (`best_k == 0`) over a
K=3 k-means with random init; both kits collapsed to one label in 4 of 6 runs.
`team_centers` was never reset on the module singleton, so match B inherited match A's
kit centroids. The grass mask (HSV hue 30–85) also swallowed yellow and lime kits.

**Fix.** Deterministic clustering, labels assigned by a stable hue-ordering rule rather
than init order, per-match state reset at the top of `process_video`, mask corrected.

```
$ bash scripts/local/verify.sh d2
PASS  d2  CV determinism  repeatable in-process and no cross-match leak (sig=61075316940f2cb1)
```
The probe runs the same video 3× in one process (identical labelling required) **and**
runs video B after video A, comparing against B run alone — the only check that
catches the singleton leak.

### D3 — `ix_radar_match_time` never reached existing databases
**Root cause.** `init_db()` migrated columns but not indexes.

**Fix.** `_reconcile_indexes()` creates any declared index the live DB is missing,
generically and idempotently.

```
$ bash scripts/local/verify.sh d3
PASS  d3  radar index on live db  migration creates index on an existing db
```
Probed against a **copy of the live DB with the index explicitly dropped** — never a
fresh database, which is the case that already worked.

### D4 — Synthetic fallback was labelled as real analysis
**Root cause.** `matches.py:100-105` set `analysis_mode="heuristic"`,
`confidence="medium"` unconditionally, including when `process_video` had silently
fallen back to sine-wave players.

**Fix.** The engine now declares its own run mode via `last_run_meta`; the route reads
it with a safe default of `("demo","low")` — if the engine claims nothing, we claim
nothing.

```
undecodable video -> {'mode': 'demo', 'confidence': 'low'}
real 90s video    -> {'mode': 'heuristic', 'confidence': 'medium'}

$ bash scripts/local/verify.sh d4
PASS  d4  honest fallback label  no unconditional heuristic label
```

**Note on attribution.** WP-3 did not implement the producer side. That was **my spec
error** — the mode contract was written into `wp-2.md` and never into `wp-3.md`. I
implemented it during integration and recorded it against the spec, not the model.

### D5 — Seeded analytics contradicted the seeded events
**Root cause.** Analytics claimed 3-3 with `tackles=41`, `passes_completed=203` while
the seeded events held one goal per side; the shot map had 5 entries against 2 events.

**Fix.** Every seeded number is now derived from the seeded events or set to `None` so
the UI renders `—`. The fix deliberately does **not** make the fiction self-consistent,
which would have been harder to detect than the original bug.

```
$ bash scripts/local/verify.sh d5
PASS  d5  seed self-consistency  seed is internally consistent
```

### D6 — Highlight export handed back the full match video
**Root cause, in two parts.** The export substituted `demo_match.mp4` for any missing
clip and buffered the whole archive in `io.BytesIO`. **And** the seed pointed every
highlight's `clip_url` at the full video, so even a correct export returned five copies
of the whole match under highlight names.

**Fix.** Export streams, never substitutes, and records unavailable clips in a
manifest. `_seed_clip()` cuts a real clip per highlight window and returns `None` if it
cannot.

```
$ bash scripts/local/verify.sh d6
PASS  d6  streaming zip export  5 clip member(s), all distinct, none a full video
```
The probe compares **every zip member byte-for-byte** against the candidate
substitutes, and fails outright if the zip contains no clips at all.

### D7 — Jobs stuck at `running` forever
**Root cause.** `jobs.status` documented an `interrupted` state that nothing ever set;
`repository.py:430` only read it. Observed live: job `8b0441a3` at `running`,
progress 0.0, indefinitely.

**Fix.** A startup sweep reclaims jobs left `running` by a dead process.

```
$ bash scripts/local/verify.sh d7
PASS  d7  orphaned-job sweep  stale job reclaimed (status=interrupted)
```

### D8 — `outcome="saved"` was invented
**Root cause.** `cv_engine.py:438` labelled every non-goal attempt `"saved"`. Nothing
distinguishes saved from blocked or off-target without GK-contact detection.

**Fix.** `"unknown"`.

### D9 — The test suite wrote to live data (found during this pass)
**Root cause.** No `conftest.py` isolated `AIFP_DATA_DIR`/`AIFP_MEDIA_DIR`, so every
upload test left a real match row and media file in `backend/.local`. **This is how the
orphaned match behind D7 got there.**

**Fix.** `backend/tests/conftest.py` redirects all three paths to a temp directory
before `backend.src` is imported. That immediately exposed a latent bug the shared
state had masked: `test_upload_pipeline` hardcoded `Path("backend/.local/media")`
instead of the configured `MEDIA_DIR`.

```
pytest: 35 passed;  live media 13 -> 13 files, matches 1 -> 1  (CLEAN)
```

## Two flaws in the verification harness itself

Worth recording, because they are the same class of error the harness exists to catch.

1. **d7 reported a false PASS** by grepping for `'interrupted'` — a string that appears
   only in a *read*. Replaced with a behavioural probe that plants a stale job.
2. **d6 passed vacuously** with "0 clip members": the probe's own isolation gave the
   server an empty media dir, so every clip was legitimately omitted and nothing was
   checked. It now carries small media files across and **fails** when a zip has no
   clips.

## Model scorecard

Seven dispatches across four CLIs. Verification was mine in every case; no package
author verified its own work.

| Package | Agent | Wall | Verdict | Fabricated a result? | Notes |
| :-- | :-- | --: | :-- | :-- | :-- |
| wp-4 | agy | 4 s | fail | no | headless auto-denied tool permissions; returned rc=0 with no output |
| wp-4 | agy/gemini-3.8-flash-high | 126 s | pass | no | changed public `init_db()` signature to suit its test; led with a fresh-DB assertion that cannot fail |
| wp-4 | opencode/qwen3.8 | 244 s | **pass, selected** | no | left the signature intact, proved the generic requirement with a second index, added idempotency |
| wp-1 | codex | 446 s | **pass** | no | clean pure-ASGI middleware; no deviations |
| wp-2 | claude/sonnet | 531 s | **pass** | no | reported `blocked`; **predicted its own regression correctly** |
| wp-5 | claude/sonnet | 707 s | **pass** | no | reported `blocked`; flagged a schema constraint it could not fix from inside its ownership |
| wp-3 | codex | 767 s | **pass** | no | missed `last_run_meta` — my spec gap, not its error |

**Truthfulness rate: 7/7.** Not one agent reported `complete` for work it had not
verified. Both claude runs were sandboxed out of executing anything and said so
explicitly rather than inventing acceptance output — one even delegated to a subagent
first to rule out a fluke. Given this codebase shipped six defects behind 18 green
tests, that is the single most valuable property observed.

**Scope discipline: 7/7.** No agent touched a file it did not own. (My first ownership
check missed *untracked* files — fixed, since that is exactly how a violation would
hide.)

**The controlled duplicate (wp-4).** Same spec, two agents, two worktrees. Both passed
my probe and a robustness probe that did **not** separate them. opencode was slower
(244 s vs 126 s) and produced the better change. One trial; not a general claim.

**Cost.** claude: $2.05 + $2.48. codex and opencode/agy exposed no per-call cost.
Orchestrator verification time was 9–16 minutes per package and is the real denominator
— a free model needing review rounds is not free.

**Measurement caveat.** `diff_lines` for wp-2/wp-3/wp-5 (715/917/722) is **inflated and
not comparable**: the wrapper diffed against `main`, which had advanced with other
merges. Only the wp-4 pair (20 vs 23), measured before main moved, is a valid
comparison.

## Not done, and honestly labelled

- **Nothing about the GPU pipeline is verified**, because none of it is built yet. The
  box is provisioned (torch 2.11.0+cu128, CUDA 12.8, 4× H100) and the match video is
  there with a matching sha256, but no detection, tracking, homography or event code
  exists. The benchmark has **not** been scored. No claim about Veo parity is made.
- **`pass_strings`** is a non-`Optional` field on `AnalyticsData`, so WP-5 could not set
  it to `None` from inside its ownership; it is `{"home": [], "away": []}`. Making the
  field `Optional` is follow-up.
- **P3 accessibility and responsive work** (WP-6a/6b) was not dispatched.
- **`RadarBall.x/y` are non-`Optional`**, so "no ball" cannot be expressed structurally;
  `detected=False` still carries coordinates. Whether the frontend honours `detected`
  before drawing is **unchecked** — if it draws regardless, that is a live fabrication
  in the UI.
- The 1 remaining lint warning in `App.tsx` is pre-existing and untouched.

## The finding that most changes what comes next

**The camera pans.** Frames at video t=700 / 2000 / 4000 / 5500 are four completely
different views: this export is Veo's ball-following pan-and-zoom crop, not the static
panorama. A single fixed homography is therefore the wrong *shape* of solution, and
`cv_engine.py:23-40` — fixed image fractions mapped onto 105×68 — is meaningless on
this footage. Two further complications visible in the same frames: the pitch carries
**two overlapping line systems** (white match lines plus a blue layout for another
field), and **goals from adjacent pitches appear in shot**.

Before building per-frame registration, check whether Veo will re-export the
**panorama** of this match. That would make the camera static and collapse the problem
to a one-time 8-point calibration.

And when the pipeline does produce numbers, the scoring harness must print the
**expected-by-chance baseline** beside recall. The Colab notebook's 97th-percentile
ball-speed heuristic would score ≈7.6 of 13 attempts **by luck alone** (~90 candidates,
±30 s tolerance, 6173 s of video) and would have printed "recall 10/13" as if it were a
result.
