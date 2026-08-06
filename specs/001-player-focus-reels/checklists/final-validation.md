# Final Validation Checklist

- [x] Run backend syntax validation with `python3 -m compileall backend/src backend/tests`.
- [x] Run backend unit and integration tests inside the backend virtual environment.
- [x] Run frontend tests after installing frontend dependencies.
- [x] Validate the local backend smoke flow from project creation through export generation.
- [x] Validate remote runner command generation and cleanup behavior through unit-level service coverage and runner construction.
- [x] Confirm observability hooks exist for intake, analysis, review, export, and cleanup.

## Validation Notes

- Backend pytest passed locally with `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/unit backend/tests/contract backend/tests/integration` after adding API root coverage, source duration probing coverage, synthetic MP4 render coverage, API-level end-to-end local workflow validation, and remote runner preflight/cleanup coverage.
- Backend pytest result: 19 tests passed.
- Frontend tests passed with `npm test` from `frontend/`.
- Frontend test result: 3 test files passed, 3 tests passed.
- Frontend production build passed with `npm run build` from `frontend/`.
- Backend `/` now returns API status, docs path, and the frontend dev URL instead of FastAPI's default 404 response.
- Local dev server ports used for this validation: backend `http://127.0.0.1:8001/`, frontend `http://127.0.0.1:5173/`.
- Local sample media found at `video/video.mp4`: H.264, 1920x1080, about 5913 seconds, about 3.1 GB. The `video/` directory is ignored so real match media is not committed.
- `ffprobe` successfully read the real sample duration as `5912.773400` seconds, and source intake now records probed duration when a local source exists.
- Export generation now has a real MP4 render path for local sources when `ffmpeg` is available, including 1080p scaling and the `target_marker` overlay mode.
- Automated local end-to-end validation creates a project, attaches a synthetic local video, sets the match window and target player, runs local analysis, approves the ambiguous detection, and renders a `1920x1080` MP4 export.
- Remote runner command generation now prepends `AI_FOCUS_REMOTE_PATH_PREFIX`, checks for `python3`, `ffmpeg`, and `ffprobe`, creates a job-scoped `/tmp` workspace with `mktemp -d`, and installs an `EXIT INT TERM` cleanup trap before running the analysis command.
- Remote SSH readiness check reached `ai-cluster`, reported two `NVIDIA H100 NVL` GPUs with `95830 MiB` each, and verified an empty `/tmp/ai-focus-play-check.*` workspace can be created and removed immediately.
- Remote `~/ai-remote/.venv` exists, `~/ai-remote/bin/ffmpeg` and `~/ai-remote/bin/ffprobe` resolve through the configured path prefix, and `~/ai-remote/tmp` had no leftover entries after setup validation.
- A `RemoteRunner`-generated SSH smoke command executed successfully through the configured path prefix and left no `/tmp/ai-focus-play.job.*` directories behind.
- Remote media validation rendered a 4-second smoke clip derived from `video/video.mp4` inside `~/ai-remote/tmp/remote-media-validation`, converting `640x360` input to `1920x1080` MP4 output with the target marker overlay; the remote validation folder was removed afterward and `~/ai-remote/tmp` was empty.
- Manual review and manual export checklists remain intentionally incomplete until labeled target-player review and visual MP4/overlay validation are performed on actual match footage.
- Task `T049` is complete for automated/local/remote plumbing validation. Labeled player-accuracy review and visual export approval remain tracked by the manual review/export checklists.
