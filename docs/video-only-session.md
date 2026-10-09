# Video-only implementation session — 2026-10-09

## Resume here

Read root `AGENTS.md`, `docs/video-only-plan.md`, and `TASKS.md`. This session is local-compute-only. User authorized GitHub and agent orchestration. Do not use the historical remote GPU scripts.

## Completed work and limits

- `MatchPipeline(..., mode="video_only")` is an experimental artifact-ingestion boundary, **not a complete raw-video event engine**. No references, acta, Veo calibration, shared fallback artifacts, score files or fixed-prior geometry. Unverified stats stay unavailable, teams unknown, positions null.
- Explicit prediction artifacts require a producer-attested video-only manifest and source SHA256. This is not independent proof of upstream isolation. Missing/partial artifacts and enriched/scored match records are rejected before writes. Manual highlights and lineups are preserved. CLI requires explicit isolated `AIFP_DB_PATH`; upload/API/UI integration is deferred, including nullable/provenanced score handling.
- `benchmarks/video_only_matches.json` is an **inventory**, never an inference input or replacement for the historical scorer registry. It lists four Veo, two Marc and seven BCC sources, with provisional whole-match roles. Private archive URLs are kept in gitignored `backend/.local/artifacts/video-only-pilot/source-pointers.json` and sibling BCC project docs.
- Three local tools inventory inputs, prepare hashed clips, and run CPU people/ball candidates. Detector requires an existing checkpoint, verifies clip hash and COCO class mappings, and checks decoded frame counts; outputs no team labels, geometry, events or analytics.
- Local platform: aarch64 Apple M1, eight CPU cores, no GPU exposed. Isolated runtime: `backend/.local/inference-venv`, Python 3.12.14, torch 2.14.1+cpu, ultralytics 8.4.174. Exact installed versions: `scripts/requirements-local-inference.lock.txt`.
- Model downloaded from official Ultralytics GitHub release `v8.3.0/yolo11n.pt` to `backend/.local/models/yolo11n.pt`, SHA256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
- Initial generic dependency installation pulled unwanted CUDA wheels; stopped it and explicitly installed CPU-only torch/torchvision pins. No GPU or remote compute was used. Downloads/cache are local, mostly `/tmp/aifp-uv-cache`.
- BCC recovery: first download produced a 360p segment. HD retry with system yt-dlp 2025.12.08 failed HTTP 403. Installing yt-dlp 2026.8.19 + EJS in the isolated runtime and using Node recovered the same 900–920s segment at 1080p. All source media remain gitignored. BCC local segment timestamps start at zero; archive offset is recorded separately and is not match-clock annotation.

## Local artifacts

All paths below are relative to `backend/.local/artifacts/video-only-pilot/`:

- `input-audit.json`: regenerated inventory with metadata/cadence and guidance availability.
- `skyline-900/`, `marc-horta-900/`: source-video 900–920s clips, 1280×720, 10fps, 200 frames; `pilot_manifest.json` and independent `clip-validation.json`.
- `skyline-900-detections/`, `marc-horta-900-detections/`: people/ball candidates and runtime/hash manifests.
- `bcc-source/bcc-northwest-900-hd-v2.mp4`: recovered 1080p archive segment; entire original recording was not downloaded.
- `bcc-northwest-hd-segment/` and `bcc-northwest-hd-segment-detections/`: comparable 10fps pilot and detections, with local clock 0–20s (archive 900–920s).
- Earlier 360p BCC directories are retained for provenance, not selected as the comparable pilot.

Portable summaries (no video or event labels): `docs/video-only-pilot-evidence.json`. Historical baseline output `/tmp/ai-focus-play-review-parity.json` is regenerable with the legacy scorer; its predictions are not genuinely unguided raw-video inference.

## Delegation ownership

- `video_boundary`: runner and new video-only unit tests; isolated boundary and regression checks.
- `local_audit`: input inventory/audit tests, then offline pilot preparation script/tests.
- Root: proposal/handoff/task documents, registry, integration review, independent validation, actual local pilots, GitHub workflow.

## Validation and observed result

- Four-match historical baseline rerun: possession MAE 8.82pt; LOMO 10.03pt; pass-share 7.38pt; shots 4.38. Derived pass totals excluded from accuracy claims.
- Independent final focused integration suite: **82 passed**.
- Full backend suite: `timeout 120 backend/.venv/bin/python -m pytest backend/tests -q -o faulthandler_timeout=45` → **192 passed**, two dependency deprecation warnings, 23.05s.
- The original sandbox run stalled at Starlette TestClient's AnyIO portal startup. A timeout/fault-handler reproduction confirmed the wait; unrestricted local rerun passed. The stalled run was interrupted. This was not an application test failure.
- Independent ffprobe checks on Veo/Marc: 20s, 10fps, 200 frames each. Object candidates: Skyline 3230 people, ball on21/200frames, 21.01s CPU prediction/decode (9.52fps); Marc 2799 people, ball on2/200frames, 19.16s (10.44fps). Counts are **not precision/recall**; no verified event accuracy improvement is claimed.
- HD BCC pilot also has 200 frames, 1280×720 at 10fps: 3085 person candidates, **0 ball candidates**, 28.23s CPU decode/prediction (7.08fps). Visually inspected first frame shows active play. This makes small-ball visibility a concrete development concern across recording types.
- Clean remote-base archive review: focused boundary/audit/preparation+legacy tests **41 passed, 1 skipped**; detector tests **15 passed**. Full clean-archive suite: **160 passed, 1 skipped, 7 failed**; the same seven missing-media/detection failures reproduce with unmodified origin code. No private media is being published to satisfy them.
- `git diff --check` passes. Media, weights, runtime and detailed candidate artifacts are excluded from Git.

## Reproduction commands

```bash
# Backend validation and local input audit
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python scripts/local/audit-video-inputs.py --registry benchmarks/video_only_matches.json --out /tmp/aifp-input-audit.json

# Rebuild a separate inference runtime if needed (local execution only)
uv venv --python 3.12 backend/.local/inference-venv
uv pip sync --python backend/.local/inference-venv/bin/python --torch-backend cpu -r scripts/requirements-local-inference.lock.txt

# Always choose NEW output directories; no overwrites
backend/.venv/bin/python scripts/local/prepare-video-pilot.py --video '/home/ai/Downloads/2026 09 20 Horta vs Turo Peira 26LEG1J01.mp4' --start 900 --duration 20 --fps 10 --out /tmp/aifp-marc-new
YOLO_CONFIG_DIR=/tmp/aifp-yolo MPLCONFIGDIR=/tmp/aifp-mpl backend/.local/inference-venv/bin/python scripts/local/detect-video-pilot.py --pilot /tmp/aifp-marc-new --weights backend/.local/models/yolo11n.pt --out /tmp/aifp-marc-detections-new

# BCC archive recovery: get BCC_VIDEO_URL from local sibling videos.md, never commit it
backend/.local/inference-venv/bin/yt-dlp --js-runtimes node --download-sections '*900-920' --force-keyframes-at-cuts -f 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]' -o '/tmp/aifp-bcc-source.%(ext)s' "$BCC_VIDEO_URL"
```

The isolated event-ingestion CLI additionally needs a freshly seeded pilot match in a separate database; it does not seed from reference data. Do not use the production DB or label historical predictions as video-only.

## GitHub workflow

- Remote `git@github.com:jordiagi/ai-focus-play.git`; SSH read access verified. `gh` has no API authentication, so issue/PR creation requires login later.
- Local implementation branch: `feat/video-only-local-pilot`, based on local main. Local main has four pre-existing unpublished commits, including a match-sheet export. These are outside this publication scope.
- Publish a separate review branch based on `origin/main` containing only this session's source/tests/docs changes, without videos, event labels, private source URLs, or previous unpublished match imports. See final publication entry below for actual branch/checks.

## Next work

1. **T-010:** compare higher-resolution/tiled/soccer-specific ball detection on these development clips, then score independently audited detections. The current general detector misses too much visual evidence to trust possession/pass inference.
2. **T-005/006:** dynamic video-derived calibration and temporal tracking/control transitions, with explicit unknown states and coverage.
3. **T-007/008:** gather more Veo event references, freeze whole-match/domain splits and independent Marc/BCC audit samples, then train temporal events and evaluate adaptation.
4. **T-011:** represent score/stat provenance before adding API/UI mode support.
