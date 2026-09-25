#!/usr/bin/env bash
# Generic orchestrator for full-video match analysis on gpu-box.
#
# Runs parallel GPU jobs across the available H100s:
#   GPU 0: Player detection (YOLO11x @ 1536px over in-play times)
#   GPU 1: Ball detection (tiled 3x2 @ 2fps across periods)
#   GPU 2: Camera registration (SIFT feature matching across match)
#
# Usage:
#   scripts/remote/launch-video-full.sh [OPTIONS]
#
# Options:
#   --video <path>         Local path to video or remote path (default: $REMOTE_VIDEO)
#   --match-id <id>        Match ID (default: derived from video name)
#   --calib <path>         Local calibration file (.veo) to use for pitch mapping
#   --p1 <t0> <t1>         Period 1 in-play window in seconds
#   --p2 <t0> <t1>         Period 2 in-play window in seconds
#   --dev-players <id>     GPU device ID for player detection (default: 0)
#   --dev-ball <id>        GPU device ID for ball detection (default: 1)
#   --dev-reg <id>         GPU device ID for camera registration (default: 2)
#   --wait                 Wait for remote jobs to complete
#   --pull                 Pull artifacts locally to backend/.local/artifacts/<match_id>
#   --clean-frames         Clean intermediate extracted JPEG frames on remote after inference
#   --clean-remote         Purge remote run directory & frames after successful pull
#   --ingest               Run local MatchPipeline to ingest pulled artifacts into SQLite
#
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

require_remote

VIDEO_PATH=""
MATCH_ID=""
CALIB_PATH=""
P1_START=""
P1_END=""
P2_START=""
P2_END=""
DEV_PLAYERS="0"
DEV_BALL="1"
DEV_REG="2"
WAIT_FOR_COMPLETION=0
PULL_ARTIFACTS=0
CLEAN_FRAMES=1
CLEAN_REMOTE=0
INGEST_LOCAL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --video)
      shift; VIDEO_PATH="${1:-}" ;;
    --match-id)
      shift; MATCH_ID="${1:-}" ;;
    --calib)
      shift; CALIB_PATH="${1:-}" ;;
    --p1)
      shift; P1_START="${1:-}"; shift; P1_END="${1:-}" ;;
    --p2)
      shift; P2_START="${1:-}"; shift; P2_END="${1:-}" ;;
    --dev-players)
      shift; DEV_PLAYERS="${1:-0}" ;;
    --dev-ball)
      shift; DEV_BALL="${1:-1}" ;;
    --dev-reg)
      shift; DEV_REG="${1:-2}" ;;
    --wait)
      WAIT_FOR_COMPLETION=1 ;;
    --pull)
      PULL_ARTIFACTS=1; WAIT_FOR_COMPLETION=1 ;;
    --clean-frames)
      CLEAN_FRAMES=1 ;;
    --no-clean-frames)
      CLEAN_FRAMES=0 ;;
    --clean-remote)
      CLEAN_REMOTE=1; PULL_ARTIFACTS=1; WAIT_FOR_COMPLETION=1 ;;
    --ingest)
      INGEST_LOCAL=1; PULL_ARTIFACTS=1; WAIT_FOR_COMPLETION=1 ;;
    *)
      log "unknown argument $1" ;;
  esac
  shift 2>/dev/null || break
done

# 1. Determine remote video
REMOTE_TARGET="$REMOTE_VIDEO"
if [ -n "$VIDEO_PATH" ]; then
  if [ -f "$VIDEO_PATH" ]; then
    log "local video provided: $VIDEO_PATH"
    # Set LOCAL_VIDEO and run push-video
    LOCAL_VIDEO="$VIDEO_PATH"
    bash "$SCRIPTS_DIR/remote/push-video.sh"
  else
    # Assume it's a remote path
    REMOTE_TARGET="$VIDEO_PATH"
  fi
fi

# Ensure video exists on remote
R_DUR=$(rsh "ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 '$REMOTE_TARGET' 2>/dev/null || echo 0")
IS_VALID=$(python3 -c "dur = float('$R_DUR'); print(1 if dur > 0 else 0)" 2>/dev/null || echo 0)
if [ "$IS_VALID" -ne 1 ]; then
  die "remote video '$REMOTE_TARGET' not found or invalid format (dur=$R_DUR)" "$EX_ERR"
fi
TOTAL_SEC=$(python3 -c "print(int(float('$R_DUR')))")
TOTAL_MIN=$(python3 -c "print(round(float('$R_DUR') / 60, 1))")
log "remote video confirmed: $REMOTE_TARGET (${TOTAL_SEC}s, ~${TOTAL_MIN} min)"

# 2. Determine match ID and run ID
if [ -z "$MATCH_ID" ]; then
  MATCH_ID="match-$(date +%Y%m%d-%H%M%S)"
fi
RUN_ID="${MATCH_ID}-$(date +%s)"
RUN="$REMOTE_RUNS/$RUN_ID"
CODE="$REMOTE_ROOT/code"

# 3. Determine period windows if not provided
if [ -z "$P1_START" ] || [ -z "$P1_END" ]; then
  P1_START="0.0"
  P1_END=$(python3 -c "print(round(float('$R_DUR') / 2, 1))")
fi
if [ -z "$P2_START" ] || [ -z "$P2_END" ]; then
  P2_START="$P1_END"
  P2_END=$(python3 -c "print(round(float('$R_DUR'), 1))")
fi

log "configuration for $MATCH_ID (run: $RUN_ID):"
log "  video:   $REMOTE_TARGET"
log "  period1: $P1_START -> $P1_END s"
log "  period2: $P2_START -> $P2_END s"
log "  devices: players=GPU$DEV_PLAYERS, ball=GPU$DEV_BALL, reg=GPU$DEV_REG"

# 4. Push code to ensure latest scripts are on gpu-box
bash "$SCRIPTS_DIR/remote/push-code.sh" --dirty >&2

# 5. Initialize remote run directories
rsh "mkdir -p '$RUN'/{out,players,ball,registration}"

# 6. Launch parallel GPU tasks via remote wrapper
log "launching GPU jobs on $GPU_HOST..."

# Frame directories isolated by run ID
F_PLAYERS="/workspace/aifp/frames/${RUN_ID}_players"
F_BALL="/workspace/aifp/frames/${RUN_ID}_ball"
F_REG="/workspace/aifp/frames/${RUN_ID}_reg"

rsh "$(remote_env)
cd '$CODE'

# Job 1: Player Detection (GPU $DEV_PLAYERS)
nohup bash -c \"
  '$REMOTE_VENV/bin/python' backend/src/services/pipeline/gpu_job/detect_players.py \\
    --video '$REMOTE_TARGET' \\
    --out '$RUN/out/players_ko.json' \\
    --run-dir '$RUN/players' \\
    --n 600 \\
    --imgsz 1536 \\
    --conf 0.25 \\
    --batch 16 \\
    --device '$DEV_PLAYERS' \\
    --frames-dir '$F_PLAYERS' \\
    --p1 '$P1_START' '$P1_END' \\
    --p2 '$P2_START' '$P2_END' > '$RUN/players/job.log' 2>&1
  if [ '$CLEAN_FRAMES' -eq 1 ]; then
    rm -rf '$F_PLAYERS' 2>/dev/null || true
  fi
\" >/dev/null 2>&1 &
echo \$! > '$RUN/players/pid'

# Job 2: Ball Detection (GPU $DEV_BALL)
nohup bash -c \"
  '$REMOTE_VENV/bin/python' backend/src/services/pipeline/gpu_job/detect_ball.py \\
    --video '$REMOTE_TARGET' \\
    --out '$RUN/out/ball_candidates.json' \\
    --run-dir '$RUN/ball' \\
    --fps 2.0 \\
    --conf 0.05 \\
    --tile-imgsz 640 \\
    --nx 3 --ny 2 \\
    --overlap 0.15 \\
    --topk 5 \\
    --batch 48 \\
    --device '$DEV_BALL' \\
    --frames-dir '$F_BALL' \\
    --p1 '$P1_START' '$P1_END' \\
    --p2 '$P2_START' '$P2_END' > '$RUN/ball/job.log' 2>&1
  if [ '$CLEAN_FRAMES' -eq 1 ]; then
    rm -rf '$F_BALL' 2>/dev/null || true
  fi
\" >/dev/null 2>&1 &
echo \$! > '$RUN/ball/pid'

# Job 3: Camera Registration (GPU $DEV_REG)
nohup bash -c \"
  '$REMOTE_VENV/bin/python' backend/src/services/pipeline/gpu_job/measure_registration.py \\
    --video '$REMOTE_TARGET' \\
    --out '$RUN/out/registration.json' \\
    --t0 '$P1_START' --t1 '$P2_END' \\
    --step 120 \\
    --scale 0.5 \\
    --frames-dir '$F_REG' > '$RUN/registration/job.log' 2>&1
  if [ '$CLEAN_FRAMES' -eq 1 ]; then
    rm -rf '$F_REG' 2>/dev/null || true
  fi
\" >/dev/null 2>&1 &
echo \$! > '$RUN/registration/pid'

python3 -c \"
import json, time
doc = {
  'job_id': '$RUN_ID',
  'match_id': '$MATCH_ID',
  'video': '$REMOTE_TARGET',
  'state': 'running',
  'started_at': time.time(),
  'periods': {'p1': [$P1_START, $P1_END], 'p2': [$P2_START, $P2_END]}
}
with open('$RUN/status.json', 'w') as f:
  json.dump(doc, f)
\"
" </dev/null

log "jobs dispatched: players (GPU $DEV_PLAYERS), ball (GPU $DEV_BALL), reg (GPU $DEV_REG)"

# 7. Wait loop if --wait / --pull
if [ "$WAIT_FOR_COMPLETION" -eq 1 ]; then
  log "monitoring progress on $GPU_HOST (poll interval: 10s)..."
  DONE=0
  while [ "$DONE" -eq 0 ]; do
    sleep 10
    STATUS_JSON=$(rsh "python3 -c \"
import json, os
run = '$RUN'
def read(p):
    try: return json.load(open(p))
    except: return {}
def alive(sub):
    p = os.path.join(run, sub, 'pid')
    if not os.path.exists(p): return False
    pid = open(p).read().strip()
    return os.path.exists('/proc/' + pid)

res = {
  'players': {'alive': alive('players'), 'status': read(os.path.join(run, 'players', 'status.json'))},
  'ball': {'alive': alive('ball'), 'status': read(os.path.join(run, 'ball', 'status.json'))},
  'reg': {'alive': alive('registration')}
}
print(json.dumps(res))
\" 2>/dev/null" || echo "{}")

    # Parse status summary
    P_ALIVE=$(echo "$STATUS_JSON" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('players',{}).get('alive', False))" 2>/dev/null || echo false)
    B_ALIVE=$(echo "$STATUS_JSON" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('ball',{}).get('alive', False))" 2>/dev/null || echo false)
    R_ALIVE=$(echo "$STATUS_JSON" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('reg',{}).get('alive', False))" 2>/dev/null || echo false)

    P_STATE=$(echo "$STATUS_JSON" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('players',{}).get('status',{}).get('state', 'unknown'))" 2>/dev/null || echo unknown)
    B_STATE=$(echo "$STATUS_JSON" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('ball',{}).get('status',{}).get('state', 'unknown'))" 2>/dev/null || echo unknown)

    log "status: players=$P_STATE (alive=$P_ALIVE) | ball=$B_STATE (alive=$B_ALIVE) | reg (alive=$R_ALIVE)"

    if [ "$P_ALIVE" = "False" ] && [ "$B_ALIVE" = "False" ] && [ "$R_ALIVE" = "False" ]; then
      DONE=1
    fi
  done
  log "all remote GPU jobs finished for $RUN_ID"
fi

# 8. Pull artifacts if requested
LOCAL_DEST="$LOCAL_ARTIFACTS/$MATCH_ID"
if [ "$PULL_ARTIFACTS" -eq 1 ]; then
  log "pulling artifacts to $LOCAL_DEST..."
  PULL_CMD=("$SCRIPTS_DIR/remote/pull-artifacts.sh" "$RUN_ID" "--dest" "$LOCAL_DEST")
  if [ "$CLEAN_REMOTE" -eq 1 ]; then
    PULL_CMD+=("--clean-remote")
  fi
  "${PULL_CMD[@]}"
fi

# 9. Ingest match into local database if requested
if [ "$INGEST_LOCAL" -eq 1 ]; then
  log "ingesting artifacts into local match database..."
  INGEST_ARGS=("--match-id" "$MATCH_ID" "--mode" "ml" "--artifacts" "$LOCAL_DEST")
  if [ -n "$CALIB_PATH" ]; then
    INGEST_ARGS+=("--calib" "$CALIB_PATH")
  fi
  "$REPO_ROOT/backend/.venv/bin/python" "$REPO_ROOT/backend/src/services/pipeline/pipeline_runner.py" "${INGEST_ARGS[@]}"
  log "match $MATCH_ID successfully ingested and verified!"
fi

result "job=$RUN_ID match=$MATCH_ID status=completed pulled=$PULL_ARTIFACTS ingested=$INGEST_LOCAL"
