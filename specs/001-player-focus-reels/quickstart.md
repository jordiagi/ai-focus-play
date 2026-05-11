# Quickstart: Player Focus Reels

## Purpose

Run the project locally for UI and backend development, then switch heavy analysis to the remote Ubuntu GPU host when validating end-to-end flows against longer match footage.

## Prerequisites

- Python 3.11 available locally
- Node.js 20+ available locally
- FFmpeg installed locally and on the remote host
- SSH access to `yehj10@ai-cluster.hhmi.org`
- A sample soccer match video placed in the local `video/` directory for development

## Local Development Setup

1. Create a Python virtual environment in `backend/.venv`.
2. Install backend dependencies into that virtual environment.
3. Install frontend dependencies in `frontend/`.
4. Configure environment variables for:
   - local artifact workspace
   - metadata database location
   - remote runner enablement
   - remote SSH host and workspace path
   - cleanup retention window
5. Start the backend API locally.
6. Start the frontend locally.

## Suggested Verification Flow

1. Create a new analysis project from a local file in `video/`.
2. Confirm the match window excludes warmup and postgame footage.
3. Enter target-player cues such as team color and jersey number.
4. Run analysis in local mode against a short clip to verify end-to-end plumbing.
5. Switch to remote mode for a full-match run.
6. Review ambiguous detections until the project reaches the verification threshold.
7. Request both short and medium exports, with and without player marker overlays.
8. Confirm exported files are downloadable 1080p MP4 outputs.
9. Confirm temporary artifacts are removed from the remote workspace after completion or cancellation.

## Manual Accuracy Validation

- Prepare a small labeled sample of frames or clips where the target player is known.
- Compare accepted detections against that labeled sample.
- Record whether each verified reel keeps the correct player in highlighted moments.
- Treat any project below the 90% threshold as blocked from verified export.

## Observability Expectations

- Each project should expose status across intake, analysis, review, export, and cleanup.
- Each failed job should provide a user-visible reason and an operator-facing diagnostic record.
- Remote execution logs should be retrievable without requiring persistent storage of source media.

## Deployment Notes

- The remote GPU host is execution infrastructure, not long-term storage.
- Remote jobs should stage inputs into a job-scoped workspace and remove that workspace after completion, cancellation, or expiry.
- Local development can use the Mac GPU or CPU path for smaller validation clips, but full-match validation should prefer the remote host.
