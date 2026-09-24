# STATE — Live Progress Tracker

**Purpose:** Live project status and verification contract. Update as you go. For in-depth post-mortems, mathematical derivations, and historical failure analysis, consult the companion document: [docs/postmortems/falsification_log.md](file:///home/ai/Projects/ai-focus-play/docs/postmortems/falsification_log.md).

**Last updated:** 2026-09-23 · **ALL 14 TYPES HAVE A VERDICT.**
- **Track 2 (UI / Route Parity)**: **COMPLETE & AUDITED** (Visual side-by-side audit against live Veo UI documented in `docs/ui_parity_comparison.md`).
- **Track 3 (D-B Pixel-Space Detection)**: **SHIPPED & GATED**. 6 of 14 types scored against the 447-event Veo benchmark (141 events, 32% of mass). Macro-F1: **0.278** reported / **0.253** conservative ($p < 0.05$ permutation-cleared).
- **All remaining detectors FALSIFIED**:
  - `FootballShot`: Period 2 F1 **0.120** (beaten by the OutOfPlay stoppage control at 0.149).
  - `FootballFreeKick`: Period 2 F1 **0.000** (0 of 10).
  - `Tier B` (Possession / Tackles / Interceptions / Dribbles, 241 events): 15 fps gate **FAILED**. 2D containment cannot resolve 3D depth; shirt-color AUC is **0.503** over open-play attributed boxes.
  - `D-A Metric Calibration`: Inverting player footprints produces a **105.8m × 104.5m square**; ground plane perspective is ill-conditioned on low-pole amateur video.
- **Veo Ground Truth & Calibration Assets Extracted**:
  - Live UI Ground Truth: `benchmarks/raw/veo_stats_live.json` (all 13 stats rows, 25 shot coordinates, pass/possession distributions, 16-player roster).
  - Dual-Camera Extrinsics & Calibration: `benchmarks/raw/skyline_camera_alignment.veo`, `benchmarks/raw/baltimore_armor_camera_alignment.veo`.
  - Secondary Match Multi-Video Sample: `backend/.local/media/baltimore_armor_sample_30s.mp4`.
- **Baseline Verification**: **`pass=12 fail=0 skip=0`** (probes `d1`–`d12`), **69 pytest tests passing**, **22 vitest tests passing** (non-interactive).

---

## What This System Can and Cannot Do

Audited against a clean rebuild from scratch (`bash scripts/local/verify.sh all`). Ball track sha `1ced4109f521208f` and all headline figures reproduce deterministically.

### 1. Detected Events (6 of 14 Types, 141 of 447 Events, 32% Mass)

| Type | $n_\text{ref}$ | $n_\text{pred}$ | F1 Team-Agnostic | F1 Team-Aware | Team Attribution Channel |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OutOfPlay** | 64 | 127 | 0.356 | 0.147 | Chained off restarts — **not a result** ($p=0.259$). Emitted unteamed in ML mode. |
| **ThrowIn** | 38 | 52 | 0.244 | **0.200** | Thrower's shirt colour — **a result** ($p=0.020$). |
| **GoalKick** | 16 | 13 | 0.276 | **0.276** | Defend-end mapping + halftime swap. |
| **CornerKick** | 9 | 11 | 0.100 | 0.100 | Defend-end mapping; type ties random control. |
| **KickOff** | 8 | 4 | **0.667** | **0.500** | Centre-spot restart + goal-end lookback. |
| **Goal** | 6 | 3 | 0.444 | **0.444** | Inferred from post-goal kickoff offset (38.13s). Low-$n$. |
| **Macro** | — | — | **0.348** | **0.278** | Conservative (unverified channels zeroed): **0.253**. Micro-F1: **0.188**. |

### 2. Closed & Falsified Capabilities (Evidence Logged in [falsification_log.md](file:///home/ai/Projects/ai-focus-play/docs/postmortems/falsification_log.md))

| Capability | Benchmark Mass | Evidence & Diagnosis |
| :--- | :--- | :--- |
| **Tier B (Interception, Tackle, Dribble, Loose ball)** | 241 events (54%) | **15 fps gate FAILED**. Attribution rose to 0.98, but accuracy remained at chance and shirt AUC was **0.503** over 86 px boxes. 2D bounding boxes cannot resolve 3D height/depth. |
| **Metric Calibration / 2D Pitch Radar** | Coordinates on 355 events | **5 methods measured and failed**. Centre circle converges ($h=6.71\text{m}$, tilt $0.87^\circ$), but outline is misaligned 24–51 px. Ground plane inverts to a square. |
| **Shot Detection (`FootballShot`)** | 25 events (5.6%) | **Pre-registered gate FAILED**. Period 2 F1 = 0.120, beaten by OutOfPlay stoppage control (0.149). Goal-directed motion conflates with clearances without 3D depth. |
| **FreeKick & Foul Detection** | 30 events (6.7%) | **Pre-registered gate FAILED**. FreeKick Period 2 F1 = 0.000. In-pitch stoppages conflate with out-of-play returns. Whistle audio is absent from footage. |
| **Camera Motion as Event Signal (D-0)** | Halftime & stoppages | **FALSIFIED**. Camera continuously roams at ~10 px/s during halftime. Frame-to-frame chaining drifts 10.6x across match duration. |
| **Jersey Recognition (G7)** | Player attributes | **DEFERRED**. No team roster available; open-set classification has an honest ceiling of ~25–40% and unlocks zero event types. |

---

## Resume in 60 Seconds

1. **Verify Environment**:
   ```bash
   bash scripts/local/verify.sh all    # Expect pass=11 fail=0 skip=0
   backend/.venv/bin/python -m pytest backend/tests -q  # Expect 48 passed
   cd frontend && npm run test         # Expect 18 passed
   ```
2. **Ground Truth**: Located at `benchmarks/raw/veo_events_447.csv` (447 events, exact timestamps).
   - Time base: Period 1 `video = match + 562s`; Period 2 `video = match + 3674s`. Halves are 2317.0s and 2457.7s.
3. **Artifacts on Disk**: Stored under `backend/.local/artifacts/mosaic/`:
   - `panorama.png`, `cameras.json`, `ball_track.json`, `pitch_frame.json`, `pred_all.json`, `score_all.json`, `manifest_all.json`.
4. **Active Rule**: When a capability is not implemented, **render an empty state (`—` or "not detected") with its measured reason**. Never show plausible fabrications.

---

## Work Package Status Matrix

Legend: ☑ Done & Verified · ◐ In Progress · ⊘ Blocked · ⏸ Deferred · ✗ Falsified / Closed

### Cross-Cutting & Honesty Probes
| ID | Description | Status | Verification Reference |
| :--- | :--- | :--- | :--- |
| **X1** | Delete `pass_strings` and `or 20.0` fallbacks | ☑ | Commit `c38d62f`, verified by `d10` |
| **X2** | Probe `d10`: No invented analytics literals | ☑ | Passes negative testing on pre-fix code |
| **X3** | `PitchRadar`: Renders "Ball not detected" caption | ☑ | Frontend test verified |
| **X4** | Probe `d11`: ML ingest honesty & capability surface | ☑ | Refuses positions, verifies 16-type surface |
| **X5** | Probe `d12`: Pydantic defaults clean of literals | ☑ | Tests fresh instance isolation & empty defaults |

### Track 1 & 3: CV Pipeline & Detection (D-B Pixel Space)
| ID | Description | Status | Verification Reference |
| :--- | :--- | :--- | :--- |
| **G0** | Rebuild benchmark from 447-event API dump | ☑ | `benchmarks/raw/veo_events_447.csv` |
| **G1** | Ball detection recall gate | ☑ | Tiled YOLO11x: 0.833 (P1) / 0.828 (P2) |
| **G2 / D-A** | Metric pitch calibration | ✗ | **CLOSED**: Failed 5 times; see [falsification_log.md §3](file:///home/ai/Projects/ai-focus-play/docs/postmortems/falsification_log.md#3-d-a--g2-metric-pitch-calibration-failed--stopped) |
| **B1–B5** | Panorama, occupancy, and Viterbi ball track | ☑ | 4414×1190 panorama, 10,994-point track |
| **B6–B13**| Dead-ball restart detectors (OOP, ThrowIn, GoalKick, Corner, KickOff, Goal) | ☑ | Macro-F1 0.278 (team-aware), 141 events |
| **B14** | Prediction budget enforcement ($K=3$) | ☑ | Controls false-positive gaming of F1 |
| **B16** | Throw-in team attribution via shirt color | ☑ | $p=0.020$ on `control_team_shuffle.py` |
| **B21** | Ball-track coverage expansion | ✗ | **CLOSED**: Erases coverage collapse signal; drops macro-F1 |
| **B23 / G4**| Tier B possession HMM | ✗ | **CLOSED**: 15 fps gate failed; see [falsification_log.md §4](file:///home/ai/Projects/ai-focus-play/docs/postmortems/falsification_log.md#4-d-b--tier-b-2d-containment--possession-falsified) |
| **P1** | `FootballShot` detector | ✗ | **CLOSED**: Period 2 F1 0.120, beaten by OOP proxy (0.149) |
| **P2** | `FootballFreeKick` & `FootballFoul` | ✗ | **CLOSED**: Period 2 F1 0.000 / 0.143; whistle unrecoverable |
| **G7** | Jersey recognition | ⏸ | **DEFERRED**: Honest ceiling 25–40%, unlocks 0 event types |
| **G8** | Veo dual-camera extrinsics & multi-sample dataset | ☑ | Extracted `.veo` calibrations and Baltimore Armor 30s sample |

### Track 2: UI & Route Parity (COMPLETE)
| ID | Description | Status | Verification Reference |
| :--- | :--- | :--- | :--- |
| **U1** | Deep-link hash router (`#/<tab>/`) & Share | ☑ | Tested on all 7 routes |
| **U2** | Jersey-only identity (no fabricated player names) | ☑ | Blank number convention; 0 invented names |
| **U3** | 16-type capability surface in Events drawer | ☑ | Renders count or measured unavailable reason |
| **U4** | Singular stat labels & disabled derived rows | ☑ | Accordion integration; comment threads at `#/highlights/<uuid>/comments/` |
| **P7** | Non-interactive Vitest frontend test suite | ☑ | 22 tests passing; covers radar absence, stats, and honesty |
| **U5** | Live Veo UI audit & ground-truth parity | ☑ | `benchmarks/raw/veo_stats_live.json`, `docs/ui_parity_comparison.md`, 69 pytest tests |
| **U6** | Live Veo Benchmark comparison drawer & API | ☑ | `/api/matches/{id}/benchmark`, `stats_benchmark.py`, toggleable side-by-side delta cards in Stats drawer, live UI verified |
| **U7** | Tactical half-pitch Shot Map & 5-metric breakdown | ☑ | Attacking half SVG, wing labels, 5 conversion metrics, Veo live GT shot markers, 22 vitest tests |

---

## Blockers & Infrastructure Status

| Resource | Status | Notes |
| :--- | :--- | :--- |
| **gpu-box SSH** | Operational (Tailscale) | May require re-auth if token expires (`doctor.sh`). `/workspace` is tmpfs. |
| **Local Environment** | Healthy | Python 3.14.7 venv, Node/npm vitest working hermetically. |
| **Sample Diversity** | Single Video Constraint | Current pipeline is evaluated on 1 sample match (Arlington vs. Skyline). User is able to provide additional Veo match MP4s with varying parameters (camera height, lighting, angles) for multi-sample validation. |
