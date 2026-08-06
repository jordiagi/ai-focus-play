from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.ml.device import get_device
from src.ml.model_registry import MODELS, ModelSpec


def _tool_version(name: str) -> str | None:
    executable = shutil.which(name)
    if executable is None:
        return None
    result = subprocess.run(
        [executable, "-version"], capture_output=True, text=True, timeout=10
    )
    first_line = (result.stdout or result.stderr).splitlines()
    return first_line[0] if result.returncode == 0 and first_line else None


def _model_present(model: ModelSpec) -> bool:
    if model.source == "torch_hub":
        torch_home = Path(os.getenv("TORCH_HOME", Path.home() / ".cache" / "torch"))
        return any((torch_home / "hub").glob("baudm_parseq_*"))
    hf_home = Path(
        os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface")
    )
    repo_dir = hf_home / "hub" / f"models--{model.repo_id.replace('/', '--')}"
    return (repo_dir / "snapshots" / model.revision).exists()


def collect_report() -> dict[str, Any]:
    return {
        "device": get_device(),
        "tools": {name: _tool_version(name) for name in ("ffmpeg", "ffprobe")},
        "models": {model.role: _model_present(model) for model in MODELS},
    }


def main() -> int:
    report = collect_report()
    print(f"Device: {report['device']}")
    for name, version in report["tools"].items():
        print(f"{name}: {version or 'missing'}")
    for role, present in report["models"].items():
        print(f"{role}: {'ready' if present else 'missing'}")
    ready = all(report["tools"].values()) and all(report["models"].values())
    if not ready:
        print("Run python -m src.ml.download_models after installing the ml extra.")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
