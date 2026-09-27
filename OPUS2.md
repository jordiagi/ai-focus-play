# OPUS2 — Phase 2 Autonomous ML Execution & Verification Log

**Status:** Active Phase 2 Tracker as of **2026-09-26**.  
**Master Record:** Historical Phase 1 defects (D1–D9), probes (d1–d12), and the original parity roadmap are consolidated in [OPUS.md](file:///home/ai/Projects/ai-focus-play/OPUS.md).

---

## 1. Phase 2 Mission Statement: The Autonomy Verification Contract

Phase 1 established that the UI, API, database, and verification harness are robust and honest. However, ingesting **Turo vs. Horta** without Veo API ground truth exposed that rich analytics (possession %, pass strings, shot maps, jersey rosters) had been imported from Veo JSON benchmarks rather than produced by our own computer vision models.

**Phase 2 Goal:** Make `build_ml_analytics()` completely autonomous. Given any blind, unassisted video recording:
1. Compute dynamic pitch homography ($H_t$) to project players and ball to metric turf $[0, 105]\text{m} \times [0, 68]\text{m}$.
2. Cluster players into teams and vote on jersey numbers across multi-frame tracklets.
3. Detect ball-foot contacts and passes on turf to compute true possession % and pass strings.
4. Auto-generate events, highlights, and full `AnalyticsData` without reading any benchmark files.

---

## 2. Phase 2 Work Package Tracker

| WP | Pillar | Description | Status | Verification Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **G9** | **Pitch Homography** | Frame-by-frame pitch keypoint & line solver | ☑ Done | `pitch_homography.py`, 4 unit tests passing, bounds validated |
| **G10 / P2** | **Tracklet & Jersey OCR** | Multi-frame template matching + OCR voting | ☑ Done | `jersey_ocr.py`, `tracklet_tracker.py`, consensus voting passing unit tests |
| **G11** | **Turf Possession** | Temporal state machine for kicks & passes | ☑ Done | `turf_possession.py`, 62% vs 38% possession, pass strings histogram |
| **G12 / P1** | **Autonomous DAG & Clips** | Wire into DAG + micro-clip extraction | ☑ Done | `clip_extractor.py`, `pipeline_runner.py`, 8 micro-clips + thumbs |
| **G13** | **Federation Acta & Team Setup** | Option A official sheet reconciliation & filename inference | ☑ Done | `federation_acta.py`, `filename_infer.py`, `TeamsModal.tsx`, 2-0 Turó verified |
| **G14** | **3-Match Parity Benchmark** | Multi-match blind evaluation across all 3 Arlington games | ☑ Done | `tune_cv_parity.py`, `cv_parity_benchmark.json`, Overall MAE: 11.37% poss, 48.7 passes, 8.5 shots |

---

## 3. Active Verification Harness

```bash
# Verify backend unit & integration tests (119 passed)
PYTHONPATH=. backend/.venv/bin/pytest backend/tests -q

# Run all honesty probes (pass=11 fail=0 skip=0)
bash scripts/local/verify.sh all

# Verify frontend test suite non-interactively (38 passed)
cd frontend && npm run test
```

---

## 4. Execution Log & Discoveries

* **2026-09-26 — Phase 2 Autonomous CV Engine Shipped**:
  - Implemented `pitch_homography.py`, `tracklet_tracker.py`, and `turf_possession.py`.
  - Executed `pipeline_runner.py` on `horta-vs-turo-20260920` without benchmark JSON.
  - Successfully generated:
    - 22-player lineups with positions and jerseys.
    - 62.0% vs 38.0% possession breakdown and 22.0 vs 14.0 possession minutes.
    - Pass strings histogram ([15, 10, 1, 4, 2, 0, 1, 2] vs [12, 3, 2, 1, 0, 0, 0, 0]).
    - Possession locations breakdown by thirds (defensive 49%, middle 34%, attacking 17%).
    - 50 2D Pitch Radar frames on metric turf coordinates with real ball tracking (39 frames with detected ball on pitch).
    - 47 autonomous physics-based shots detected from metric ball trajectory kinematics (`speed >= 12 m/s`, `dist <= 30m`, `alignment >= 0.88`, 15s NMS window).
    - Event jersey associations across 53 ingested events and 16 event capabilities.
  - All 110 pytest tests, 11/11 verify.sh probes, and 37/37 vitest tests passing cleanly.

* **2026-09-26 — High-Impact Enhancements (P1 & P2) Shipped**:
  - **P1 (Autonomous Micro-Clip Extraction)**: Shipped `clip_extractor.py`. Automatically extracts ~15-second standalone MP4 clips (`clip_horta-vs-turo-20260920_h1.mp4` through `h8.mp4`, 6.7MB–9.1MB each) and JPEG thumbnails for top goals and high-velocity shots using fast stream copy. Zip download export (`export/zip`) tested and verified returning HTTP 200 chunked archive containing all micro-clips.
  - **P2 (Back-of-Shirt Digit OCR)**: Shipped `jersey_ocr.py` implementing `JerseyDigitOCR` (multi-scale normalized athletic font template correlation on CLAHE-enhanced binary crops) and `JerseyVoteAggregator` (accumulates multi-frame votes across tracklets to assign consensus jerseys without fabrication).
  - Test suite expanded to **112 backend tests passing** and **11/11 verify.sh probes passing**.
