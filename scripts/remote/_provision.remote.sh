#!/usr/bin/env bash
# Runs ON gpu-box. Piped in by provision.sh - not invoked directly.
# Idempotent: every step is guarded, a warm re-run is ~60-90s.
set -euo pipefail

REQS=/opt/env/requirements-gpu.txt
STAMP="/opt/env/.provisioned-$(sha256sum "$REQS" | cut -c1-16)"
VENV=/workspace/aifp/.venv

export TMPDIR=/workspace/aifp/tmp MPLCONFIGDIR=/workspace/aifp/tmp
export UV_CACHE_DIR=/opt/uv-cache UV_PYTHON_INSTALL_DIR=/opt/uv-python
export TORCH_HOME=/opt/models/torch HF_HOME=/opt/models/hf
export YOLO_CONFIG_DIR=/opt/models/ultralytics
export PATH=/opt/uv:$PATH
export DEBIAN_FRONTEND=noninteractive

# 1. tmpfs + tree (tmpfs is wiped by a restart, so always re-assert)
mkdir -p /workspace
mountpoint -q /workspace || mount -t tmpfs -o size=64g,mode=0755 tmpfs /workspace
mkdir -p /workspace/aifp/{media,tmp,frames,work/{queue,claim,done},chunks,out/qa,logs,runs}
mkdir -p /opt/{uv,uv-cache,uv-python,apt-archives,models/{weights,torch,hf,ultralytics},env}

# 2. apt: ffmpeg, plus the GL libs ultralytics' opencv-python needs on bare NGC
#    (without libgl1 you get ImportError: libGL.so.1 at `import ultralytics`)
if ! command -v ffmpeg >/dev/null || ! ldconfig -p | grep -q libGL.so.1; then
  apt-get -o Dir::Cache::archives=/opt/apt-archives -qq update
  apt-get -o Dir::Cache::archives=/opt/apt-archives -qq install -y \
          --no-install-recommends ffmpeg libgl1 libglib2.0-0 >/dev/null
fi

# 3. uv on the overlay, so a tmpfs wipe does not remove it
[ -x /opt/uv/uv ] || curl -LsSf https://astral.sh/uv/install.sh \
  | env UV_INSTALL_DIR=/opt/uv INSTALLER_NO_MODIFY_PATH=1 sh >/dev/null 2>&1

# 4. CPython 3.12 (cached on the overlay; no-op when warm).
#    NEVER use the image's `pip` - it is bound to 3.11 while python3 is 3.10.
uv python install 3.12 >/dev/null 2>&1

# 5. venv on tmpfs, rebuilt from the warm overlay cache
if [ ! -x "$VENV/bin/python" ]; then
  uv venv --python 3.12 "$VENV" >/dev/null 2>&1
fi

# 6. deps. torch first, from the cu128 index (driver 575 = CUDA 12.9).
if [ ! -f "$STAMP" ]; then
  uv pip install --python "$VENV/bin/python" -q \
     --index-url "${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}" torch torchvision
  uv pip install --python "$VENV/bin/python" -q -r "$REQS"
fi

# 7. verify - fail fast with a NAMED diagnosis, not a stack trace 20 min later
"$VENV/bin/python" - <<'PY'
import sys
try:
    import torch
except Exception as e:
    sys.exit(f"FAIL torch-import: {e}")
if not torch.cuda.is_available():
    sys.exit(f"FAIL cuda-unavailable: torch {torch.__version__} built for CUDA "
             f"{torch.version.cuda}; driver may be too old for this wheel")
n = torch.cuda.device_count()
if n < 1:
    sys.exit("FAIL no-devices-visible")
try:
    from ultralytics import YOLO  # noqa: F401
except Exception as e:
    sys.exit(f"FAIL ultralytics-import: {e}  (missing libGL.so.1?)")
import pandas, pyarrow, scipy  # noqa: F401
print(f"OK torch={torch.__version__} cuda={torch.version.cuda} gpus={n} "
      f"dev0={torch.cuda.get_device_name(0)}")
PY

command -v ffmpeg >/dev/null || { echo "FAIL ffmpeg-missing"; exit 1; }

touch "$STAMP"
echo "STAMP=$STAMP"
