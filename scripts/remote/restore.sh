#!/usr/bin/env bash
# THE one-shot after a container restart wiped the 64 GB tmpfs.
# Everything under it is idempotent, so a no-op re-run is cheap (~5 s).
#   warm (caches on /opt survive): ~90 s + video transfer
#   the video is the only expensive part: ~21 min, and only if it is gone
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

T0=$(date +%s)
require_remote

for step in provision push-code push-video; do
  out=$(bash "$SCRIPTS_DIR/remote/$step.sh" 2>/dev/null); rc=$?
  case $rc in
    0|10) log "$step: ${out#RESULT: }" ;;
    *)    printf '%s\n' "$out" >&2; die "$step failed (rc=$rc)" "$rc" ;;
  esac
  eval "RES_${step//-/_}='${out#RESULT: }'"
done

result "restore=done elapsed_s=$(( $(date +%s) - T0 ))"
