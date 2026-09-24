# STATE — Live Progress Tracker

**Purpose:** Live project status and verification contract. Update as you go. For in-depth post-mortems, mathematical derivations, and historical failure analysis, consult the companion document: [docs/postmortems/falsification_log.md](file:///home/ai/Projects/ai-focus-play/docs/postmortems/falsification_log.md).

**Last updated:** 2026-09-24 · **3RD MATCH (BALTIMORE ARMOR) INGESTED, CALIBRATED, & VERIFIED ACROSS DAG & UI.**
- **Track 2 (UI / Route Parity)**: **COMPLETE & AUDITED** (Visual side-by-side audit against live Veo UI documented in `docs/ui_parity_comparison.md`, deep-link routing, tactical shot map 5-metric breakdown, Veo GT overlay).
- **Option B (Physics-Based 3D Goal-Directed Shot Detection Gate & DAG Integration)**: **SHIPPED & GATED**. `PhysicsShotDetector` projects 2D panoramic points $(u, v)$ to metric pitch coordinates $[0, 105]\text{m} \times [0, 68]\text{m}$ using `VeoCameraModel`. Cleared pre-registered criteria S1 ($F1 \ge 0.25$), S2 ($\ge 2.0\times$ chance [5.77x]), and S3 (beats OutOfPlay proxy [+0.236]) with Period 2 heldout F1 = **0.385** (Recall = **0.909** [10/11 matched], Precision = 0.244). Wired directly into `MatchPipeline` DAG stage 3b: auto-generates metric `Shot` events with $(x, y)$ turf coordinates, speeds, and goal alignment, dynamically updating `event_capabilities["Shot"]` to `detected`.
- **Option C (Video Telestration & Drawing Enhancement)**: **SHIPPED & TESTED**. Enhanced `TelestratorCanvas` with Veo-style spotlight, directional arrows, player tactical rings, freehand pen, and text labels. Added undo active stroke, hotkey `D` and player toolbar `Draw` toggle, and frame snapshot PNG export with Veo watermark badge.
- **Option D (Clip Download & Streaming Zip Export in Header Menu)**: **SHIPPED & VERIFIED**. Connected download dropdown to Full Match Video (`/media/...`), streaming zip highlight clips (`/api/matches/{id}/highlights/export` and `/api/matches/{id}/export/zip`), match analytics JSON export, and events/highlights CSV spreadsheet export with click-outside dismissal.
- **3-Match Campaign Ingestion (Skyline, Fairfax Union, Baltimore Armor)**: **SHIPPED & TESTED**. All 3 matches calibrated with physical `.veo` camera alignment models, sample MP4 video fixtures, live Veo analytics benchmark ground truth, and MatchPipeline DAG execution.
- **Baseline Verification**: **`pass=11 fail=0 skip=0`** (probes `d1`–`d12`), **100 pytest tests passing**, **33 vitest tests passing** (non-interactive).

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
| **U10** | Video Telestration & Frame Snapshot PNG Export (Option C) | ☑ | Spotlight, directional arrow, player tactical ring, freehand pen, text labels, undo active stroke, hotkey `D` & player toolbar `Draw` toggle, Veo watermark snapshot; 32 vitest tests |
| **U11** | Clip Download & Streaming Zip Export in Header Menu (Option D) | ☑ | Full match video MP4, streaming zip highlights (`/export/zip`), match analytics JSON, and tagged events/highlights CSV export; 33 vitest tests |
| **U12** | 3-Match Campaign Ingestion & Multi-Match Veo Parity | ☑ | Arlington vs Skyline, Fairfax Union, and Baltimore Armor; physical camera models, live benchmark mapping, dynamic match switcher, 100 pytest tests passing |

---

## Blockers & Infrastructure Status

| Resource | Status | Notes |
| :--- | :--- | :--- |
| **gpu-box SSH** | Operational (Tailscale) | May require re-auth if token expires (`doctor.sh`). `/workspace` is tmpfs. |
| **Local Environment** | Healthy | Python 3.14.7 venv, Node/npm vitest working hermetically. |
| **Sample Diversity** | Multi-Match Validated (3 Matches) | Pipeline and UI evaluate across 3 real ECNL matches (Skyline, Fairfax Union, Baltimore Armor) with varying camera heights ($4.17\text{m} - 4.22\text{m}$), field geometries ($105\text{m} \times 67.7\text{m} - 70.3\text{m}$), and live Veo stats ground truth. |

