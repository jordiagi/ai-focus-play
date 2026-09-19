#!/usr/bin/env bash
# Dispatch one work package to one fleet agent and record the attempt.
#   scripts/agent/run-package.sh <agent> <wp-id> <worktree-dir> [model]
# agent: codex | agy | opencode | claude
#
# Writes an append-only record per ATTEMPT (not per package, so rework is visible)
# to specs/opus2-hardening/ledger.jsonl. Timing and exit codes are captured here
# rather than relying on anyone to remember them.
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

AGENT="${1:?agent}"; WP="${2:?wp-id}"; DIR="${3:?worktree}"; MODEL="${4:-}"
# Find the spec in whichever specs/<set>/ directory holds it.
SPEC=""; for d in "$REPO_ROOT"/specs/*/; do
  [ -f "$d$WP.md" ] && { SPEC="$d$WP.md"; SPECDIR="$d"; break; }
done
[ -n "$SPEC" ] || die "no spec named $WP.md under $REPO_ROOT/specs/*/"
README="${SPECDIR}README.md"
LEDGER="${SPECDIR}ledger.jsonl"
[ -f "$SPEC" ] || die "no spec: $SPEC"
[ -d "$DIR" ]  || die "no worktree: $DIR"

CODEX=/home/ai/.local/share/mise/installs/codex/0.154.0/bin/codex
AGY=/home/ai/.local/share/mise/installs/antigravity-cli/1.2.5/agy
CLAUDE=/home/ai/.local/share/mise/installs/claude/2.1.273/claude
OPENCODE=/home/ai/.local/bin/opencode-headless

PROMPT="$(cat "$README")

---

$(cat "$SPEC")

---

You are working in the git worktree at $DIR. Edit ONLY the files listed under
'Files OWNED'. Run the acceptance command yourself and paste its REAL output.
Reply with the JSON reporting contract and nothing else."

LOG="${SPECDIR}${WP}.${AGENT}.log"
T0=$(date +%s)
set +e
case "$AGENT" in
  codex)    "$CODEX" exec --skip-git-repo-check -C "$DIR" -s workspace-write \
                     --color never "$PROMPT" >"$LOG" 2>&1 ;;
  agy)      ( cd "$DIR" && "$AGY" --output-format text --mode accept-edits --dangerously-skip-permissions \
                     --print-timeout 30m ${MODEL:+--model "$MODEL"} \
                     -p="$PROMPT" ) >"$LOG" 2>&1 ;;
  opencode) ( cd "$DIR" && "$OPENCODE" run --format json --auto \
                     -m "${MODEL:-unsloth/qwen3.8:latest}" "$PROMPT" ) >"$LOG" 2>&1 ;;
  claude)   ( cd "$DIR" && "$CLAUDE" -p --output-format json --permission-mode acceptEdits \
                     --model "${MODEL:-sonnet}" "$PROMPT" ) >"$LOG" 2>&1 ;;
  *) die "unknown agent $AGENT" ;;
esac
RC=$?
set -e
T1=$(date +%s)

cd "$DIR"
BASE=$(git merge-base HEAD main 2>/dev/null || echo main)
CHANGED=$(git diff --name-only "$BASE" 2>/dev/null | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')
DIFFLINES=$(git diff --numstat "$BASE" 2>/dev/null | awk '{a+=$1;d+=$2} END{print (a+d)+0}')
cd "$REPO_ROOT"

python3 - "$WP" "$AGENT" "${MODEL:-default}" "$RC" "$((T1-T0))" "$CHANGED" "$DIFFLINES" \
         "$(sha256sum "$SPEC" | cut -c1-16)" "$LEDGER" <<'PY'
import json, sys, datetime
wp, agent, model, rc, secs, changed, difflines, specsha, ledger = sys.argv[1:10]
rec = {"package": wp, "agent": agent, "model": model,
       "dispatched_at": datetime.datetime.now().isoformat(timespec="seconds"),
       "wall_seconds": int(secs), "exit_code": int(rc),
       "files_changed": json.loads(changed), "diff_lines": int(difflines),
       "spec_sha": specsha,
       "verified": None, "defects_found": [], "orchestrator_minutes": None}
with open(ledger, "a") as f:
    f.write(json.dumps(rec) + "\n")
PY

result "dispatch=$WP agent=$AGENT rc=$RC wall_s=$((T1-T0)) diff_lines=$DIFFLINES log=$LOG"
