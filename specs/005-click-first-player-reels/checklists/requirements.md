# Requirements Traceability Checklist: Click-First Player Reels

Check each requirement against the implementation before final validation. Every row
needs evidence: a test path, an endpoint, or a manual-validation entry.

## Functional requirements

- [ ] FR-001 Click identifies the player; no flow requires a jersey number
      (evidence: `test_clicks_target_api.py`; SC-001 walk-through)
- [ ] FR-002 Click hit-testing runs on the backend against real detections
      (`test_click_service.py`)
- [ ] FR-003 Evidence strip: 8–12 real crops with timestamps, spread across the match;
      zero placeholder media (`test_candidates_api.py`; IdentityEvidenceStrip tests)
- [ ] FR-004 One-action confirm; per-appearance "Not them" persists as negative
      evidence across re-clustering (`test_embed_cluster_stage.py` user_removed case)
- [ ] FR-005 Extra positive clicks reinforce; pre-analysis clicks pin and auto-resolve
      (`test_detect_track_stage.py` pin case; manual pin scenario)
- [ ] FR-006 Jersey hint optional, ranks candidates, cross-checks in plain language,
      never blocks (`PUT /jersey-hint` contract test; ui-flow §2c/§2d copy)
- [ ] FR-007 Analysis auto-starts on source attach; jobs never block the API
      (`POST /source` contract test; `test_job_lifecycle.py`)
- [ ] FR-008 No hosted inference APIs anywhere (dependency review; grep for http calls
      in `src/ml/`)
- [ ] FR-009 Every long stage checkpoints and resumes without redoing completed stages
      (`test_job_lifecycle.py`; manual kill/resume)
- [ ] FR-010 Progress is real and derived from work done; jobs cancellable
      (`test_jobs_api.py`; minutes-watched in AnalysisProgressCard test)
- [ ] FR-011 Identities cluster tracklets; temporal overlap can never merge
      (`test_embed_cluster_stage.py` cannot-link case)
- [ ] FR-012 Bounded SAM 2 refinement on click-miss / gap-fill; never full-match
      (`test_sam2_refine_stage.py` window-bounds case)
- [ ] FR-013 Coverage segments: merged/padded/scored; timeline with preview and
      include/exclude (`test_timeline_service.py`; CoverageTimeline tests)
- [ ] FR-014 Reel generation blocked until confirmation, with normative copy
      (`test_timeline_exports_api.py` 409 case)
- [ ] FR-015 Reel renders included segments chronologically; marker follows real
      per-frame boxes (manual T068)
- [ ] FR-016 Reels traceable to identity + segments (`segment_ids_json` in outputs;
      `test_full_flow.py`)
- [ ] FR-017 SQLite replaces the JSON store entirely; `JsonDatabase` deleted
      (`test_db.py`; grep)
- [ ] FR-018 Three wizard steps with new labels; plain-language copy; no model names or
      bare confidence numbers in the UI (component tests; copy review)
- [ ] FR-019 Every failure message: what happened + data safe + one action
      (ui-flow copy table implemented verbatim)
- [ ] FR-020 Legacy heuristic CV, JSON store, stub/remote runners, review queue all
      deleted; no dangling references (T069 grep evidence)

## Operational requirements

- [ ] OR-001 `download_models` + `doctor` CLIs work as documented in quickstart
- [ ] OR-002 Default test suite passes in a venv without ML weights or torch
- [ ] OR-003 Structured events emitted for job/click/confirmation/export lifecycles
- [ ] OR-004 Manual validation executed and recorded in `manual-validation.md`

## Success criteria spot-checks

- [ ] SC-001 through SC-008 each have a recorded pass in `manual-validation.md` or a
      pointing test
