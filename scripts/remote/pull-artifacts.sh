#!/usr/bin/env bash
# Bring results home. Small files only - the link is 2.8 MB/s.
# Refuses anything over 200 MB unless --allow-large: shipping frames or video
# across this relay is always a mistake.
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

JOB="${1:-}"; [ "${JOB:0:2}" = "--" ] && JOB=""
ALLOW_LARGE=0; for a in "$@"; do [ "$a" = "--allow-large" ] && ALLOW_LARGE=1; done
MAXB=$((200*1024*1024))

require_remote
[ -n "$JOB" ] || JOB=$(rsh "ls -t '$REMOTE_RUNS' 2>/dev/null | head -1")
[ -n "$JOB" ] || die "no runs on $GPU_HOST" "$EX_ERR"

SRC="$REMOTE_RUNS/$JOB/out"
rsh "test -d '$SRC'" || SRC="$REMOTE_OUT"
DEST="$LOCAL_ARTIFACTS/$JOB"; mkdir -p "$DEST"

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

result "pulled=$pulled cached=$cached skipped=$skipped job=$JOB dest=$DEST"
