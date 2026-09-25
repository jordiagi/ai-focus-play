#!/usr/bin/env bash
# Launch Fairfax Union full-match GPU pipeline on gpu-box.
# Runs 3 GPU jobs in parallel across the 4 H100 NVLs:
#   GPU 0: player detection (600 evenly-spaced in-play frames)
#   GPU 1: ball detection (tiled, 2 fps across both halves)
#   GPU 2: camera registration (SIFT feature matching)
# GPU 3 left free for Ollama/other workloads (good-neighbour policy).
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

require_remote

VIDEO="$REMOTE_VIDEO"
CODE="$REMOTE_ROOT/code"
RUN_ID="fairfax-full-$(date +%Y%m%d-%H%M%S)"
RUN="$REMOTE_RUNS/$RUN_ID"

# Fairfax Union period timings (from Veo API ground truth)
P1_START=241.0
P1_END=2806.0
P2_START=3433.0
P2_END=5843.0

log "launching Fairfax Union full-match pipeline: $RUN_ID"
log "video=$VIDEO periods=[$P1_START-$P1_END, $P2_START-$P2_END]"

# Create run directory structure
rsh "mkdir -p '$RUN'/{players,ball,registration,colour}/out"

# --- Job 1: Player detection (GPU 0) ---
log "[GPU 0] starting player detection (600 samples from in-play time)"
rsh "$(remote_env)
cd '$CODE'
nohup '$REMOTE_VENV/bin/python' backend/src/services/pipeline/gpu_job/detect_players.py \
  --video '$VIDEO' \
  --out '$RUN/players/out/players_ko.json' \
  --run-dir '$RUN/players' \
  --n 600 \
  --imgsz 1536 \
  --conf 0.25 \
  --batch 16 \
  --device 0 \
  --frames-dir /workspace/aifp/frames/fairfax_players \
  --p1 $P1_START $P1_END \
  --p2 $P2_START $P2_END \
  > '$RUN/players/job.log' 2>&1 &
echo \$! > '$RUN/players/pid'
echo started-pid=\$(cat '$RUN/players/pid')" </dev/null

# --- Job 2: Ball detection (GPU 1) ---
log "[GPU 1] starting ball detection (tiled 3x2 @ 2fps, both halves)"
rsh "$(remote_env)
cd '$CODE'
nohup '$REMOTE_VENV/bin/python' backend/src/services/pipeline/gpu_job/detect_ball.py \
  --video '$VIDEO' \
  --out '$RUN/ball/out/ball_candidates.json' \
  --run-dir '$RUN/ball' \
  --fps 2.0 \
  --conf 0.05 \
  --tile-imgsz 640 \
  --nx 3 --ny 2 \
  --overlap 0.15 \
  --topk 5 \
  --batch 48 \
  --device 1 \
  --frames-dir /workspace/aifp/frames/fairfax_ball \
  --p1 $P1_START $P1_END \
  --p2 $P2_START $P2_END \
  > '$RUN/ball/job.log' 2>&1 &
echo \$! > '$RUN/ball/pid'
echo started-pid=\$(cat '$RUN/ball/pid')" </dev/null

# --- Job 3: Camera registration (GPU 2, CPU-heavy but uses GPU for SIFT if available) ---
log "[GPU 2] starting camera registration (SIFT feature matching)"
rsh "$(remote_env)
cd '$CODE'
nohup '$REMOTE_VENV/bin/python' backend/src/services/pipeline/gpu_job/measure_registration.py \
  --video '$VIDEO' \
  --out '$RUN/registration/out/registration.json' \
  --t0 $P1_START --t1 $P2_END \
  --step 120 \
  --scale 0.5 \
  --frames-dir /workspace/aifp/frames/fairfax_reg \
  > '$RUN/registration/job.log' 2>&1 &
echo \$! > '$RUN/registration/pid'
echo started-pid=\$(cat '$RUN/registration/pid')" </dev/null

log "all 3 jobs launched — run_id=$RUN_ID"
log "poll with: bash scripts/remote/job-status.sh $RUN_ID"

result "launched=3 run_id=$RUN_ID gpu0=players gpu1=ball gpu2=registration"
