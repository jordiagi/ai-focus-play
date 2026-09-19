#!/usr/bin/env bash
# Ship the pipeline source to gpu-box. Tiny (~300 KB) - seconds even on the relay.
#   default: git archive HEAD (committed state)
#   --dirty: include uncommitted work (git ls-files -co --exclude-standard)
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

require_remote
cd "$REPO_ROOT"

PATHS=(backend/src benchmarks scripts)
rsh "mkdir -p '$REMOTE_ROOT/code'"

if [ "${1:-}" = "--dirty" ]; then
  git ls-files -co --exclude-standard -- "${PATHS[@]}" \
    | tar -czf - -T - 2>/dev/null \
    | rsh "tar -xzf - -C '$REMOTE_ROOT/code'"
  SRC=dirty
else
  git archive HEAD -- "${PATHS[@]}" 2>/dev/null \
    | rsh "tar -xf - -C '$REMOTE_ROOT/code'" \
    || die "git archive failed - is anything committed under ${PATHS[*]}?"
  SRC=HEAD
fi

SHA=$(git rev-parse --short HEAD 2>/dev/null || echo none)
rsh "printf '%s\n' '$SHA' > '$REMOTE_ROOT/code/CODE_SHA'"
N=$(rsh "find '$REMOTE_ROOT/code' -type f | wc -l")
result "code=sent src=$SRC sha=$SHA files=$N"
