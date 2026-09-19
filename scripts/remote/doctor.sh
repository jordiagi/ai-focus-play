#!/usr/bin/env bash
# One round trip. One JSON line on stdout. Pure read - changes nothing.
# Run this FIRST, before dispatching any work, and after any container restart.
. "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

require_remote

rsh 'bash -s' <<'REMOTE'
python3 - <<'PY'
import json, os, shutil, subprocess

def sh(cmd, default=""):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=20).stdout.strip() or default
    except Exception:
        return default

d = {}
d["hostname"] = sh("hostname")

# GPUs: report free VRAM so the caller can honour the good-neighbour budget.
gpus = []
raw = sh("nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv,noheader,nounits")
for line in raw.splitlines():
    parts = [p.strip() for p in line.split(",")]
    if len(parts) == 3:
        gpus.append({"i": int(parts[0]), "used_gb": round(int(parts[1])/1024, 1),
                     "free_gb": round(int(parts[2])/1024, 1)})
d["gpus"] = gpus
d["gpu_count"] = len(gpus)
d["gpu_min_free_gb"] = min([g["free_gb"] for g in gpus], default=0)
d["neighbour_max_used_gb"] = max([g["used_gb"] for g in gpus], default=0)

# tmpfs
d["tmpfs_mounted"] = os.path.ismount("/workspace")
if d["tmpfs_mounted"]:
    st = shutil.disk_usage("/workspace")
    d["tmpfs_total_gb"] = round(st.total/1e9, 1)
    d["tmpfs_free_gb"] = round(st.free/1e9, 1)

# toolchain
d["uv"] = bool(shutil.which("uv") or os.path.exists("/opt/uv/uv"))
d["ffmpeg"] = bool(shutil.which("ffmpeg"))
venv = "/workspace/aifp/.venv/bin/python"
d["venv"] = os.path.exists(venv)
d["venv_py"] = sh(f"{venv} -V") if d["venv"] else None
d["torch"] = sh(
    f"{venv} -c 'import torch;print(torch.__version__,torch.cuda.is_available(),"
    f"torch.cuda.device_count())'", None) if d["venv"] else None

# the video
v = "/workspace/aifp/media/video.mp4"
d["video"] = os.path.exists(v)
d["video_bytes"] = os.path.getsize(v) if d["video"] else 0
d["video_partial"] = os.path.exists(v + ".part")
shafile = "/workspace/aifp/media/video.sha256"
d["video_sha256"] = open(shafile).read().strip()[:16] if os.path.exists(shafile) else None

# most recent job
runs = "/workspace/aifp/runs"
last = None
if os.path.isdir(runs):
    ids = sorted(os.listdir(runs), key=lambda r: os.path.getmtime(os.path.join(runs, r)))
    if ids:
        sp = os.path.join(runs, ids[-1], "status.json")
        last = {"job_id": ids[-1]}
        if os.path.exists(sp):
            try:
                last.update(json.load(open(sp)))
            except Exception as e:
                last["status_error"] = str(e)
d["last_job"] = last

print(json.dumps(d, separators=(",", ":")))
PY
REMOTE
