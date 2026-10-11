# Video-only accuracy work queue

Session constraint: local CPU/GPU only; no remote GPU. See `docs/video-only-session.md` for commands, evidence, and GitHub status.

## Active

- [T-010] Audit ball detection and select a soccer-specific model. Local full-clip tiling completed: candidate-bearing frames 138→118 Veo, 25→109 Marc, 0→6 BCC (200 frames/domain); CPU 1.78–2.00 fps. Counts are not accuracy. Independent audit scorer and fixed unannotated sample plan are ready. See `docs/ball-detection-session-20261010.md`.

## Queued

- [T-005] Integrate automatic dynamic calibration with confidence; compare candidate models on pilot clips.
- [T-006] Implement synchronized temporal tracking/control transitions; report unknown and coverage instead of extrapolated totals.
- [T-007] Obtain additional Veo event exports; define split and locked audit samples for Marc/BCC.
- [T-008] Train/evaluate temporal shots and passing, then test cautious unlabeled adaptation.
- [T-011] Wire video-only mode to API/UI only after score/metric provenance is represented; current mode is experimental CLI with isolated DB.
- [T-012] Create PR from published `feat/video-only-local-pilot-review` after GitHub API authentication; exact command/body in `docs/video-only-pr.md`.

## Completed

- [T-000] Read project, inspect actual implementation, and reproduce four-match baseline: 8.82pt possession MAE / 10.03pt leave-one-match-out.
- [T-001] Explicit boundary with provenance validation, no reference/calibration/fixed-prior enrichment, preservation of manual content, and enriched-match rejection.
- [T-002] Separate inventory registry: four Veo, two Marc, seven BCC source pointers; local audit generated.
- [T-003] Dense hashed local Veo/Marc clips prepared; independent ffprobe confirms 200 frames, 10 fps, 20s. BCC archive segment recovered; resolution comparison documented in session log.
- [T-004] Separate Python 3.12 CPU inference environment, CPU-only PyTorch, YOLO11n checkpoint, locked runtime dependencies, and real local object detection pilots. No remote compute used.
- [T-009] Reviewed session-only branch published to GitHub via SSH; preserves prior unpublished local commits. PR draft saved; API authentication unavailable.
