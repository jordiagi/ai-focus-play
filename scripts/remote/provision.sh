#!/usr/bin/env bash
# Bare NGC container -> working GPU env. Idempotent.
#   cold: ~5-8 min (torch download, over the BOX's fast link, not Tailscale)
#   warm after a tmpfs wipe: ~60-90s (caches live on the persistent overlay)
# Exits 10 + provision=cached when the requirements hash is already stamped.
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

require_remote

REQS_SHA=$(sha256sum "$GPU_REQS" | cut -c1-16)

# Fast path: already provisioned for exactly these requirements?
if rsh "test -f /opt/env/.provisioned-$REQS_SHA && test -x $REMOTE_VENV/bin/python" 2>/dev/null; then
  result "provision=cached reqs=$REQS_SHA"
  exit "$EX_CACHED"
fi

log "provisioning $GPU_HOST (reqs $REQS_SHA) - cold run downloads torch, be patient"

rsh "mkdir -p /opt/env" </dev/null
rcp "$GPU_REQS" "$GPU_HOST:/opt/env/requirements-gpu.txt"

OUT=$(rsh "TORCH_INDEX_URL='$TORCH_INDEX_URL' bash -s" \
        < "$SCRIPTS_DIR/remote/_provision.remote.sh" 2>&1) || {
  printf '%s\n' "$OUT" >&2
  die "provision failed (see output above)" "$EX_VERIFY"
}

printf '%s\n' "$OUT" | grep -E '^(OK|FAIL)' >&2 || true
TORCHLINE=$(printf '%s\n' "$OUT" | grep '^OK ' | head -1)
[ -n "$TORCHLINE" ] || die "provision produced no OK line" "$EX_VERIFY"

result "provision=done reqs=$REQS_SHA ${TORCHLINE#OK }"
