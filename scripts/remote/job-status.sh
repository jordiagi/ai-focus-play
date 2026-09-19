#!/usr/bin/env bash
# One round trip, one JSON line. Pure read. Poll this; do not tail logs remotely.
#   scripts/remote/job-status.sh [job_id] [--tail N]
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

JOB="${1:-}"; [ "${JOB:0:2}" = "--" ] && JOB=""
TAIL=0; [ "${1:-}" = "--tail" ] && TAIL="${2:-20}"; [ "${2:-}" = "--tail" ] && TAIL="${3:-20}"

require_remote
rsh "JOB='$JOB' TAIL='$TAIL' RUNS='$REMOTE_RUNS' bash -s" <<'REMOTE'
python3 - <<PY
import json, os, sys
runs = os.environ["RUNS"]; job = os.environ.get("JOB") or ""
if not os.path.isdir(runs) or not os.listdir(runs):
    print(json.dumps({"state": "no-runs"})); sys.exit()
if not job:
    job = sorted(os.listdir(runs), key=lambda r: os.path.getmtime(os.path.join(runs, r)))[-1]
d = {"job_id": job}
sp = os.path.join(runs, job, "status.json")
if os.path.exists(sp):
    try: d.update(json.load(open(sp)))
    except Exception as e: d["status_error"] = str(e)
else:
    d["state"] = "no-status"
pid = os.path.join(runs, job, "pid")
if os.path.exists(pid):
    d["alive"] = os.path.exists("/proc/" + open(pid).read().strip())
print(json.dumps(d, separators=(",", ":")))
PY
if [ "${TAIL:-0}" -gt 0 ]; then
  tail -n "$TAIL" "$RUNS/$JOB/job.log" 2>/dev/null >&2 || true
fi
REMOTE
