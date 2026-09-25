#!/usr/bin/env bash
# Bring results home. Small files only - the link is 2.8 MB/s.
# Refuses anything over 200 MB unless --allow-large: shipping frames or video
# across this relay is always a mistake.
#
# Flags:
#   scripts/remote/pull-artifacts.sh [job_id] [--dest <path>] [--clean-remote] [--allow-large]
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

JOB=""
DEST_OVERRIDE=""
CLEAN_REMOTE=0
ALLOW_LARGE=0
MAXB=$((200*1024*1024))

while [ $# -gt 0 ]; do
  case "$1" in
    --dest)
      shift; DEST_OVERRIDE="${1:-}" ;;
    --clean-remote)
      CLEAN_REMOTE=1 ;;
    --allow-large)
      ALLOW_LARGE=1 ;;
    --*)
      log "unknown flag $1" ;;
    *)
      if [ -z "$JOB" ]; then JOB="$1"; fi ;;
  esac
  shift 2>/dev/null || break
done

require_remote
[ -n "$JOB" ] || JOB=$(rsh "ls -t '$REMOTE_RUNS' 2>/dev/null | head -1")
[ -n "$JOB" ] || die "no runs on $GPU_HOST" "$EX_ERR"

SRC="$REMOTE_RUNS/$JOB/out"
rsh "test -d '$SRC'" || SRC="$REMOTE_OUT"

if [ -n "$DEST_OVERRIDE" ]; then
  DEST="$DEST_OVERRIDE"
else
  DEST="$LOCAL_ARTIFACTS/$JOB"
fi
mkdir -p "$DEST"

LIST=$(rsh "cd '$SRC' 2>/dev/null && find . -type f -printf '%s %p\n'" || true)
[ -n "$LIST" ] || { result "pulled=0 cached=0 job=$JOB note=no-artifacts"; exit "$EX_CACHED"; }

pulled=0; cached=0; skipped=0
while read -r size path; do
  [ -z "$size" ] && continue
  rel="${path#./}"
  if [ "$size" -gt "$MAXB" ] && [ "$ALLOW_LARGE" -eq 0 ]; then
    log "SKIP $rel ($(( size/1024/1024 )) MB > 200 MB; use --allow-large)"
    skipped=$((skipped+1)); continue
  fi
  mkdir -p "$DEST/$(dirname "$rel")"
  if [ -f "$DEST/$rel" ] && [ "$(stat -c%s "$DEST/$rel")" = "$size" ]; then
    cached=$((cached+1)); continue
  fi
  rcp "$GPU_HOST:$SRC/$rel" "$DEST/$rel" && pulled=$((pulled+1))
done <<< "$LIST"

if [ "$CLEAN_REMOTE" -eq 1 ] && [ "$((pulled + cached))" -gt 0 ]; then
  log "clearing remote run artifacts and frames for $JOB to free space..."
  rsh "rm -rf '$REMOTE_RUNS/$JOB' /workspace/aifp/frames/'$JOB'* 2>/dev/null || true"
  log "remote cleanup for $JOB completed"
fi

result "pulled=$pulled cached=$cached skipped=$skipped job=$JOB dest=$DEST clean_remote=$CLEAN_REMOTE"
