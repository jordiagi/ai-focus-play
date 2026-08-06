# Quickstart: Simplified Guided Video Workflow

## Purpose

Validate the redesigned workflow where users choose a video first, confirm a player from uncropped evidence, and generate reels only after confirmation.

## Prerequisites

- Backend virtual environment already created in `backend/.venv`.
- Frontend dependencies installed in `frontend/`.
- At least one soccer video available under the repository `video/` folder for local discovery.
- FFmpeg/FFprobe available locally for source metadata when validating real media.

## Local Run

Start the backend:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn src.app.main:app --host 127.0.0.1 --port 8001
```

Start the frontend:

```bash
cd frontend
npm run dev
```

Open the frontend development URL and follow the three-step workflow.

## Workflow Validation

1. Open the application and confirm the first visible decision is video source selection.
2. Confirm local videos under `video/` appear in a dropdown with readable display names.
3. Select a discovered local video and continue without entering match start or end times.
4. Restart source selection and enter a valid relative path under `video/`; confirm it is accepted.
5. Enter an absolute path or a path that escapes `video/`; confirm it is rejected with a clear message.
6. Enter a YouTube link; confirm the UI accepts the source or shows a clear availability error.
7. Enter a target jersey number and request player evidence.
8. Confirm the evidence panel shows uncropped frame context when candidate evidence exists.
9. Reject at least one candidate and confirm extraction remains blocked.
10. Confirm one candidate and verify identity cues are recorded or marked as not visible.
11. Request short, medium, and target-marker reel outputs after player confirmation.

## Automated Validation Targets

Backend:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/unit backend/tests/contract backend/tests/integration
backend/.venv/bin/python -m compileall backend/src backend/tests
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

## Manual Validation Required

Manual review remains required for player identity because the application cannot prove the target player is correct without human visual confirmation. Record:

- Whether the jersey number was visible in evidence.
- Whether jersey/team color matched the target player.
- Whether body shape or cleat details were visible.
- Whether rejected candidates stayed blocked from extraction.
- Whether generated reels focused on the confirmed player.

## Operator Notes

- The `video/` folder is the only accepted root for local source discovery and relative paths.
- Display name means the readable source label shown to the user, not necessarily the full filename or path.
- The standard workflow should not expose required manual match-window fields.
- When automatic match inference is uncertain, the UI should explain uncertainty and continue with review-safe behavior.

## Implementation Validation Results

- 2026-05-11: Backend unit, contract, and integration tests passed with 31 tests.
- 2026-05-11: Frontend workflow tests passed with 7 tests.
- 2026-05-11: Backend compile validation and frontend production build passed.
- Manual player identity review remains required with a real video before declaring visual accuracy complete.
