# Shared helpers for scripts/. Source this, never execute it.
# The ONLY file that reads config.env. Everything else gets values from here.
#
# Exit-code contract (the API - agents branch on the code, not on prose):
#   0  done
#   10 cached / no-op
#   20 remote unreachable
#   30 verification failed
#   1  usage or unexpected error

set -euo pipefail

EX_OK=0; EX_CACHED=10; EX_UNREACHABLE=20; EX_VERIFY=30; EX_ERR=1

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$_LIB_DIR")"

set -a
. "$SCRIPTS_DIR/config.env"
[ -f "$SCRIPTS_DIR/config.local.env" ] && . "$SCRIPTS_DIR/config.local.env"
set +a

# Scripts are quiet by default; log() goes to stderr so stdout stays parseable.
log()  { printf '%s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit "${2:-$EX_ERR}"; }

# The last line of every script. Machine-readable, one line.
result() { printf 'RESULT: %s\n' "$*"; }

# Remote shell / copy. Word-splitting of SSH_OPTS is intentional.
# shellcheck disable=SC2086
rsh() { ssh $SSH_OPTS "$GPU_HOST" "$@"; }
# shellcheck disable=SC2086
rcp() { scp $SSH_OPTS -q "$@"; }

require_remote() {
  rsh true 2>/dev/null || die "cannot reach $GPU_HOST" "$EX_UNREACHABLE"
}

# Remote env preamble: every remote command needs these, and TMPDIR must point
# into tmpfs or temp files silently leak onto the persistent overlay.
remote_env() {
  cat <<'RENV'
export TMPDIR=/workspace/aifp/tmp MPLCONFIGDIR=/workspace/aifp/tmp
export UV_CACHE_DIR=/opt/uv-cache UV_PYTHON_INSTALL_DIR=/opt/uv-python
export TORCH_HOME=/opt/models/torch HF_HOME=/opt/models/hf
export YOLO_CONFIG_DIR=/opt/models/ultralytics
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PATH=/opt/uv:$PATH
RENV
}
