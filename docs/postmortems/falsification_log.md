# Falsification Log & Technical Post-Mortems

This document preserves the complete mathematical, empirical, and forensic records of all hypotheses, experiments, and approaches attempted in the `ai-focus-play` project that were falsified, failed pre-registered gates, or led to critical engineering discoveries.

---

## 1. Incident Log & Reproducibility Traps

### 2026-09-20 — Step 8's Published Figures Did Not Reproduce
- **Context**: `detect_out_of_play.py` was committed in `3a8d4a1` with reported numbers: Period 1 $n=51, \text{tp}=12, \text{F1}=0.296$; Period 2 $n=39, \text{tp}=14, \text{F1}=0.384$; combined $n=90, \text{tp}=26, \text{F1}=0.338$.
- **Discovery**: Re-running the script against `ball_track.json` gave 187 predictions and F1=0.319; Period 1 topped out at 0.265. The signature medians also shifted (267/0.13/42 vs. 196/0.20/35).
- **Root Cause**: `backend/.local/artifacts/` was gitignored, so artifacts were overwritten without recording the exact invocation command or parameters.
- **Remediation**:
  - Enforced Rule **B12**: Every detector script must record the exact `sys.argv` command in its output JSON document.
  - Step 8 restated under a formal protocol with an explicit prediction budget ($K=3$).
  - Added reproducibility checks before extending any pipeline step.

### 2026-09-19 — Worktree Symlink Destroyed `.venv`
- **Context**: `.venv` and `.local` symlinks were created inside worktrees for test execution.
- **Failure**: `.gitignore` contained trailing slashes (`backend/.venv/`), which matched directories but *not symlinks*. `git add -A` tracked the symlinks, replacing directories with self-referential links upon merge.
- **Remediation**:
  - Slashes removed from ignore patterns (`backend/.venv`, `backend/.local`).
  - Python environment rebuilt on 3.14.7. CV determinism signature verified byte-identical (`61075316940f2cb1`).

---

## 2. D-0: Camera Motion as Event Signal (FALSIFIED)

- **Hypothesis**: Out-of-play situations cause the camera to become static; camera velocity or pan stops during dead-ball intervals.
- **Script**: `backend/src/services/pipeline/gpu_job/camera/falsify_halftime.py`
- **Pre-Registered Kill-Test**: Must clearly recover the 795s halftime window and show static behavior during stoppages.

| Criterion | Target | Measured Result | Verdict |
| :--- | :--- | :--- | :--- |
| **C1** ROC AUC of camera speed | $\ge 0.80$ | **0.613** | **FAIL** |
| **C2** Median in-play speed vs. halftime | $\ge 2.0\times$ | **1.70** | **FAIL** |
| **C3** Halftime boundaries recovered | $\pm 30\text{s}$ | **0.7s / 2825s** | **FAIL** |

- **Root Cause**: Veo's virtual camera does not stop during stoppages or halftime. It continuously roams at ~10 px/s tracking players warming up or milling around on an empty pitch. A kickoff detector based on camera stillness scored **0/8**.
- **Crucial Metric Discovery (Chaining Drift)**: Integrating frame-to-frame registration ($dx$) across 185,003 frames drifted by **616 px median (1490 px max)** between identical kickoff views that were physically only 58 px apart—a **10.6x drift factor**. This proved that chained frame-to-frame tracking across match durations is structurally impossible.

---

## 3. D-A & G2: Metric Pitch Calibration (FAILED & STOPPED)

The goal was to map frame pixels to metric coordinates ($meters$ on a 105m×68m pitch) to enable 2D pitch radar and speed calculations.

### Attempt 1: SIFT + RANSAC Correspondence
- Using 46 frames across 600–6100s.
- While registration between overlapping frames was crisp (0.31–3.93 px round-trip error for inliers $\ge 100$), correspondence to pitch coordinates produced **median errors of 10–15m** and extreme outliers up to **1854m**.
- **Root Cause**: On grazing-angle amateur footage, generic SIFT features latch onto off-pitch structures (trees, tents, spectators, buildings, and adjacent pitches).

### Attempt 2: Learned Pitch-Keypoint Calibration (PnLCalib / SoccerNet)
- Pretrained deep pitch-calibration model (`/opt/PnLCalib`) evaluated against 355 Veo event frames.
- **Result**: Median error **88m (restarts) / 110m (open play)** on a 105m pitch. Essentially random.
- **Root Cause**: All existing academic models (PnLCalib, Broadtrack, NBJW) are trained on elevated broadcast TV cameras where the entire pitch or major thirds are clearly framed. On low amateur poles (~6.7m), action close-ups lack line landmarks.

### Attempt 3: Stitched Panorama + Line Map + Centre-Circle Anchor
- Built a 4414×1190 equirectangular rotating-camera panorama covering $125.4^\circ$ horizontal FOV.
- Composited frame line responses into a clean line evidence map showing the centre circle, halfway line, and penalty boxes.
- Anchored pose on the centre circle (fixed $R=9.15\text{m}$):
  - Solved camera height: **6.71m** (physically realistic pole height).
  - Ground normal: **$0.87^\circ$ off vertical**.
  - In-plane rotation: **168.6–171.1°**.
  - Centre-circle fit: **0.0 px median, 68% within 3 px**.
- **The Structural Failure**:
  - Despite the circle fitting with 0.0 px median error, the pitch outline (touchlines, goal lines) could not align (touchlines 24–39 px off, goal lines 31–51 px off).
  - Inverting 14,607 player foot points onto the fitted ground plane yielded a **105.8m × 104.5m square** (aspect ratio 1.01 instead of ~1.5:1).
  - **Verdict**: Near the horizon on a grazing-angle camera, a vertical shift of 2 pixels corresponds to 20+ meters. Metric calibration cannot be reliably solved on this geometry without explicit depth sensors or higher camera elevation. Work stopped; moved to D-B (pixel space).

---

## 4. D-B & Tier B: 2D Containment & Possession (FALSIFIED)

Tier B aimed to detect 241 events (54% of benchmark): `interception`, `tackle`, `dribble`, `loose`.

### The 15 fps Association Gate Failure (Step 18)
- **Pre-Registered Gate**: Model fitted on Period 1; Period 2 held-out balanced accuracy must exceed 0.55 and beat majority-class baseline.
- **GPU Cost**: 2,880 frames each of ball and player detection, 107s + 96s on H100 NVL.

| Route | Attribution Rate | Period 1 Acc | Period 2 Acc | Majority Baseline | Balanced Acc | Gate Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Last contact, 5 fps | 0.94 | 0.70 | 0.64 | 0.64 | — | FAIL |
| **Last contact, 15 fps** | **0.98** | 0.66 | **0.53** | 0.65 | 0.41 | **FAIL** |
| Strike frame, 5 fps | 0.58 | 0.71 | 0.45 | 0.60 | — | FAIL |
| **Strike frame, 15 fps** | 0.45 | 0.71 | **0.47** | 0.60 | 0.56 | **FAIL** |

- **Shirt-Color Separation Test over Attributed Boxes**:
  - Kits: White (Home) vs. Dark Navy (Away).
  - At throw-in moments (held ball), Own L med = 84 vs. Opp L med = 177 ($\text{AUC} \approx 0.88$).
  - Over open-play attributed boxes: Own L med = 118, Opp L med = 104 $\longrightarrow$ **$\text{AUC} = 0.503$** (even with large median box height of 86 px).
- **Physical Diagnosis**: 2D bounding boxes contain no depth. When a ball is kicked in the air across the pitch, it projects inside the 2D bounding boxes of multiple players who are 30 meters away in 3D depth. Increasing frame rate merely creates more accidental 2D overlaps. Without 3D depth or foot-level contact models, Tier B is structurally unfeasible.

### Ball-Track Coverage Paradox (B21)
- Attempted to boost ball track coverage by relaxing Viterbi parameters.
- **Result**: Raising track coverage from 0.586 to 0.802 **dropped macro-F1 from 0.348 to 0.252**.
- **Reason**: The OutOfPlay detector relied on the coverage *collapse* (the ball disappearing from view when kicked out of play). Increasing false-positive ball detections erased the boundary signal.

---

## 5. Complete Parity Spec: P1 (Shot) & P2 (Setpieces) (FALSIFIED)

Evaluated under `specs/complete-veo-parity/spec.md` with pre-registered gates committed in `070ba47`.

### P1 — `FootballShot` (25 events)
- **Cues**: Ball speed and direction toward the defending goal in `(xi, eta)` panorama space using B10's validated defend-end map.
- **Pre-Registered Requirements**:
  - S1: Period 2 F1 $\ge 0.25$
  - S2: Period 2 F1 $\ge 2.0\times$ matched-K chance baseline
  - S3: Period 2 F1 strictly greater than OutOfPlay-proxy control (relabeling OutOfPlay stoppage predictions as shots).
- **Measured Result**:
  - Period 2 F1: **0.120** (failed S1).
  - Chance ratio: $1.80\times$ chance (chance mean 0.067, failed S2).
  - OutOfPlay-proxy control: scored **0.149** $\longrightarrow$ **The control scored higher than the detector!**
- **Diagnosis**: The detector was firing on stoppages and clearances near the goal end, not actual shots.

### P2 — `FootballFreeKick` & `FootballFoul` (30 events)
- **Cues**: Stoppage where the ball remains *inside* the pitch region (complement of OutOfPlay), followed by a static restart.
- **Measured Result**:
  - `FootballFreeKick`: Period 2 F1 = **0.000** (0 of 10 matched). Chance mean = 0.016. Tied OOP proxy control at 0.000.
  - `FootballFoul`: Period 2 F1 = **0.143** (1 hit in 4 predictions). Ungated because referee whistle audio is missing from the footage.
- **Diagnosis**: Stoppages inside the pitch are dominated by throw-ins and out-of-play bounces that landed back inbounds. The absence of audio whistle cues prevents isolating foul infractions.

---

## 6. Audit Discoveries: Leaking Defaults & UI Fabrications

During the September 2026 audits, several subtle violations of the "Honesty Rule" were identified and eliminated:

1. **Pydantic Defaults Leakage (`d12`)**:
   - While producers were fixed in `c38d62f`, [match.py](file:///home/ai/Projects/ai-focus-play/backend/src/domain/models/match.py) had class-level dictionary literals in `AnalyticsData` that leaked into fresh instances. Solved via `Field(default_factory=...)` and validated by negative probe `d12`.
2. **Disconnected Frontend `unavailable` Map**:
   - The backend attached measured reasons to uncomputed stats, but [SidebarTabs.tsx](file:///home/ai/Projects/ai-focus-play/frontend/src/components/Sidebar/SidebarTabs.tsx) rendered `goals` directly, displaying **"3 Goal 0"** for a 3-3 match. Corrected by introducing [Unavailable.tsx](file:///home/ai/Projects/ai-focus-play/frontend/src/components/Sidebar/Unavailable.tsx) and rendering an em-dash (`—`) with tooltip explanations for all detection counts.
3. **Hardcoded UI Literals**:
   - [Header.tsx](file:///home/ai/Projects/ai-focus-play/frontend/src/components/Header.tsx) hardcoded `{views_count || 95} views` and `{date || 'Sep 13, 2026'}`.
   - [PlayerRoster](file:///home/ai/Projects/ai-focus-play/backend/src/domain/models/match.py) defaulted `minutes_played` to 90/25 mins without real measurements.
