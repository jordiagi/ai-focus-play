from __future__ import annotations

import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from src.ml.model_registry import MODELS


def download_models() -> None:
    total = len(MODELS)
    for index, model in enumerate(MODELS, start=1):
        print(f"[{index}/{total}] Fetching {model.role}: {model.repo_id}", flush=True)
        if model.source == "huggingface":
            from huggingface_hub import snapshot_download

            snapshot_download(repo_id=model.repo_id, revision=model.revision)
        else:
            import torch

            repo_dir = _download_torch_hub_repo(model.repo_id, model.revision)
            torch.hub.load(
                str(repo_dir),
                "parseq",
                pretrained=True,
                source="local",
                trust_repo=True,
            )
    print("All model weights are ready.")


def _download_torch_hub_repo(repo_id: str, revision: str) -> Path:
    torch_home = Path(os.getenv("TORCH_HOME", Path.home() / ".cache" / "torch"))
    hub_dir = torch_home / "hub"
    hub_dir.mkdir(parents=True, exist_ok=True)
    destination = hub_dir / f"{repo_id.replace('/', '_')}_{revision}"
    if destination.exists():
        return destination
    archive_url = f"https://github.com/{repo_id}/archive/{revision}.zip"
    with tempfile.TemporaryDirectory(dir=hub_dir) as temporary:
        temporary_dir = Path(temporary)
        archive_path = temporary_dir / "repository.zip"
        urllib.request.urlretrieve(archive_url, archive_path)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(temporary_dir)
        extracted = next(
            path for path in temporary_dir.iterdir() if path.is_dir()
        )
        shutil.move(str(extracted), destination)
    return destination


def main() -> int:
    try:
        download_models()
    except ImportError as exc:
        print(f"The ML dependencies are not installed: {exc}")
        print('Install them with: pip install -e ".[dev,ml]"')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
