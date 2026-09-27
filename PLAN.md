# Autonomous Computer Vision Match Analytics Engine (`PLAN.md`)

> **PARADIGM SHIFT as of 2026-09-26**:
> 
> **Eliminating the Ground-Truth Shortcut.** During initial development, Arlington matches (Skyline, Fairfax Union, Baltimore Armor) utilized Veo cloud API exports (`veo_events_447.csv`, `fairfax_union_stats.json`, `veo_stats_live.json`) to establish UI parity and test the verification harness. When the generalized YouTube match (**Turo vs. Horta**) was ingested without an API export, `build_ml_analytics()` defaulted to empty states and em-dashes due to the honesty contract.
>
> Relying on proprietary cloud API dumps is benchmarking, not production. The true objective of `ai-focus-play` is to take any raw match recording (broadcast, mobile, or tactical camera) and autonomously extract complete, Veo-grade analytics directly from video pixels without external exports.
>
> This plan defines the end-to-end architecture to achieve true algorithmic parity.

---

## 1. Executive Summary & Problem Diagnosis

### The "Cheat" Gap: What Happened
1. **Arlington Matches**: Displayed rich possession percentages (54% vs 46%), pass strings histograms, shot maps, and complete 23-player rosters with jersey numbers. All of this came from `build_analytics_from_benchmark()` parsing Veo's cloud JSON, not from the local CV models.
2. **Turo vs. Horta Match**: Ingested blindly from YouTube (`tb-youtube-download`). With no ground-truth JSON available, `pipeline_runner.py` routed to `build_ml_analytics()`. Because the CV pipeline lacked autonomous modules for dynamic camera calibration, tracklet-level OCR, and turf-level possession modeling, the honesty probes correctly suppressed fabricated metrics, leaving the UI sparse.

### Is Autonomous Parity Possible?
**Yes.** Commercial platforms (Veo, Hudl Focus, Spiideo) do not employ human taggers or wearable GPS sensors for base analytics; their cloud servers extract tracking, events, and statistics purely from video. However, they do not rely on naive single-frame 2D object detection. They chain:
1. **Dynamic Pitch Homography** (mapping video pixels to a standard 105m × 68m metric pitch).
2. **Multi-Frame Tracklet Aggregation** (pooling observations over hundreds of frames for jersey numbers and team ReID).
3. **Turf-Level Spatial Association** (evaluating ball-foot contact on the 2D pitch plane rather than 2D screen bounding boxes).
4. **Temporal Event State Machines** (identifying kicks, passes, and turnovers as sequential state transitions).

---

## 2. The 4 Core Pillars of Autonomous Analytics

```
                     ┌──────────────────────────────────────────────┐
                     │          Raw Match Video (1080p MP4)         │
                     └──────────────────────┬───────────────────────┘
                                            │
                    ┌───────────────────────┴───────────────────────┐
                    ▼                                               ▼
     ┌─────────────────────────────┐                 ┌─────────────────────────────┐
     │  Pillar 1: Pitch Homography │                 │ Pillar 2: Tracklet Tracking │
     │  - Field line segmentation  │                 │ - ByteTrack multi-object    │
     │  - Landmark keypoint solver │                 │ - CIELAB kit clustering     │
     │  - Frame-by-frame H_t matrix│                 │ - Multi-frame jersey voting │
     └──────────────┬──────────────┘                 └──────────────┬──────────────┘
                    │                                               │
                    │   ┌───────────────────────────────────────────┘
                    ▼   ▼
     ┌─────────────────────────────────────────────────────────────┐
     │  Pillar 3: Turf-Level Ball-Foot Association & Possession    │
     │  - Ball trajectory projection to metric turf plane (x, y)   │
     │  - Player ground contact points (bottom-center of bbox)     │
     │  - Temporal State Machine: Kick -> Transit -> Reception     │
     │  - Outputs: Possession %, Pass Strings, Turnovers, Heatmaps │
     └──────────────────────────────┬──────────────────────────────┘
                                    │
                                    ▼
     ┌─────────────────────────────────────────────────────────────┐
     │  Pillar 4: Autonomous Event & Highlight State Machine       │
     │  - PhysicsShotDetector (metric velocity towards goal mouth) │
     │  - Dead-ball restarts: KickOff, GoalKick, Corner, ThrowIn   │
     │  - Goal confirmation via kickoff offset & score updates     │
     │  - Fully populated AnalyticsData without API imports        │
     └─────────────────────────────────────────────────────────────┘
```

---

### Pillar 1: Dynamic Pitch Homography & Metric Turf Projection (WP G9)

#### The Limitation
In `falsification_log.md` (Section 3), static homography failed on grazing-angle broadcast cameras because integrating frame-to-frame optical flow drifted 10.6x across the match, and unconstrained SIFT latched onto spectators and trees. Furthermore, broadcast cameras pan, tilt, and zoom continuously.

#### The Architecture
1. **Pitch Feature Extraction**: Segment pitch boundary lines, touchlines, 18-yard penalty boxes, goal boxes, and the center circle per frame.
2. **Landmark Solver**: Identify canonical geometric intersections (penalty box corners, halfway line touchline T-junctions, center circle center).
3. **Per-Frame Homography $H_t$**:
   $$\begin{bmatrix} X_\text{pitch} \\ Y_\text{pitch} \\ 1 \end{bmatrix} \sim H_t \begin{bmatrix} u_\text{pixel} \\ v_\text{pixel} \\ 1 \end{bmatrix}$$
   Mapping pixel coordinates $(u, v)$ to FIFA standard pitch metric coordinates $[0, 105]\text{m} \times [0, 68]\text{m}$.
4. **Deliverables**:
   - Real-time 2D Pitch Radar working on any panning/zooming camera.
   - Metric player coordinates $(x, y)$ on turf.
   - Physical ball coordinates and velocity vectors in m/s.

---

### Pillar 2: Multi-Frame Tracklet Tracking & Jersey Number Voting (WP G10)

#### The Limitation
Single-frame OCR on 1080p match video yields ~25–40% accuracy due to motion blur, low pixel height (player boxes are 40–80px, numbers are 10–20px), and players facing away from the camera.

#### The Architecture
1. **Multi-Object Tracking (MOT)**: Implement **ByteTrack** / **BoT-SORT** to track player detections into persistent tracklets spanning dozens to hundreds of frames.
2. **Tracklet Kit Clustering**:
   - Extract player shirt crops across the tracklet.
   - Compute CIELAB color histograms on upper torso regions.
   - Cluster into two dominant field team kits (e.g. Green vs. White) plus goalkeeper kits using Gaussian Mixture Models (GMM) with temporal consistency.
3. **Multi-Frame Jersey Digit Voting**:
   - Detect frames where a player is moving away from the camera (back of shirt visible).
   - Crop upper-back region and run digit recognition (SVHN-style lightweight CNN / CRNN).
   - Maintain a probability histogram of predicted jersey numbers for each tracklet:
     $$P(\text{jersey} = k \mid \text{tracklet}) \propto \sum_{t \in \text{visible}} \log P(k \mid \text{crop}_t)$$
   - Only assign a jersey number when the top candidate exceeds confidence threshold $\tau \ge 0.70$ across $\ge 5$ consistent frames.
4. **Deliverables**:
   - Lineup extraction with verified jersey numbers.
   - Player-specific timeline events and highlight tagging.
   - Player movement heatmaps and distance covered metrics.

---

### Pillar 3: Turf-Level Ball-Foot Association & Possession Engine (WP G11)

#### The Limitation
In `falsification_log.md` (Section 4), the 15 fps association gate failed because 2D bounding boxes contain no depth: a ball kicked 15 meters in the air overlaps players standing 30 meters away in the background (shirt AUC was 0.503).

#### The Architecture
1. **Turf Projection**: Evaluate proximity on the **metric turf plane**, not in 2D image coordinates.
   - Player position on turf = $H_t \cdot (u_\text{bottom\_center}, v_\text{bottom\_center})$.
   - Ball ground position = $H_t \cdot (u_\text{ball}, v_\text{ball})$ when ball vertical height estimate is near zero.
2. **Temporal State Machine (Possession & Pass Detection)**:
   - **State 1: Ball in Control (Player $P_i$)**: Ball is within $d \le 1.8\text{m}$ of $P_i$'s turf position for $\ge 3$ consecutive frames.
   - **State 2: Kick / Release**: Ball accelerates away from $P_i$ ($v_\text{ball} > 4.0\text{m/s}$ and distance increases).
   - **State 3: Ball in Flight / Transit**: Ball follows kinematic trajectory across turf.
   - **State 4: Reception / Control**: Ball decelerates within $1.8\text{m}$ of $P_j$:
     - If $\text{Team}(P_j) == \text{Team}(P_i)$: **Completed Pass**. Increment team pass string count.
     - If $\text{Team}(P_j) \neq \text{Team}(P_i)$: **Interception / Turnover**. Reset pass string, attribute turnover.
     - If ball crosses boundary: **Out of Play**.
3. **Deliverables**:
   - Autonomous **Possession %** (cumulative time of team control vs. total in-play time).
   - Autonomous **Pass Strings Histogram** (sequences of 3, 4, 5, 6, 7, 8, 9, 10+ completed passes).
   - Thirds breakdown: Possession location (% defensive, % middle, % attacking third).

---

### Pillar 4: Autonomous Event & Highlight State Machine (WP G12)

#### The Architecture
1. **Shot Detection (`PhysicsShotDetector`)**:
   - Compute ball velocity towards opposing goal mouth on metric turf:
     $$\mathbf{v}_\text{ball} = \frac{\Delta \mathbf{x}_\text{turf}}{\Delta t}, \quad \text{Speed} \ge 12.0\text{m/s}, \quad \mathbf{v} \cdot \hat{\mathbf{g}}_\text{goal} > 0.85$$
   - Check origin: inside attacking third ($X_\text{pitch} > 70\text{m}$ or $< 35\text{m}$).
   - Outcome classification: on-target vs off-target based on goal line intersection.
2. **Goal & Scoreboard Tracking**:
   - Goal candidate triggered when ball enters goal bounding volume or crosses goal line.
   - Confirmed by post-goal cessation of play followed by KickOff at center circle ($t \in [20\text{s}, 60\text{s}]$ later).
   - Live score dynamically increments.
3. **Dead-Ball Restarts**:
   - **KickOff**: Static ball at center spot $(52.5\text{m}, 34.0\text{m}) \pm 2\text{m}$ with players in their respective halves.
   - **ThrowIn**: Static ball at touchlines with thrower motion and ball entering pitch.
   - **CornerKick**: Ball placed in corner arcs $(0/105, 0/68)$.
   - **GoalKick**: Ball placed within 6-yard box and kicked downfield.
4. **Highlights & Clip Generation**:
   - Auto-extract 15-second video windows around verified Goals, Shots, and key restarts.
   - Populate `repo.add_highlight()` directly from detection timestamps.

---

## 3. Work Package & Execution Roadmap

| Phase | WP | Description | Deliverable | Acceptance Gate |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **G9** | Dynamic Pitch Homography | `pitch_homography.py` | Mean pitch reprojection error $< 2.5\text{m}$ across 100 sample frames |
| **Phase 2** | **G10** | Tracklet Tracking & Jersey Voting | `tracklet_tracker.py` | Tracklet persistence $\ge 90\%$ over 5s windows; Jersey voting accuracy $\ge 80\%$ on clear frames |
| **Phase 3** | **G11** | Turf-Level Possession & Passes | `turf_possession.py` | Pass completion precision $\ge 75\%$; Possession % matches benchmark within $\pm 4\%$ |
| **Phase 4** | **G12** | Autonomous `build_ml_analytics()` | `ml_analytics.py` & DAG runner | Full `AnalyticsData` populated for arbitrary video; 0 benchmark file dependencies (☑ Completed) |
| **Phase 5** | **G13** | Federation Acta Ingestion & Option A Reconciliation | `federation_acta.py`, `filename_infer.py`, `TeamsModal.tsx` | Auto-infer match from MP4 filename; reconcile score/lineup/cards/subs with official FCF/ECNL sheets; roster-backed OCR prior; Turó match reprocessed (☑ Completed) |
| **Phase 6** | **G14** | 3-Match Blind CV Evaluation & Parity Benchmark | `tune_cv_parity.py`, `extract_baltimore_artifacts.py` | Blind evaluation across all 3 Arlington matches (Skyline, Fairfax Union, Baltimore Armor); Overall MAE: 11.37% possession, 48.7 passes, 8.5 shots (☑ Completed) |

---

## 4. Verification & Honesty Contract

1. **No Hardcoded Constants**: No match identifiers, static rosters, or predefined scorelines in analysis scripts.
2. **Deterministic Evaluation**: Re-running the pipeline on `turo_peira_vs_horta_20260920.mp4` produces identical metric outputs.
3. **Adversarial Integrity**: Tests assert that `build_ml_analytics()` produces valid non-zero stats without loading any file from `benchmarks/raw/veo_*.json`.
4. **Continuous Test Suite**: All 100+ pytest tests and vitest tests pass non-interactively.
