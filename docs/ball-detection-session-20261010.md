# Ball detection continuation — 2026-10-10

## Authorization and ownership

User requested continuing with **Claude Code agents to orchestrate the job and agy as needed**. Local CPU inference only; no remote GPU/SSH compute. Code agents may use their normal model APIs; no video or private labels may be uploaded to them.

- Claude Code coordinator: new `scripts/local/detect-ball-tiles.py`, `backend/tests/unit/test_ball_tiles.py`, and `docs/ball-tiles-design.md`; delegates implementation/review via custom agent definitions. No git operations or real-video runs authorized to those agents.
- agy: independent read-only code/design review, no modifications or inference.
- Codex/root: audit scorer/tests, actual experiments, validation, evidence, handoff and GitHub publication.

Prompts, custom agent definitions, results and stderr are saved under gitignored `backend/.local/agent-jobs/20261010/`. Claude invoked in print mode with scoped ownership instructions and allowed tools; no `--bare` (that disables existing OAuth auth). agy print prompt uses attached `-p=...`, plan mode, and a 180-second deadline. First detached agy launch did not survive its tool session; restarted as an awaited foreground process. Neither invocation performs soccer inference remotely.

## Frozen experiment contract

- Reuse the same three 20-second clips and YOLO11n checkpoint from the previous session. No reference event labels enter inference.
- Compare generic full-frame 1280 baseline against 3×2 overlapping tiles at 640 with confidence 0.25; inspect bounded first 20 frames before running full 200 frames. Tile coverage includes the whole image, avoiding a label-informed or camera-specific pitch crop.
- Report candidate counts/presence, duplicate suppression, actual coverage, runtime and hash provenance. These are not precision/recall.
- Keep private manual audits separate from model inputs. `scripts/local/score-ball-audit.py` performs one-to-one matching on saved candidate centers at a frozen 6-pixel tolerance. Audit schema: same `clip_sha256`, `frames` with source-video `t`, status `visible` plus `[x,y]` center, `not_visible` for a verified negative, or `uncertain`/`occluded` to exclude. Freeze tolerance before reviewing predictions; record labeler and coordinate resolution in private audit metadata.
- The scorer's synthetic tests do not establish actual video accuracy. Real audits remain private and must distinguish missed detections from invisible/off-screen balls.

## References inspected

Sliced inference is a candidate method for small objects, not evidence that it works on these matches: [SAHI paper](https://arxiv.org/abs/2202.06934), [official Ultralytics guide](https://docs.ultralytics.com/guides/sahi-tiled-inference). Existing project `gpu_job/detect_ball.py` has reusable tiling/NMS logic but is a historical remote job with reference period defaults; do not run it for this session.

## Progress

- Existing baseline: ball candidates on 138/200 Veo frames, 25/200 Marc, 0/200 BCC at full-frame 1280; ~4.6fps local CPU.
- Evaluation-only audit scorer added; targeted tests pass. Does not import any detector or feed annotations into inference.
- Claude Code completed successfully (session `9fa56a7c-a43c-47d1-be7f-800f291ee846`), delegating separate implementation and review agents. Its 88 fake-runtime tests pass; review fixes include same-shape bounded batching, integrity checks, malformed manifest handling, and staged writes. Root reviewed integration and ran actual inference.
- agy completed an independent read-only review. Its suggestions include independent audits, confidence sweeps and soccer-specific detection. Its ball-size and throughput estimates were speculative; measured runtime below takes precedence. No suggested accuracy gate has been achieved.
- Added `--max-width` to clip preparation (default remains 1280); independently verified native BCC pilot: 1920×1080, 200 frames at 10 fps. Native-resolution smoke produced zero candidates, so larger source dimensions alone did not solve detection.

## Smoke results (first 20 frames only)

| Clip | Full-frame 1280 candidate-bearing frames | Tiled 640 candidate-bearing frames | Tiled candidates after NMS | Tiled CPU fps |
| :-- | --: | --: | --: | --: |
| Veo Skyline | 14/20 | 12/20 | 16 | 1.78 |
| Marc Horta | 0/20 | 4/20 | 4 | 1.88 |
| BCC 720p | 0/20 | 1/20 | 1 | 1.88 |
| BCC native 1080p | No same-clip baseline | 0/20 | 0 | 1.88 |

The first three comparisons use identical prepared clip hashes and the same frame window. The native pilot has a different clip hash and is a separate input-resolution experiment. Partial manifests honestly report 20/200 coverage and do not pass whole-clip integrity. More candidate-bearing frames can reflect false positives; fewer can reflect misses. No independent audit is available yet, so precision/recall and event accuracy remain unknown.

## Commands and artifact locations

Run from repository root. The inference interpreter is the existing gitignored CPU environment, not the backend test interpreter.

```bash
# Native BCC preparation; use a new output directory on reruns.
backend/.venv/bin/python scripts/local/prepare-video-pilot.py \
  --video backend/.local/artifacts/video-only-pilot/bcc-source/bcc-northwest-900-hd-v2.mp4 \
  --start 0 --duration 20 --fps 10 --max-width 1920 \
  --out backend/.local/artifacts/video-only-pilot/bcc-native-20261010

# Full frozen tiled experiment (remove no inputs and overwrite no artifacts).
for pilot_name in skyline-900 marc-horta-900 bcc-northwest-hd-segment; do
  YOLO_CONFIG_DIR=backend/.local/yolo-config MPLCONFIGDIR=backend/.local/matplotlib \
  backend/.local/inference-venv/bin/python scripts/local/detect-ball-tiles.py \
    --pilot "backend/.local/artifacts/video-only-pilot/$pilot_name" \
    --weights backend/.local/models/yolo11n.pt \
    --out "backend/.local/artifacts/video-only-pilot/$pilot_name-tiles-full-20261010" || exit
done

backend/.venv/bin/python -m pytest backend/tests -q

# Evaluation only, after independent private annotation has been completed.
backend/.venv/bin/python scripts/local/score-ball-audit.py \
  --predictions SAVED_BALL_CANDIDATES.json --audit PRIVATE_AUDIT.json \
  --tolerance-px 6 --out NEW_SCORE_REPORT.json
```

Smoke outputs are `<pilot>-tiles-smoke-20261010/`; complete outputs are `<pilot>-tiles-full-20261010/`, all under `backend/.local/artifacts/video-only-pilot/`. Every output contains `detection_manifest.json` and `ball_candidates.json`. These media/candidate artifacts and verbose agent logs stay gitignored. Published evidence contains aggregate counts and hashes only.

## Next agent

1. Read this log and `docs/ball-tiles-design.md` alongside the standard handoff files. Do not rerun into existing output directories.
2. Independently annotate a fixed, representative frame sample for Veo, Marc and BCC, before viewing predictions. Keep annotations private, outside inference inputs; distinguish visible, verified absent, uncertain and occluded. Score saved baseline and tiled outputs with the same clip hash and frozen tolerance. Expand to other whole matches and camera setups before claiming generalization.
3. Select a ball-specific model or tile configuration using development audits; freeze the choice before evaluating held-out recordings. Current YOLO11n is a generic candidate generator.
4. Address synchronized tracking and dynamic geometry only when trustworthy observations and coverage support them. No label-guided match stats or pseudo-label accuracy claims.
5. Publish only session commits through `/tmp/aifp-github-review`, never the implementation branch containing earlier unpublished match imports. GitHub API authentication is unavailable; branch push via SSH is authorized.

## Validation and review

- Full local backend suite: **301 passed**, two existing dependency deprecation warnings, 25.44 seconds.
- Focused scorer/tiled/preparation suite: **114 passed**. Tiled tests use fake runtime; actual local smoke/full pilots provide the real-runtime check.
- Independent ffprobe confirms native BCC 1920×1080, 10 fps, 200 frames.
- Remaining detector risks: tile-border fragments can survive IoU-only NMS; top-k and NMS defaults are untuned; output schema differs from the baseline and needs an adapter before pipeline ingestion. Atomic staging has a narrow race if another process creates an empty destination directory during rename.
- Comparison is between full-frame `imgsz=1280` and full-frame plus 3×2 tiles at `imgsz=640`, both confidence 0.25 and the same checkpoint. Baseline includes person and ball classes; tiled inference requests ball only. Preprocessing/batch equivalence is not independently verified, so this is a candidate-method comparison, not a controlled proof isolating tiling alone.

Claude orchestration command (prompts restricted agent ownership and prohibited video/label uploads):

```bash
timeout 600 claude -p \
  --agents backend/.local/agent-jobs/20261010/claude-agents.json \
  --permission-mode acceptEdits --allowedTools Read Edit Write Bash Agent Glob Grep \
  --output-format json \
  < backend/.local/agent-jobs/20261010/claude-prompt.txt \
  > backend/.local/agent-jobs/20261010/claude-result.json \
  2> backend/.local/agent-jobs/20261010/claude-stderr.log
```

agy was invoked via an awaited Python subprocess with `['agy', '-p='+prompt, '--mode=plan', '--print-timeout=180s']`, timeout 200 seconds and file-backed stdout/stderr. Both CLIs exited 0. Normal agent model APIs were used for code/design work; all video processing ran locally on CPU.
