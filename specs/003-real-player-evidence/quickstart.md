# Quickstart: Real Player Evidence

## Prerequisites

- Backend virtual environment exists under `backend/.venv`.
- Frontend dependencies are installed under `frontend/node_modules`.
- FFmpeg and FFprobe are available on `PATH`.
- A real soccer video exists under the repository `video/` folder, such as `video/video.mp4`.

## Evidence Settings

The real evidence workflow writes small project-scoped artifacts under `AI_FOCUS_DATA_DIR/<project-id>/evidence/`.

- `AI_FOCUS_VIDEO_ROOT`: trusted local video folder, normally `video` from the repository root or `../video` when running from `backend/`.
- `AI_FOCUS_EVIDENCE_SAMPLE_COUNT`: number of initial real source-video evidence samples to extract for review.
- `AI_FOCUS_EVIDENCE_CLIP_SECONDS`: duration of each short evidence clip.

Troubleshooting:

- If evidence search fails with an FFmpeg message, confirm `ffmpeg` and `ffprobe` are on `PATH`.
- If no candidates appear for a local source, confirm the selected file is a readable MP4 under `video/`.
- If the UI shows `no_candidates` or `failed`, reel generation should stay locked; do not create placeholder candidates.

## Start The Backend

```bash
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn src.app.main:app --host 127.0.0.1 --port 8000
```

## Start The Frontend

```bash
cd frontend
npm run dev
```

Open the Vite URL and use the guided workflow.

## Manual Real-Evidence Workflow

1. Choose a local video from the Step 1 dropdown.
2. Continue to Step 2.
3. Enter jersey number `8`.
4. Click `Show player evidence`.
5. Confirm that the UI shows a processing/loading state before candidates appear.
6. Confirm that every candidate includes a real thumbnail or clip, a source timestamp, and visible cue information.
7. Reject at least one incorrect or insufficient candidate if available.
8. Confirm the intended player only after the evidence visually supports the decision.
9. Confirm that Step 3 unlocks only after that confirmation.
10. Generate the desired reel output and verify it remains linked to the confirmed player identity.

## Automated Validation

Run backend tests focused on evidence, confirmation, and export gating:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/unit backend/tests/contract backend/tests/integration
```

Run frontend tests:

```bash
cd frontend
npm test
```

Run the frontend production build:

```bash
cd frontend
npm run build
```

## Required Manual Checks

- Evidence candidates must never show placeholder gradient cards or fake image URIs.
- Every selectable candidate must include real media generated from the selected source video.
- No-result and failure states must keep reel generation blocked.
- Confirmed player identity must be traceable to supporting evidence samples.
- At least one real local video must be reviewed visually because automated tests cannot certify player identity accuracy.
