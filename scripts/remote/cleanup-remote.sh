#!/usr/bin/env bash
# Cleanup remote space on gpu-box /workspace tmpfs.
# Usage:
#   scripts/remote/cleanup-remote.sh [--frames] [--runs] [--video] [--all]
#
# Defaults to --frames if no options specified.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

require_remote

CLEAN_FRAMES=0
CLEAN_RUNS=0
CLEAN_VIDEO=0

for arg in "$@"; do
  case "$arg" in
    --frames) CLEAN_FRAMES=1 ;;
    --runs)   CLEAN_RUNS=1 ;;
    --video)  CLEAN_VIDEO=1 ;;
    --all)    CLEAN_FRAMES=1; CLEAN_RUNS=1; CLEAN_VIDEO=1 ;;
    *) log "unknown argument: $arg" ;;
  esac
done

if [ "$CLEAN_FRAMES" -eq 0 ] && [ "$CLEAN_RUNS" -eq 0 ] && [ "$CLEAN_VIDEO" -eq 0 ]; then
  CLEAN_FRAMES=1
fi

log "evaluating remote disk space on $GPU_HOST before cleanup..."
BEFORE=$(rsh "df -h /workspace | awk 'NR==2 {print \$3 \" used of \" \$2 \" (\" \$5 \")\"}'")
log "current /workspace usage: $BEFORE"

if [ "$CLEAN_FRAMES" -eq 1 ]; then
  log "clearing temporary extracted frame caches in /workspace/aifp/frames/..."
  rsh "rm -rf /workspace/aifp/frames/* 2>/dev/null || true"
fi

if [ "$CLEAN_RUNS" -eq 1 ]; then
  log "clearing old run directories in /workspace/aifp/runs/..."
  rsh "rm -rf /workspace/aifp/runs/* 2>/dev/null || true"
fi

if [ "$CLEAN_VIDEO" -eq 1 ]; then
  log "clearing uploaded video and checksum in /workspace/aifp/media/..."
  rsh "rm -f /workspace/aifp/media/video.mp4 /workspace/aifp/media/video.sha256 2>/dev/null || true"
fi

# Clean tmpfs temp directory
rsh "rm -rf /workspace/aifp/tmp/* 2>/dev/null || true"

AFTER=$(rsh "df -h /workspace | awk 'NR==2 {print \$3 \" used of \" \$2 \" (\" \$5 \")\"}'")
log "cleanup complete. /workspace usage: $AFTER"

result "cleanup=done before='$BEFORE' after='$AFTER'"
