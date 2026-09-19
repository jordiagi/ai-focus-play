#!/usr/bin/env bash
# Ship the match video to gpu-box. Resumable, atomic, content-addressed.
# ~21 min cold at 2.8 MB/s; instant when the remote copy already matches.
# tmpfs means a container restart loses it - this script is how you get it back.
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

require_remote
[ -f "$LOCAL_VIDEO" ] || die "local video not found: $LOCAL_VIDEO"

LOCAL_BYTES=$(stat -c%s "$LOCAL_VIDEO")

# sha256 of 3.5 GB costs ~20s, so cache it keyed by size+mtime.
CACHE="$SCRIPTS_DIR/.video.sha256"
KEY="$LOCAL_BYTES:$(stat -c%Y "$LOCAL_VIDEO")"
if [ -f "$CACHE" ] && [ "$(head -1 "$CACHE")" = "$KEY" ]; then
  LOCAL_SHA=$(sed -n 2p "$CACHE")
else
  log "hashing local video (~20s, cached afterwards)"
  LOCAL_SHA=$(sha256sum "$LOCAL_VIDEO" | cut -d' ' -f1)
  printf '%s\n%s\n' "$KEY" "$LOCAL_SHA" > "$CACHE"
fi

# One round trip for remote state.
read -r R_FULL R_PART < <(rsh "stat -c%s '$REMOTE_VIDEO' 2>/dev/null || echo 0; \
                               stat -c%s '$REMOTE_VIDEO.part' 2>/dev/null || echo 0" | paste -sd' ')

if [ "$R_FULL" = "$LOCAL_BYTES" ]; then
  R_SHA=$(rsh "cat '${REMOTE_VIDEO%.mp4}.sha256' 2>/dev/null || sha256sum '$REMOTE_VIDEO' | cut -d' ' -f1")
  if [ "$R_SHA" = "$LOCAL_SHA" ]; then
    result "video=cached bytes=$LOCAL_BYTES sha=${LOCAL_SHA:0:16}"
    exit "$EX_CACHED"
  fi
  log "remote size matches but sha differs - re-sending from scratch"
  rsh "rm -f '$REMOTE_VIDEO' '$REMOTE_VIDEO.part'"
  R_PART=0
fi

rsh "mkdir -p '$(dirname "$REMOTE_VIDEO")'"

if [ "${R_PART:-0}" -gt 0 ] && [ "$R_PART" -lt "$LOCAL_BYTES" ]; then
  log "resuming at $R_PART / $LOCAL_BYTES bytes ($(( R_PART*100/LOCAL_BYTES ))%)"
  # iflag=skip_bytes makes the offset exact, not a block multiple.
  dd if="$LOCAL_VIDEO" bs=1M iflag=skip_bytes skip="$R_PART" status=none \
    | rsh "cat >> '$REMOTE_VIDEO.part'"
else
  log "sending $LOCAL_BYTES bytes (~$(( LOCAL_BYTES/1024/1024/168 )) min at 2.8 MB/s)"
  rsh "rm -f '$REMOTE_VIDEO.part'"
  dd if="$LOCAL_VIDEO" bs=1M status=none | rsh "cat > '$REMOTE_VIDEO.part'"
fi

# Verify BEFORE the atomic rename: a bad file must never take the real name.
R_SHA=$(rsh "sha256sum '$REMOTE_VIDEO.part' | cut -d' ' -f1")
[ "$R_SHA" = "$LOCAL_SHA" ] || die "sha mismatch after transfer (got $R_SHA want $LOCAL_SHA)" "$EX_VERIFY"

rsh "mv '$REMOTE_VIDEO.part' '$REMOTE_VIDEO'; printf '%s\n' '$LOCAL_SHA' > '${REMOTE_VIDEO%.mp4}.sha256'"
result "video=sent bytes=$LOCAL_BYTES sha=${LOCAL_SHA:0:16}"
