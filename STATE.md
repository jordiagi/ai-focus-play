# STATE — Live Progress Tracker

**Purpose:** Live project status and verification contract. Update as you go. For in-depth post-mortems, mathematical derivations, and historical failure analysis, consult the companion document: [docs/postmortems/falsification_log.md](file:///home/ai/Projects/ai-focus-play/docs/postmortems/falsification_log.md).

**Last updated:** 2026-09-24 · **ROADMAP OPTIONS 1, 2, 3, 4 COMPLETED & MULTI-MATCH PIPELINE VERIFIED.**
- **Track 2 (UI / Route Parity)**: **COMPLETE & AUDITED** (Visual side-by-side audit against live Veo UI documented in `docs/ui_parity_comparison.md`, deep-link routing, tactical shot map 5-metric breakdown, Veo GT overlay).
- **Track 3 (D-B Pixel-Space Detection)**: **SHIPPED & GATED**. 6 of 14 types scored against the 447-event Veo benchmark (141 events, 32% of mass). Macro-F1: **0.278** reported / **0.253** conservative ($p < 0.05$ permutation-cleared).
- **Option 1 (2D Pitch Radar Physical Calibration)**: **RESOLVED & SHIPPED**. Unconstrained 8-point homography failure resolved by physical camera extrinsics (`VeoCameraModel` & `CalibratedPitchRadar`). 99.9% (10,978 / 10,994) of ball track points and 100% of sampled player footprints land validly within pitch bounds $[0, 105]\text{m} \times [0, 68]\text{m}$.
- **Option 2 (Foot-Level Spatial Masking / Tier B Resurrection)**: **GATE PASSED**. Root cause of previous failure was 2D whole-body depth conflation. Restricting ball proximity strictly to the bottom 15% foot-contact zone (`route_foot_contact`) achieves Period 1 accuracy **0.696**, Period 2 held-out accuracy **0.645** (beating 0.613 majority baseline), and balanced accuracy **0.649** (exceeding 0.55 floor). `gate_fps15.json` status: **`GATE: PASS`**.
- **Option 4 (Unified MatchPipeline DAG Runner)**: **SHIPPED**. Refactored `pipeline_runner.py` orchestrating asset resolution, physical calibration, calibrated radar frames, event ingestion, and capability manifest verification.
- **Secondary Match Discovery & Veo Parity Verification**: **COMPLETE & VERIFIED**.
  - Connected to live Veo session via `browser-harness` and selected **Arlington SA U16B ECNL (26-27) vs. Fairfax Union** (Sept 20, 2026, 3-0 result, Match UUID `45cf9155-0ea3-4d56-957a-e454de77e216`).
  - Extracted `.veo` camera alignment to `benchmarks/raw/fairfax_union_camera_alignment.veo` (camera height 4.17m, 105.0m × 70.26m pitch).
  - Extracted 30-second 1080p sample video from signed CDN stream to `backend/.local/media/fairfax_union_sample_30s.mp4`.
  - Extracted complete live analysis and stats ground-truth to `benchmarks/raw/fairfax_union_stats.json` (13 metrics table, 23 shots + 3 goals breakdown, 389 events, 26 AI highlights, pass & possession distributions).
  - Executed and validated `MatchPipeline` across both ML and demo modes on the new match, generating calibrated 2D pitch radar frames and event capability manifest.
  - Multi-match switcher deployed to local UI header with instant match switching, query URL synchronization, and dynamic match-specific Veo ground-truth benchmark comparison.
  - Protected sample video fixtures from unlinking during match cleanup in `MatchRepository`.
- **Baseline Verification**: **`pass=11 fail=0 skip=0`** (probes `d1`–`d12`), **92 pytest tests passing**, **28 vitest tests passing** (non-interactive).

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
| **G2 / D-A** | Metric pitch calibration | ☑ | **RESOLVED via VeoCameraModel**: Physical extrinsics replace unconstrained 8-pt homography; 99.9% ball points & 100% player footprints on pitch |
| **B1–B5** | Panorama, occupancy, and Viterbi ball track | ☑ | 4414×1190 panorama, 10,994-point track |
| **B6–B13**| Dead-ball restart detectors (OOP, ThrowIn, GoalKick, Corner, KickOff, Goal) | ☑ | Macro-F1 0.278 (team-aware), 141 events |
| **B14** | Prediction budget enforcement ($K=3$) | ☑ | Controls false-positive gaming of F1 |
| **B16** | Throw-in team attribution via shirt color | ☑ | $p=0.020$ on `control_team_shuffle.py` |
| **B21** | Ball-track coverage expansion | ✗ | **CLOSED**: Erases coverage collapse signal; drops macro-F1 |
| **B23 / G4**| Tier B possession association gate | ☑ | **GATE PASSED**: Foot-region spatial masking (`route_foot_contact`) clears gate (P1 0.696, P2 0.645 vs 0.613 maj, bal 0.649 vs 0.55) |
| **P1** | `FootballShot` detector (3D metric kinematics) | ☑ | **GATE PASSED**: `PhysicsShotDetector` projects to 2D turf plane; Period 2 heldout F1 = **0.385** (TP=10/11, Prec=0.244, Rec=0.909), beats chance (5.77x vs 2.0x floor), beats OOP proxy (+0.236). `gate_shot_physics.json` status: **PASS** |
| **P2** | `FootballFreeKick` & `FootballFoul` | ✗ | **CLOSED**: Period 2 F1 0.000 / 0.143; whistle unrecoverable |
| **G7** | Jersey recognition | ⏸ | **DEFERRED**: Honest ceiling 25–40%, unlocks 0 event types |
| **G8** | Veo dual-camera extrinsics & multi-sample dataset | ☑ | Extracted `.veo` calibrations and Baltimore Armor 30s sample |
| **O1** | 2D Pitch Radar physical calibration service | ☑ | `CalibratedPitchRadar`, `veo_calibrator.py`, 7 unit tests passing |
| **O2** | Foot-contact spatial masking & Tier B gate clearance | ☑ | `route_foot_contact` in `gate_association_fps.py`, 2 unit tests passing |
| **O4** | Unified `MatchPipeline` DAG runner | ☑ | `pipeline_runner.py` with self-verification, 3 unit tests passing |

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
| **U8** | Multi-Match Switcher & dynamic match-specific Veo benchmark comparison | ☑ | Dropdown in Header, query param sync, `fairfax_union_stats.json` & `veo_stats_live.json`, 24 vitest tests |
| **U9** | Player Moments & Jersey Tag Filtering in Video Timeline & Drawers | ☑ | Cross-linked jersey selection across `PlayerMomentsBar`, `Timeline`, `Highlights`, `Events`, and dedicated player view in `Players` drawer; 28 vitest tests |

---

## Blockers & Infrastructure Status

| Resource | Status | Notes |
| :--- | :--- | :--- |
| **gpu-box SSH** | Operational (Tailscale) | May require re-auth if token expires (`doctor.sh`). `/workspace` is tmpfs. |
| **Local Environment** | Healthy | Python 3.14.7 venv, Node/npm vitest working hermetically. |
| **Sample Diversity** | Single Video Constraint | Current pipeline is evaluated on 1 sample match (Arlington vs. Skyline). User is able to provide additional Veo match MP4s with varying parameters (camera height, lighting, angles) for multi-sample validation. |
