# ai-focus-play agent handoff

Read `docs/video-only-plan.md`, `docs/video-only-session.md`, `TASKS.md`, and the newest entry in `STATE.md` before continuing accuracy work. Older status documents contain conflicting historical claims; executable evidence takes precedence.

## Current authorization and constraints

- Goal: accurate analysis on new Marc/BCC recordings without per-video event labels guiding inference. Existing Veo labels may supervise training and score saved predictions.
- This session uses **local compute only; no remote GPU, SSH compute, or remote job scripts**. Do not silently restore older gpu-box workflows. No local GPU is currently exposed; use CPU pilots.
- User explicitly authorized GitHub use and orchestration with other agents as needed. Assign disjoint files, review integrations, and record commands/results here. Do not publish videos or labels.
- Markdown proposal and progress logs are requested. Keep enough information for any agent to resume, including limitations, failed checks, output paths, and next commands.

## Engineering rules

- `ml` remains the historical enriched pipeline. `video_only` is a separate, conservative boundary; it is not yet a trained video inference engine.
- `video_only` is experimental CLI-only; require a separate `AIFP_DB_PATH` (for example `/tmp/aifp-pilot/veo.db`). Upload/API/UI do not advertise it yet; default match scores are not video measurements.
- No reference stats/events, official match sheets, reference period timings, external Veo calibration, or shared match fallback in video-only inference. Unverified geometry and metrics stay unavailable.
- Prediction artifact provenance is producer-attested, not proof that upstream training/inference was isolated. Never relabel historical artifacts as blind predictions.
- Use fresh pilot match IDs to avoid overwriting existing enriched match records. Preserve human-authored content.
- Keep evaluation labels outside inference inputs. Split evaluation by whole match and recording setup, and report coverage alongside accuracy.
- Run targeted regression tests. Tests use isolated temporary database/media via `backend/tests/conftest.py`.

## Commands

```bash
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python scripts/local/audit-video-inputs.py --registry benchmarks/video_only_matches.json --out /tmp/aifp-video-input-audit.json
backend/.venv/bin/python -m backend.src.services.pipeline.pipeline_runner --help
```

GitHub repository: `jordiagi/ai-focus-play`. Check authentication before issue/PR operations; never print credentials.
